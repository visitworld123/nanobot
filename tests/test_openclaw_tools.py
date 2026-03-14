"""Tests for nanobot.engine.tools — definitions, registry, and tool dispatch."""

import pytest

from nanobot.engine.tools.definitions import (
    TOOLS, TOOLS_OPENAI, TOOL_HANDLERS,
    process_tool_call, tools_to_openai_format,
    tool_get_current_time, tool_read_file, tool_write_file,
)
from nanobot.engine.tools.registry import ToolRegistry, SystemPromptBuilder


class TestToolDefinitions:
    def test_tools_count(self):
        # 4 base + 16 extended = 20
        assert len(TOOLS) == 20

    def test_tools_openai_format(self):
        assert len(TOOLS_OPENAI) == 20
        for tool in TOOLS_OPENAI:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_handler_count(self):
        assert len(TOOL_HANDLERS) == 20

    def test_all_tools_have_handlers(self):
        tool_names = {t["name"] for t in TOOLS}
        handler_names = set(TOOL_HANDLERS.keys())
        assert tool_names == handler_names

    def test_process_tool_call_known(self):
        result = process_tool_call("get_current_time", {})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_process_tool_call_unknown(self):
        result = process_tool_call("nonexistent_tool", {})
        assert "Error" in result
        assert "Unknown" in result

    def test_get_current_time(self):
        result = tool_get_current_time()
        assert "T" in result  # ISO format

    def test_tools_to_openai_format(self):
        sample = [{"name": "test", "description": "test tool", "input_schema": {"type": "object", "properties": {}}}]
        result = tools_to_openai_format(sample)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "test"


class TestToolRegistry:
    def test_register_and_handle(self):
        reg = ToolRegistry()
        reg.register("echo", {"type": "function", "function": {"name": "echo"}},
                     lambda text="": f"echo: {text}")
        result = reg.handle("echo", {"text": "hello"})
        assert result == "echo: hello"

    def test_handle_unknown(self):
        reg = ToolRegistry()
        assert reg.handle("unknown", {}) is None

    def test_specs(self):
        reg = ToolRegistry()
        spec = {"type": "function", "function": {"name": "test"}}
        reg.register("test", spec, lambda: "ok")
        assert len(reg.specs) == 1
        assert reg.specs[0] == spec

    def test_merge(self):
        r1 = ToolRegistry()
        r1.register("t1", {"type": "function", "function": {"name": "t1"}}, lambda: "1")
        r2 = ToolRegistry()
        r2.register("t2", {"type": "function", "function": {"name": "t2"}}, lambda: "2")
        merged = r1.merge(r2)
        assert len(merged.specs) == 2
        assert merged.handle("t1", {}) == "1"
        assert merged.handle("t2", {}) == "2"

    def test_from_definitions(self):
        reg = ToolRegistry.from_definitions(TOOLS_OPENAI, TOOL_HANDLERS)
        assert len(reg.specs) == 20
        result = reg.handle("get_current_time", {})
        assert isinstance(result, str)


class TestSystemPromptBuilder:
    def test_basic_build(self):
        pb = SystemPromptBuilder()
        pb.add_section("base", lambda ag, base: base)
        pb.add_section("extra", lambda ag, _: "Extra section")
        result = pb.build(None, "Base prompt")
        assert "Base prompt" in result
        assert "Extra section" in result

    def test_empty_sections_skipped(self):
        pb = SystemPromptBuilder()
        pb.add_section("base", lambda ag, base: base)
        pb.add_section("empty", lambda ag, _: "")
        result = pb.build(None, "Base prompt")
        assert result == "Base prompt"

    def test_default_builder(self):
        from nanobot.routing.config import AgentConfig
        agent = AgentConfig(id="test", model="m", system_prompt="Be helpful")
        pb = SystemPromptBuilder.default()
        result = pb.build(agent, "System prompt base")
        assert "System prompt base" in result
        assert "Be helpful" in result
