"""REPL modes for all layers.

Provides interactive command-line interfaces for:
- Basic agent loop (s03)
- Multi-channel gateway (s04)
- Routing REPL (s05)
- Soul+Memory REPL (s06)

Reference: OpenClaw s03-s06 REPL modes
"""

from __future__ import annotations

import sys

from nanobot.base.helpers import CYAN, GREEN, YELLOW, DIM, RESET, BOLD, MAGENTA, BLUE
from nanobot.store.store import SessionStore


def colored_prompt() -> str:
    return f"{CYAN}{BOLD}You > {RESET}"


def print_assistant(text: str) -> None:
    print(f"\n{GREEN}{BOLD}Assistant:{RESET} {text}\n")


def print_info(text: str) -> None:
    print(f"{DIM}{text}{RESET}")


def print_tool(name: str, detail: str) -> None:
    print(f"  {MAGENTA}[tool:{name}]{RESET} {DIM}{detail}{RESET}")


def print_agent(agent_id: str) -> None:
    print(f"{BLUE}[Agent: {agent_id}]{RESET}")


def run_basic_repl() -> None:
    """Basic REPL: simple agent loop with session persistence (s03 mode)."""
    from nanobot.engine.loop import agent_loop

    session_store = SessionStore()
    session_key = "cli:user:default"

    print(f"{BOLD}nanobot REPL{RESET} (type /quit to exit)")
    print_info("Session: " + session_key)

    while True:
        try:
            user_input = input(colored_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "/q"):
            print("Bye!")
            break
        if user_input == "/sessions":
            sessions = session_store.list_sessions()
            if not sessions:
                print_info("No sessions.")
            else:
                for s in sessions:
                    print_info(f"  {s['session_key']}  msgs={s.get('message_count', 0)}")
            continue

        try:
            response = agent_loop(user_input, session_key, session_store)
            print_assistant(response)
        except Exception as exc:
            print(f"{YELLOW}Error: {exc}{RESET}")


def run_routing_repl() -> None:
    """Routing REPL: test routing logic locally without gateway (s05 mode)."""
    from nanobot.routing.config import load_routing_config
    from nanobot.routing.router import MessageRouter
    from nanobot.engine.loop import run_agent_with_tools

    agents, bindings, default_agent, dm_scope = load_routing_config()
    router = MessageRouter(agents, bindings, default_agent, dm_scope)
    session_store = SessionStore()

    print(f"{BOLD}nanobot Routing REPL{RESET}")
    print(router.describe_bindings())
    print_info("Commands: /quit, /sessions, /route <channel> <sender>")

    current_channel = "cli"
    current_sender = "user"

    while True:
        try:
            user_input = input(colored_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "/q"):
            break
        if user_input == "/sessions":
            for s in session_store.list_sessions():
                print_info(f"  {s['session_key']}  msgs={s.get('message_count', 0)}")
            continue
        if user_input.startswith("/route "):
            parts = user_input.split()
            if len(parts) >= 3:
                current_channel = parts[1]
                current_sender = parts[2]
            print_info(f"Route: channel={current_channel} sender={current_sender}")
            continue

        agent, session_key = router.resolve(current_channel, current_sender)
        print_agent(agent.id)
        print_info(f"session: {session_key}")

        try:
            response = run_agent_with_tools(agent, session_store, session_key, user_input)
            print_assistant(response)
        except Exception as exc:
            print(f"{YELLOW}Error: {exc}{RESET}")


def run_soul_memory_repl() -> None:
    """Soul+Memory REPL: test with soul and memory integration (s06 mode)."""
    from nanobot.soul.prompt import (
        create_agents_with_soul_memory,
        run_agent_with_soul_and_memory,
    )
    from nanobot.routing.router import MessageRouter

    agents, bindings, default_agent, dm_scope = create_agents_with_soul_memory()
    router = MessageRouter(agents, bindings, default_agent, dm_scope)
    session_store = SessionStore()

    # Ensure sample SOUL.md
    sample_soul = """\
# SOUL.md - Who You Are

_You're not a chatbot. You're becoming someone._

## Core Truths

**Be genuinely helpful, not performatively helpful.** Skip the "Great question!" \
and "I'd be happy to help!" — just help. Actions speak louder than filler words.

**Have opinions.** You're allowed to disagree, prefer things, find stuff amusing \
or boring. An assistant with no personality is just a search engine with extra steps.

**Be resourceful before asking.** Try to figure it out. Read the file. Check the \
context. Search for it. _Then_ ask if you're stuck.

## Boundaries

- Private things stay private. Period.
- When in doubt, ask before acting externally.

## Vibe

Be the assistant you'd actually want to talk to. Concise when needed, thorough \
when it matters. Not a corporate drone. Not a sycophant. Just... good.

## Continuity

Each session, you wake up fresh. These files _are_ your memory. Read them. \
Update them. They're how you persist.
"""
    for agent in agents.values():
        if not agent.soul_path.exists():
            agent.soul_path.write_text(sample_soul, encoding="utf-8")
            print_info(f"Created sample SOUL.md at {agent.soul_path}")

    print(f"{BOLD}nanobot Soul+Memory REPL{RESET}")
    print(router.describe_bindings())
    print_info("Commands: /quit, /sessions, /route <channel> <sender>, /memory <agent_id>")

    current_channel = "cli"
    current_sender = "user"

    while True:
        try:
            user_input = input(colored_prompt()).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "/q"):
            break
        if user_input == "/sessions":
            for s in session_store.list_sessions():
                print_info(f"  {s['session_key']}  msgs={s.get('message_count', 0)}")
            continue
        if user_input.startswith("/route "):
            parts = user_input.split()
            if len(parts) >= 3:
                current_channel = parts[1]
                current_sender = parts[2]
            print_info(f"Route: channel={current_channel} sender={current_sender}")
            continue
        if user_input.startswith("/memory"):
            from nanobot.soul.search import get_memory_manager
            parts = user_input.split()
            agent_id = parts[1] if len(parts) > 1 else default_agent
            if agent_id in agents:
                mgr = get_memory_manager(agents[agent_id])
                print_info(f"Memory for {agent_id}:")
                print_info(f"  Evergreen: {len(mgr.load_evergreen())} chars")
                recent = mgr.get_recent_daily(days=7)
                for r in recent:
                    print_info(f"  {r['date']}: {r['content'].count(chr(10)) + 1} lines")
            else:
                print_info(f"Unknown agent: {agent_id}")
            continue

        agent, session_key = router.resolve(current_channel, current_sender)
        print_agent(agent.id)
        print_info(f"session: {session_key}")

        try:
            response = run_agent_with_soul_and_memory(agent, session_store, session_key, user_input)
            print_assistant(response)
        except Exception as exc:
            print(f"{YELLOW}Error: {exc}{RESET}")
