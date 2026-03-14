"""Tests for nanobot.soul — workspace, search, memory tools, prompt builder."""

import json
import pytest
from pathlib import Path

from nanobot.soul.workspace import (
    AgentWithSoulMemory,
    load_workspace_bootstrap_files,
    _truncate_bootstrap,
    BOOTSTRAP_MAX_CHARS,
)
from nanobot.soul.search import (
    MemoryIndexManager,
    _tokenize,
    _cosine_sim,
    _bm25_score,
    SEARCH_MAX_RESULTS,
)
from nanobot.soul.tools import (
    build_memory_tools,
    handle_memory_tool,
    MEMORY_TOOL_NAMES,
)


class TestWorkspace:
    def test_agent_workspace_creation(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test",
            model="m",
            system_prompt="test",
            workspace_dir=tmp_path / "test",
        )
        assert agent.workspace_dir.exists()
        assert agent.memory_dir.exists()
        assert agent.soul_path == tmp_path / "test" / "SOUL.md"
        assert agent.memory_md_path == tmp_path / "test" / "MEMORY.md"

    def test_truncate_bootstrap_short(self):
        text = "short text"
        assert _truncate_bootstrap(text) == text

    def test_truncate_bootstrap_long(self):
        text = "a" * 25000
        result = _truncate_bootstrap(text)
        assert len(result) < len(text)
        assert "truncated" in result

    def test_load_bootstrap_files(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "SOUL.md").write_text("# Soul\nI am helpful.", encoding="utf-8")
        (ws / "MEMORY.md").write_text("# Memory\nRemember this.", encoding="utf-8")
        files = load_workspace_bootstrap_files(ws)
        assert len(files) == 2
        assert files[0]["name"] == "SOUL.md"
        assert files[1]["name"] == "MEMORY.md"

    def test_load_bootstrap_no_files(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        files = load_workspace_bootstrap_files(ws)
        assert files == []

    def test_load_bootstrap_symlink_skipped(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        target = tmp_path / "real.md"
        target.write_text("content", encoding="utf-8")
        (ws / "SOUL.md").symlink_to(target)
        files = load_workspace_bootstrap_files(ws)
        assert len(files) == 0


class TestTokenize:
    def test_basic(self):
        tokens = _tokenize("Hello World 2026")
        assert "hello" in tokens
        assert "world" in tokens
        assert "2026" in tokens

    def test_chinese(self):
        tokens = _tokenize("我好")
        # Chinese chars are in range \u4e00-\u9fff
        assert len(tokens) > 0

    def test_empty(self):
        assert _tokenize("") == []

    def test_single_char_filtered(self):
        # Single ASCII chars should be filtered
        tokens = _tokenize("a b c")
        assert tokens == []


class TestCosineSim:
    def test_identical(self):
        vec = {"a": 1.0, "b": 2.0}
        assert abs(_cosine_sim(vec, vec) - 1.0) < 0.001

    def test_orthogonal(self):
        a = {"x": 1.0}
        b = {"y": 1.0}
        assert _cosine_sim(a, b) == 0.0

    def test_empty(self):
        assert _cosine_sim({}, {"a": 1.0}) == 0.0


class TestMemoryIndexManager:
    @pytest.fixture
    def mgr(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "memory").mkdir()
        return MemoryIndexManager(ws)

    def test_write_daily(self, mgr):
        path = mgr.write_daily("test content", category="fact")
        assert "memory/" in path
        assert ".md" in path
        # Verify file exists
        full_path = mgr.workspace_dir / path
        assert full_path.exists()
        content = full_path.read_text(encoding="utf-8")
        assert "test content" in content
        assert "fact" in content

    def test_write_daily_append(self, mgr):
        mgr.write_daily("first entry")
        mgr.write_daily("second entry")
        # Get today's file
        from datetime import date
        path = mgr.memory_dir / f"{date.today().isoformat()}.md"
        content = path.read_text(encoding="utf-8")
        assert "first entry" in content
        assert "second entry" in content

    def test_read_file(self, mgr):
        (mgr.workspace_dir / "MEMORY.md").write_text("# Memory\nLine 1\nLine 2\nLine 3\n", encoding="utf-8")
        result = mgr.read_file("MEMORY.md")
        assert result["text"] != ""
        assert "Memory" in result["text"]

    def test_read_file_with_range(self, mgr):
        (mgr.workspace_dir / "MEMORY.md").write_text("Line 1\nLine 2\nLine 3\nLine 4\n", encoding="utf-8")
        result = mgr.read_file("MEMORY.md", from_line=2, n_lines=2)
        assert "Line 2" in result["text"]
        assert "Line 3" in result["text"]

    def test_read_file_access_denied(self, mgr):
        result = mgr.read_file("../../etc/passwd")
        assert "error" in result
        assert "denied" in result["error"].lower() or "Access" in result["error"]

    def test_read_file_not_found(self, mgr):
        result = mgr.read_file("MEMORY.md")
        assert "error" in result or result["text"] == ""

    def test_load_evergreen(self, mgr):
        assert mgr.load_evergreen() == ""
        (mgr.workspace_dir / "MEMORY.md").write_text("# Long-term memory", encoding="utf-8")
        assert "Long-term memory" in mgr.load_evergreen()

    def test_search_empty(self, mgr):
        results = mgr.search("anything")
        assert results == []

    def test_search_with_content(self, mgr):
        (mgr.workspace_dir / "MEMORY.md").write_text(
            "# Preferences\n\nThe user prefers dark mode and vim keybindings.\n"
            "They work on Python projects mainly.\n\n"
            "# Decisions\n\nWe decided to use PostgreSQL for the database.\n"
            "The deployment will be on AWS using ECS containers.\n\n"
            "# People\n\nAlice is the project manager.\n"
            "Bob is the lead developer working on the backend.\n",
            encoding="utf-8",
        )
        results = mgr.search("dark mode preferences", min_score=0.1)
        assert len(results) > 0
        assert results[0]["score"] > 0

    def test_search_relevance(self, mgr):
        (mgr.workspace_dir / "MEMORY.md").write_text(
            "# Database\n\nWe use PostgreSQL for data storage.\n\n"
            "# Colors\n\nThe user likes blue and dark themes.\n\n"
            "# Food\n\nThe user prefers sushi and ramen.\n",
            encoding="utf-8",
        )
        results = mgr.search("PostgreSQL database", min_score=0.1)
        assert len(results) > 0
        # Best result should mention database/PostgreSQL
        assert "PostgreSQL" in results[0]["snippet"] or "database" in results[0]["snippet"].lower()

    def test_get_recent_daily(self, mgr):
        mgr.write_daily("test entry")
        recent = mgr.get_recent_daily(days=1)
        assert len(recent) == 1
        assert "test entry" in recent[0]["content"]


class TestMemoryTools:
    def test_build_memory_tools(self):
        tools = build_memory_tools()
        assert len(tools) == 3
        names = {t["function"]["name"] for t in tools}
        assert names == {"memory_search", "memory_get", "memory_write"}

    def test_tool_names_constant(self):
        assert MEMORY_TOOL_NAMES == {"memory_search", "memory_get", "memory_write"}

    def test_handle_memory_write(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test", model="m", system_prompt="test",
            workspace_dir=tmp_path / "test",
        )
        result = handle_memory_tool("memory_write", {"content": "remember this", "category": "fact"}, agent)
        data = json.loads(result)
        assert data["status"] == "saved"
        assert "memory/" in data["path"]

    def test_handle_memory_search_empty(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test2", model="m", system_prompt="test",
            workspace_dir=tmp_path / "test2",
        )
        result = handle_memory_tool("memory_search", {"query": "anything"}, agent)
        data = json.loads(result)
        assert data["results"] == []

    def test_handle_memory_get(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test3", model="m", system_prompt="test",
            workspace_dir=tmp_path / "test3",
        )
        (agent.workspace_dir / "MEMORY.md").write_text("# Test\nContent here", encoding="utf-8")
        result = handle_memory_tool("memory_get", {"path": "MEMORY.md"}, agent)
        data = json.loads(result)
        assert "Content here" in data["text"]

    def test_handle_empty_query(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test4", model="m", system_prompt="test",
            workspace_dir=tmp_path / "test4",
        )
        result = handle_memory_tool("memory_search", {"query": ""}, agent)
        data = json.loads(result)
        assert "error" in data

    def test_handle_unknown_tool(self, tmp_path):
        agent = AgentWithSoulMemory(
            id="test5", model="m", system_prompt="test",
            workspace_dir=tmp_path / "test5",
        )
        result = handle_memory_tool("unknown_tool", {}, agent)
        data = json.loads(result)
        assert "error" in data
