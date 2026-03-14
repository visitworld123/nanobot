"""Entry point for running nanobot as a module: python -m nanobot

Usage:
  python -m nanobot                  Basic REPL (s03 mode)
  python -m nanobot --repl           Basic REPL (s03 mode)
  python -m nanobot --routing        Routing REPL (s05 mode)
  python -m nanobot --soul           Soul+Memory REPL (s06 mode)
  python -m nanobot --gateway        Start WebSocket gateway (s05)
  python -m nanobot --soul-gateway   Start Soul+Memory gateway (s06)
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="nanobot - AI agent framework")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--repl", action="store_true", help="Basic REPL (s03)")
    group.add_argument("--routing", action="store_true", help="Routing REPL (s05)")
    group.add_argument("--soul", action="store_true", help="Soul+Memory REPL (s06)")
    group.add_argument("--gateway", action="store_true", help="WebSocket gateway (s05)")
    group.add_argument("--soul-gateway", action="store_true", help="Soul+Memory gateway (s06)")

    args = parser.parse_args()

    if args.routing:
        from nanobot.cli.repl import run_routing_repl
        run_routing_repl()
    elif args.soul:
        from nanobot.cli.repl import run_soul_memory_repl
        run_soul_memory_repl()
    elif args.gateway:
        import asyncio
        import os
        from nanobot.config.loader import load_routing_config
        from nanobot.gateway.routing import MessageRouter
        from nanobot.gateway.server import RoutingGateway
        from nanobot.session.store import SessionStore

        agents, bindings, default_agent, dm_scope = load_routing_config()
        router = MessageRouter(agents, bindings, default_agent, dm_scope)
        sessions = SessionStore()
        host = os.getenv("GATEWAY_HOST", "127.0.0.1")
        port = int(os.getenv("GATEWAY_PORT", "18789"))
        token = os.getenv("GATEWAY_TOKEN", "")
        gw = RoutingGateway(host, port, router, sessions, token)
        asyncio.run(gw.start())
    elif args.soul_gateway:
        import asyncio
        import os
        from nanobot.soul.prompt import create_agents_with_soul_memory
        from nanobot.gateway.routing import MessageRouter
        from nanobot.soul.gateway import SoulMemoryGateway
        from nanobot.session.store import SessionStore

        agents, bindings, default_agent, dm_scope = create_agents_with_soul_memory()
        router = MessageRouter(agents, bindings, default_agent, dm_scope)
        sessions = SessionStore()
        host = os.getenv("GATEWAY_HOST", "127.0.0.1")
        port = int(os.getenv("GATEWAY_PORT", "18789"))
        token = os.getenv("GATEWAY_TOKEN", "")
        gw = SoulMemoryGateway(host, port, router, sessions, agents, token)
        asyncio.run(gw.start())
    else:
        from nanobot.cli.repl import run_basic_repl
        run_basic_repl()


if __name__ == "__main__":
    main()
