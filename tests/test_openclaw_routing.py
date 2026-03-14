"""Tests for nanobot.config and nanobot.gateway.routing — AgentConfig, Binding, MessageRouter."""

import json
import pytest
from pathlib import Path

from nanobot.config.loader import AgentConfig, Binding, load_routing_config, DEFAULT_CONFIG
from nanobot.gateway.routing import MessageRouter, build_session_key


class TestAgentConfig:
    def test_basic(self):
        cfg = AgentConfig(id="test", model="gpt-4", system_prompt="You are helpful.")
        assert cfg.id == "test"
        assert cfg.model == "gpt-4"
        assert "test" in repr(cfg)

    def test_defaults(self):
        cfg = AgentConfig(id="x", model="m", system_prompt="p")
        assert cfg.tools == []


class TestBinding:
    def test_repr_with_conditions(self):
        b = Binding(channel="telegram", agent_id="alice", priority=10)
        r = repr(b)
        assert "telegram" in r
        assert "alice" in r

    def test_repr_wildcard(self):
        b = Binding(agent_id="main", priority=0)
        r = repr(b)
        assert "*" in r


class TestBuildSessionKey:
    def test_direct_per_peer(self):
        key = build_session_key("alice", "telegram", "default", "direct", "user-123", "per-peer")
        assert key == "agent:alice:direct:user-123"

    def test_direct_per_channel_peer(self):
        key = build_session_key("alice", "telegram", "default", "direct", "user-123", "per-channel-peer")
        assert key == "agent:alice:telegram:direct:user-123"

    def test_direct_main_scope(self):
        key = build_session_key("alice", "telegram", "default", "direct", "user-123", "main")
        assert key == "agent:alice:main"

    def test_group(self):
        key = build_session_key("alice", "discord", "default", "group", "dev-server")
        assert key == "agent:alice:discord:group:dev-server"


class TestMessageRouter:
    @pytest.fixture
    def router(self):
        agents = {
            "main": AgentConfig(id="main", model="m", system_prompt="General"),
            "alice": AgentConfig(id="alice", model="m", system_prompt="Alice"),
            "bob": AgentConfig(id="bob", model="m", system_prompt="Bob"),
        }
        bindings = [
            Binding(peer_id="user-alice-fan", agent_id="alice", priority=40),
            Binding(guild_id="dev-server", agent_id="bob", priority=30),
            Binding(channel="telegram", agent_id="main", priority=10),
        ]
        return MessageRouter(agents, bindings, default_agent="main", dm_scope="per-peer")

    def test_default_routing(self, router):
        agent, key = router.resolve("slack", "random-user")
        assert agent.id == "main"

    def test_peer_routing(self, router):
        agent, key = router.resolve("telegram", "user-alice-fan")
        assert agent.id == "alice"

    def test_guild_routing(self, router):
        agent, key = router.resolve("discord", "someone", peer_kind="group", guild_id="dev-server")
        assert agent.id == "bob"

    def test_channel_routing(self, router):
        agent, key = router.resolve("telegram", "random-user")
        assert agent.id == "main"

    def test_priority_order(self, router):
        # user-alice-fan on discord dev-server group: peer binding (p=40) > guild (p=30)
        agent, key = router.resolve("discord", "user-alice-fan", peer_kind="group", guild_id="dev-server")
        assert agent.id == "alice"

    def test_describe_bindings(self, router):
        desc = router.describe_bindings()
        assert "priority" in desc.lower() or "Routing" in desc
        assert "main" in desc


class TestLoadRoutingConfig:
    def test_default_config(self):
        agents, bindings, default, dm_scope = load_routing_config()
        assert "main" in agents
        assert isinstance(bindings, list)
        assert default == "main"
        assert dm_scope == "per-peer"

    def test_from_file(self, tmp_path):
        config = {
            "agents": [
                {"id": "test", "model": "m", "system_prompt": "test agent"},
            ],
            "bindings": [],
            "default_agent": "test",
            "dm_scope": "main",
        }
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps(config), encoding="utf-8")
        agents, bindings, default, dm_scope = load_routing_config(str(cfg_path))
        assert "test" in agents
        assert default == "test"
        assert dm_scope == "main"
