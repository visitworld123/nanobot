"""Tests for nanobot.node — NodeInfo, NodePairingStore, NodeRegistry, events, tools."""

import json
import time
import pytest
from pathlib import Path

from nanobot.node.info import (
    NodeInfo,
    NODE_CMD_SYSTEM_RUN,
    NODE_CMD_SYSTEM_NOTIFY,
    NODE_CMD_CAMERA_SNAP,
    NODE_CMD_LOCATION,
    NODE_CMD_SCREEN_SNAP,
    DEFAULT_ALLOWED_COMMANDS,
)
from nanobot.node.pairing import NodePairingStore, PENDING_TTL_S
from nanobot.node.registry import NodeRegistry, ConnectedNode, PendingInvoke
from nanobot.node.events import NodeEventSource, handle_node_event
from nanobot.node.client import SimulatedNodeHandler
from nanobot.node.tools import (
    execute_node_tool,
    build_node_tool_registry,
    NODE_TOOL_SPEC,
    NODE_LIST_TOOL_SPEC,
)


# ============================================================================
# NodeInfo
# ============================================================================

class TestNodeInfo:
    def test_basic_creation(self):
        info = NodeInfo(node_id="abc123", display_name="My Phone", platform="ios")
        assert info.node_id == "abc123"
        assert info.display_name == "My Phone"
        assert info.platform == "ios"
        assert info.caps == []
        assert info.commands == []

    def test_repr(self):
        info = NodeInfo(node_id="abc123", display_name="Phone", platform="ios")
        r = repr(info)
        assert "Phone" in r
        assert "ios" in r

    def test_repr_no_name(self):
        info = NodeInfo(node_id="abcdefgh1234")
        r = repr(info)
        assert "abcdefgh" in r

    def test_to_dict(self):
        info = NodeInfo(
            node_id="n1",
            display_name="Test",
            platform="android",
            version="1.0",
            caps=["exec", "camera"],
            commands=["system.run"],
            permissions={"camera": True},
        )
        d = info.to_dict()
        assert d["node_id"] == "n1"
        assert d["display_name"] == "Test"
        assert d["platform"] == "android"
        assert d["version"] == "1.0"
        assert d["caps"] == ["exec", "camera"]
        assert d["commands"] == ["system.run"]
        assert d["permissions"] == {"camera": True}

    def test_from_dict(self):
        d = {
            "node_id": "n2",
            "display_name": "Laptop",
            "platform": "macos",
            "version": "2.0",
            "caps": ["exec"],
            "commands": ["system.run", "system.notify"],
        }
        info = NodeInfo.from_dict(d)
        assert info.node_id == "n2"
        assert info.display_name == "Laptop"
        assert info.platform == "macos"
        assert info.caps == ["exec"]

    def test_from_dict_missing_fields(self):
        info = NodeInfo.from_dict({})
        assert info.node_id == ""
        assert info.caps == []

    def test_command_constants(self):
        assert NODE_CMD_SYSTEM_RUN == "system.run"
        assert NODE_CMD_SYSTEM_NOTIFY == "system.notify"
        assert NODE_CMD_CAMERA_SNAP == "camera.snap"
        assert NODE_CMD_LOCATION == "location.get"
        assert NODE_CMD_SCREEN_SNAP == "screen.snap"

    def test_allowed_commands(self):
        assert NODE_CMD_SYSTEM_RUN in DEFAULT_ALLOWED_COMMANDS
        assert NODE_CMD_CAMERA_SNAP in DEFAULT_ALLOWED_COMMANDS
        assert "dangerous.command" not in DEFAULT_ALLOWED_COMMANDS


# ============================================================================
# NodePairingStore
# ============================================================================

