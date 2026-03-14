"""Tests for nanobot.gateway — protocol helpers and RoutingGateway basics."""

import json
import pytest

from nanobot.gateway.protocol import (
    JSONRPC_VERSION,
    PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND,
    INTERNAL_ERROR, AUTH_ERROR,
    make_result, make_error, make_event,
)


class TestProtocol:
    def test_make_result(self):
        raw = make_result("req-1", {"status": "ok"})
        parsed = json.loads(raw)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == "req-1"
        assert parsed["result"]["status"] == "ok"

    def test_make_error(self):
        raw = make_error("req-2", PARSE_ERROR, "Bad JSON")
        parsed = json.loads(raw)
        assert parsed["error"]["code"] == PARSE_ERROR
        assert parsed["error"]["message"] == "Bad JSON"

    def test_make_event(self):
        raw = make_event("chat.typing", {"session_key": "test"})
        parsed = json.loads(raw)
        assert parsed["method"] == "event"
        assert parsed["params"]["type"] == "chat.typing"
        assert parsed["params"]["session_key"] == "test"

    def test_error_codes(self):
        assert PARSE_ERROR == -32700
        assert INVALID_REQUEST == -32600
        assert METHOD_NOT_FOUND == -32601
        assert INTERNAL_ERROR == -32603
        assert AUTH_ERROR == -32000
