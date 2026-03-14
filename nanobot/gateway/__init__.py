"""WebSocket gateway with JSON-RPC protocol and message routing."""

from nanobot.gateway.routing import MessageRouter, build_session_key
from nanobot.gateway.server import RoutingGateway, ConnectedClient
from nanobot.gateway.protocol import (
    JSONRPC_VERSION,
    PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND,
    INTERNAL_ERROR, AUTH_ERROR,
    make_result, make_error, make_event,
)

__all__ = [
    "MessageRouter", "build_session_key",
    "RoutingGateway", "ConnectedClient",
    "JSONRPC_VERSION", "PARSE_ERROR", "INVALID_REQUEST",
    "METHOD_NOT_FOUND", "INTERNAL_ERROR", "AUTH_ERROR",
    "make_result", "make_error", "make_event",
]