class TestNodePairingStore:
    @pytest.fixture
    def store(self, tmp_path):
        return NodePairingStore(tmp_path / "pairing.json")

    def test_request_pairing(self, store):
        info = NodeInfo(node_id="phone-1", display_name="iPhone", platform="ios")
        result = store.request_pairing(info)
        assert result["status"] == "pending"
        assert "request_id" in result
        assert result["created"] is True

    def test_request_pairing_reuse(self, store):
        info = NodeInfo(node_id="phone-1", display_name="iPhone", platform="ios")
        r1 = store.request_pairing(info)
        r2 = store.request_pairing(info)
        assert r1["request_id"] == r2["request_id"]
        assert r2["created"] is False

    def test_request_pairing_empty_id(self, store):
        info = NodeInfo(node_id="", display_name="Bad")
        with pytest.raises(ValueError, match="node_id required"):
            store.request_pairing(info)

    def test_approve(self, store):
        info = NodeInfo(node_id="phone-1", display_name="iPhone", platform="ios")
        req = store.request_pairing(info)
        result = store.approve(req["request_id"])
        assert result is not None
        assert result["node"]["node_id"] == "phone-1"
        assert "token" in result["node"]
        assert len(result["node"]["token"]) > 10

    def test_approve_nonexistent(self, store):
        assert store.approve("fake-id") is None

    def test_reject(self, store):
        info = NodeInfo(node_id="phone-1", display_name="iPhone", platform="ios")
        req = store.request_pairing(info)
        result = store.reject(req["request_id"])
        assert result is not None
        assert result["node_id"] == "phone-1"
        # After rejection, pending should be empty
        listing = store.list_pairing()
        assert len(listing["pending"]) == 0

    def test_reject_nonexistent(self, store):
        assert store.reject("fake-id") is None

    def test_verify_token(self, store):
        info = NodeInfo(node_id="phone-1", display_name="iPhone")
        req = store.request_pairing(info)
        result = store.approve(req["request_id"])
        token = result["node"]["token"]

        # Correct token
        verified = store.verify_token("phone-1", token)
        assert verified is not None
        assert verified["node_id"] == "phone-1"

        # Wrong token
        assert store.verify_token("phone-1", "wrong-token") is None

        # Wrong node_id
        assert store.verify_token("phone-999", token) is None

    def test_list_pairing(self, store):
        info1 = NodeInfo(node_id="p1", display_name="Phone 1")
        info2 = NodeInfo(node_id="p2", display_name="Phone 2")
        store.request_pairing(info1)
        req2 = store.request_pairing(info2)
        store.approve(req2["request_id"])

        listing = store.list_pairing()
        assert len(listing["pending"]) == 1
        assert len(listing["paired"]) == 1
        assert listing["pending"][0]["node_id"] == "p1"
        assert listing["paired"][0]["node_id"] == "p2"

    def test_rename_node(self, store):
        info = NodeInfo(node_id="p1", display_name="Old Name")
        req = store.request_pairing(info)
        store.approve(req["request_id"])

        result = store.rename_node("p1", "New Name")
        assert result is not None
        assert result["display_name"] == "New Name"

    def test_rename_nonexistent(self, store):
        assert store.rename_node("fake", "Name") is None

    def test_rename_empty_name(self, store):
        info = NodeInfo(node_id="p1", display_name="Old")
        req = store.request_pairing(info)
        store.approve(req["request_id"])
        with pytest.raises(ValueError, match="display_name required"):
            store.rename_node("p1", "")

    def test_update_metadata(self, store):
        info = NodeInfo(node_id="p1", display_name="Phone", version="1.0")
        req = store.request_pairing(info)
        store.approve(req["request_id"])

        store.update_metadata("p1", {"version": "2.0", "last_connected_at": 12345})
        listing = store.list_pairing()
        paired = listing["paired"][0]
        assert paired["version"] == "2.0"
        assert paired["last_connected_at"] == 12345

    def test_repair_flow(self, store):
        """Test re-pairing an already paired device."""
        info = NodeInfo(node_id="p1", display_name="Phone")
        req1 = store.request_pairing(info)
        store.approve(req1["request_id"])

        # Re-request should be flagged as repair
        req2 = store.request_pairing(info)
        listing = store.list_pairing()
        pending = listing["pending"]
        assert len(pending) == 1
        assert pending[0].get("is_repair") is True


# ============================================================================
# NodeRegistry
# ============================================================================

