"""Multi-channel abstraction layer.

Provides Channel ABC, CLIChannel, FileChannel, and ChannelRegistry.
Reference: OpenClaw s04_multi_channel.py
"""

from nanobot.channels.base import Channel
from nanobot.channels.cli import CLIChannel
from nanobot.channels.file import FileChannel
from nanobot.channels.registry import ChannelRegistry

__all__ = ["Channel", "CLIChannel", "FileChannel", "ChannelRegistry"]
