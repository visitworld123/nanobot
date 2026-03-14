"""Tests for nanobot.session.store — SessionStore CRUD operations."""

import json
import pytest
from pathlib import Path

from nanobot.session.store import SessionStore


@pytest.fixture
def tmp_store(tmp_path):
    """Create a SessionStore with temp directories."""
    store_path = tmp_path / "sessions.json"
    transcript_dir = tmp_path / "transcripts"
    return SessionStore(store_path=store_path, transcript_dir=transcript_dir)


def test_create_session(tmp_store):
    meta = tmp_store.create_session("test:cli:user")
    assert meta["session_key"] == "test:cli:user"
    assert meta["message_count"] == 0
    assert "session_id" in meta
    assert "created_at" in meta


def test_load_new_session(tmp_store):
    data = tmp_store.load_session("new:session")
    assert data["history"] == []
    assert data["metadata"]["session_key"] == "new:session"


def test_save_turn_and_reload(tmp_store):
    tmp_store.create_session("test:key")
    tmp_store.save_turn("test:key", "hello", [
        {"type": "text", "text": "Hi there!"},
    ])
    data = tmp_store.load_session("test:key")
    assert data["metadata"]["message_count"] == 1
    history = data["history"]
    assert any(m.get("role") == "user" for m in history)
    assert any(m.get("role") == "assistant" for m in history)


def test_save_turn_with_tool_calls(tmp_store):
    tmp_store.create_session("test:tools")
    tmp_store.save_turn("test:tools", "what time is it?", [
        {"type": "tool_use", "id": "call_1", "name": "get_current_time", "input": {}},
        {"type": "tool_result", "tool_use_id": "call_1", "output": "2026-03-14T12:00:00Z"},
        {"type": "text", "text": "It is noon."},
    ])
    data = tmp_store.load_session("test:tools")
    assert data["metadata"]["message_count"] == 1
    # History should contain user, tool call assistant, tool result, and final assistant
    roles = [m.get("role") for m in data["history"]]
    assert "user" in roles
    assert "assistant" in roles
    assert "tool" in roles


def test_list_sessions(tmp_store):
    tmp_store.create_session("a:b:c")
    tmp_store.create_session("x:y:z")
    sessions = tmp_store.list_sessions()
    assert len(sessions) == 2
    keys = {s["session_key"] for s in sessions}
    assert keys == {"a:b:c", "x:y:z"}


def test_session_exists(tmp_store):
    assert not tmp_store.session_exists("nope")
    tmp_store.create_session("exists")
    assert tmp_store.session_exists("exists")


def test_delete_session(tmp_store):
    tmp_store.create_session("to_delete")
    assert tmp_store.session_exists("to_delete")
    assert tmp_store.delete_session("to_delete")
    assert not tmp_store.session_exists("to_delete")
    assert not tmp_store.delete_session("to_delete")  # Already deleted