class TestNodeRegistry:
    def _make_node(self, node_id="n1", display_name="Test Node"):
        class MockWS:
            async def send(self, data):
                pass
            async def close(self):
                pass

        info = NodeInfo(node_id=node_id, display_name=display_name, platform="test")
        return ConnectedNode(node_id=node_id, info=info, ws=MockWS())

    def test_register_and_get(self):
        reg = NodeRegistry()
        node = self._make_node("n1")
        reg.register(node)
        assert reg.get("n1") is node
        assert reg.get("n2") is None

    def test_list_nodes(self):
        reg = NodeRegistry()
        reg.register(self._make_node("n1"))
        reg.register(self._make_node("n2"))
        nodes = reg.list_nodes()
        assert len(nodes) == 2

    def test_unregister(self):
        reg = NodeRegistry()
        node = self._make_node("n1")
        reg.register(node)
        removed = reg.unregister("n1")
        assert removed is node
        assert reg.get("n1") is None

    def test_unregister_nonexistent(self):
        reg = NodeRegistry()
        assert reg.unregister("fake") is None

    def test_update_tick(self):
        reg = NodeRegistry()
        node = self._make_node("n1")
        reg.register(node)
        reg.update_tick("n1")
        assert node.last_tick_at > 0

    def test_replace_existing(self):
        reg = NodeRegistry()
        n1 = self._make_node("n1", "First")
        n2 = self._make_node("n1", "Second")
        reg.register(n1)
        reg.register(n2)
        assert reg.get("n1").info.display_name == "Second"

    def test_invoke_not_connected(self):
        reg = NodeRegistry()
        result = reg.invoke("fake", "system.run")
        assert result["error"] == "node_not_found"

    def test_invoke_command_not_allowed(self):
        reg = NodeRegistry()
        reg.register(self._make_node("n1"))
        result = reg.invoke("n1", "dangerous.command")
        assert result["error"] == "command_not_allowed"

    def test_handle_invoke_result_unknown(self):
        reg = NodeRegistry()
        assert reg.handle_invoke_result("fake-id", {"ok": True}) is False

    def test_lifecycle_callbacks(self):
        reg = NodeRegistry()
        connected = []
        disconnected = []
        ticks = []

        reg.on_node_connect = lambda nid, info: connected.append(nid)
        reg.on_node_disconnect = lambda nid, info: disconnected.append(nid)
        reg.on_node_tick = lambda nid: ticks.append(nid)

        node = self._make_node("n1")
        reg.register(node)
        assert connected == ["n1"]

        reg.update_tick("n1")
        assert ticks == ["n1"]

        reg.unregister("n1")
        assert disconnected == ["n1"]


# ============================================================================
# NodeEventSource
# ============================================================================

class TestNodeEventSource:
    def test_start_stop(self):
        reg = NodeRegistry()
        source = NodeEventSource(reg)
        source.start()
        assert source._started is True
        source.stop()
        assert source._started is False

    def test_status(self):
        reg = NodeRegistry()
        source = NodeEventSource(reg)
        s = source.status()
        assert s["name"] == "node"
        assert s["online_nodes"] == 0

    def test_emit_on_connect(self):
        reg = NodeRegistry()
        source = NodeEventSource(reg)
        events = []
        source._emit_callback = lambda e: events.append(e)
        source.start()

        class MockWS:
            async def send(self, data): pass
            async def close(self): pass

        info = NodeInfo(node_id="n1", display_name="Phone", platform="ios")
        node = ConnectedNode(node_id="n1", info=info, ws=MockWS())
        reg.register(node)

        assert len(events) == 1
        assert events[0]["type"] == "node.connected"
        assert events[0]["payload"]["node_id"] == "n1"

    def test_no_emit_when_stopped(self):
        reg = NodeRegistry()
        source = NodeEventSource(reg)
        events = []
        source._emit_callback = lambda e: events.append(e)
        # Not started

        class MockWS:
            async def send(self, data): pass
            async def close(self): pass

        info = NodeInfo(node_id="n1", platform="ios")
        node = ConnectedNode(node_id="n1", info=info, ws=MockWS())
        reg.register(node)

        assert len(events) == 0


class TestHandleNodeEvent:
    def test_exec_started(self):
        text = handle_node_event("n1", "exec.started", {"command": "ls", "run_id": "r1"})
        assert text is not None
        assert "Exec started" in text
        assert "n1" in text

    def test_exec_finished_success_no_output(self):
        text = handle_node_event("n1", "exec.finished", {"exit_code": 0})
        assert text is None  # Silent on clean success

    def test_exec_finished_with_output(self):
        text = handle_node_event("n1", "exec.finished", {
            "exit_code": 0,
            "output": "some output",
        })
        assert text is not None
        assert "some output" in text

    def test_exec_finished_error(self):
        text = handle_node_event("n1", "exec.finished", {"exit_code": 1})
        assert text is not None
        assert "code 1" in text

    def test_exec_finished_timeout(self):
        text = handle_node_event("n1", "exec.finished", {"timed_out": True})
        assert text is not None
        assert "timeout" in text

    def test_exec_denied(self):
        text = handle_node_event("n1", "exec.denied", {
            "command": "rm -rf /",
            "reason": "blocked",
        })
        assert text is not None
        assert "denied" in text.lower()

    def test_notification_posted(self):
        text = handle_node_event("n1", "notifications.changed", {
            "change": "posted",
            "key": "k1",
            "title": "New Message",
            "text": "Hello",
        })
        assert text is not None
        assert "posted" in text.lower()
        assert "New Message" in text

    def test_notification_removed(self):
        text = handle_node_event("n1", "notifications.changed", {
            "change": "removed",
            "key": "k1",
        })
        assert text is not None
        assert "removed" in text.lower()

    def test_notification_unknown_change(self):
        text = handle_node_event("n1", "notifications.changed", {"change": "unknown"})
        assert text is None

    def test_voice_transcript(self):
        text = handle_node_event("n1", "voice.transcript", {"text": "Hello world"})
        assert text is not None
        assert "Hello world" in text

    def test_voice_transcript_empty(self):
        text = handle_node_event("n1", "voice.transcript", {"text": ""})
        assert text is None

    def test_unknown_event(self):
        text = handle_node_event("n1", "unknown.event", {})
        assert text is None


# ============================================================================
# SimulatedNodeHandler
# ============================================================================

class TestSimulatedNodeHandler:
    def test_system_run(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "system.run", {"cmd": "echo hello"})
        assert result["ok"] is True
        assert "echo hello" in result["data"]["stdout"]

    def test_system_notify(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "system.notify", {})
        assert result["ok"] is True

    def test_camera_snap(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "camera.snap", {})
        assert result["ok"] is True
        assert result["data"]["format"] == "jpeg"

    def test_location_get(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "location.get", {})
        assert result["ok"] is True
        assert "latitude" in result["data"]

    def test_screen_snap(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "screen.snap", {})
        assert result["ok"] is True

    def test_unsupported_command(self):
        handler = SimulatedNodeHandler("n1")
        result = handler.handle_invoke("i1", "unknown.cmd", {})
        assert "error" in result


# ============================================================================
# Node Tools
# ============================================================================

class TestNodeTools:
    def test_tool_specs(self):
        assert NODE_TOOL_SPEC["type"] == "function"
        assert NODE_TOOL_SPEC["function"]["name"] == "node_invoke"
        assert NODE_LIST_TOOL_SPEC["function"]["name"] == "node_list"

    def test_node_list_empty(self):
        reg = NodeRegistry()
        result = json.loads(execute_node_tool("node_list", {}, reg))
        assert result["nodes"] == []

    def test_node_list_with_nodes(self):
        reg = NodeRegistry()

        class MockWS:
            async def send(self, data): pass
            async def close(self): pass

        info = NodeInfo(node_id="n1", display_name="Phone", platform="ios",
                       caps=["exec"])
        node = ConnectedNode(node_id="n1", info=info, ws=MockWS())
        reg.register(node)

        result = json.loads(execute_node_tool("node_list", {}, reg))
        assert len(result["nodes"]) == 1
        assert result["nodes"][0]["node_id"] == "n1"
        assert result["nodes"][0]["display_name"] == "Phone"

    def test_node_invoke_missing_id(self):
        reg = NodeRegistry()
        result = json.loads(execute_node_tool("node_invoke", {"command": "test"}, reg))
        assert "error" in result

    def test_node_invoke_missing_command(self):
        reg = NodeRegistry()
        result = json.loads(execute_node_tool(
            "node_invoke", {"node_id": "n1"}, reg
        ))
        assert "error" in result

    def test_node_invoke_not_connected(self):
        reg = NodeRegistry()
        result = json.loads(execute_node_tool(
            "node_invoke",
            {"node_id": "n1", "command": "system.run", "args": {}},
            reg,
        ))
        assert result["error"] == "node_not_found"

    def test_unknown_tool(self):
        reg = NodeRegistry()
        result = json.loads(execute_node_tool("unknown_tool", {}, reg))
        assert "error" in result

    def test_build_registry(self):
        node_reg = NodeRegistry()
        tool_reg = build_node_tool_registry(node_reg)
        assert len(tool_reg.specs) == 2
        names = {s["function"]["name"] for s in tool_reg.specs}
        assert "node_list" in names
        assert "node_invoke" in names

    def test_registry_handle_node_list(self):
        node_reg = NodeRegistry()
        tool_reg = build_node_tool_registry(node_reg)
        result = tool_reg.handle("node_list", {})
        assert result is not None
        parsed = json.loads(result)
        assert "nodes" in parsed

    def test_registry_handle_unknown(self):
        node_reg = NodeRegistry()
        tool_reg = build_node_tool_registry(node_reg)
        result = tool_reg.handle("nonexistent", {})
        assert result is None
