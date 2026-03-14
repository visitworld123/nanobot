"""Tests for nanobot.channels — Channel ABC, CLIChannel, FileChannel, ChannelRegistry."""

import pytest
from pathlib import Path

from nanobot.bus.events import InboundMessage
from nanobot.channels.base import Channel
from nanobot.channels.cli import CLIChannel
from nanobot.channels.file import FileChannel
from nanobot.channels.registry import ChannelRegistry


class TestInboundMessage:
    def test_fields(self):
        msg = InboundMessage(channel="cli", sender="user", text="hello")
        assert msg.channel == "cli"
        assert msg.sender == "user"
        assert msg.text == "hello"
        assert msg.media_urls == []
        assert msg.thread_id is None
        assert msg.timestamp > 0


class TestCLIChannel:
    def test_properties(self):
        ch = CLIChannel()
        assert ch.id == "cli"
        assert ch.label == "CLI (stdin/stdout)"
        assert ch.max_text_length == 8000

    def test_receive_empty(self):
        ch = CLIChannel()
        assert ch.receive() is None

    def test_enqueue_and_receive(self):
        ch = CLIChannel()
        ch.enqueue("hello", sender="test_user")
        msg = ch.receive()
        assert msg is not None
        assert msg.text == "hello"
        assert msg.sender == "test_user"
        assert msg.channel == "cli"
        # Second receive should be None
        assert ch.receive() is None

    def test_send(self, capsys):
        ch = CLIChannel()
        ch.send("hello world")
        captured = capsys.readouterr()
        assert "hello world" in captured.out

    def test_chunk_text(self):
        ch = CLIChannel()
        # Short text — no chunking
        assert ch.chunk_text("hello") == ["hello"]
        # Long text — chunked
        long_text = "a " * 5000
        chunks = ch.chunk_text(long_text)
        assert len(chunks) > 1


class TestFileChannel:
    def test_properties(self, tmp_path):
        inbox = tmp_path / "inbox.txt"
        outbox = tmp_path / "outbox.txt"
        ch = FileChannel(inbox_path=inbox, outbox_path=outbox)
        assert ch.id == "file"
        assert "inbox" in ch.label.lower() or "File" in ch.label
        assert ch.max_text_length == 4000

    def test_receive_no_new_content(self, tmp_path):
        inbox = tmp_path / "inbox.txt"
        outbox = tmp_path / "outbox.txt"
        ch = FileChannel(inbox_path=inbox, outbox_path=outbox)
        assert ch.receive() is None

    def test_receive_new_content(self, tmp_path):
        inbox = tmp_path / "inbox.txt"
        outbox = tmp_path / "outbox.txt"
        ch = FileChannel(inbox_path=inbox, outbox_path=outbox)
        # Append new content after channel init
        with open(inbox, "a", encoding="utf-8") as f:
            f.write("new message\n")
        msg = ch.receive()
        assert msg is not None
        assert msg.text == "new message"
        assert msg.channel == "file"
        assert msg.sender == "file_user"

    def test_send(self, tmp_path):
        inbox = tmp_path / "inbox.txt"
        outbox = tmp_path / "outbox.txt"
        ch = FileChannel(inbox_path=inbox, outbox_path=outbox)
        ch.send("hello from agent")
        content = outbox.read_text(encoding="utf-8")
        assert "hello from agent" in content


class TestChannelRegistry:
    def test_register_and_get(self):
        reg = ChannelRegistry()
        ch = CLIChannel()
        reg.register(ch)
        assert reg.get("cli") is ch
        assert reg.get("unknown") is None

    def test_duplicate_register_raises(self):
        reg = ChannelRegistry()
        ch = CLIChannel()
        reg.register(ch)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(CLIChannel())

    def test_list_channels(self):
        reg = ChannelRegistry()
        reg.register(CLIChannel())
        assert len(reg.list_channels()) == 1
        assert len(reg.channels) == 1

    def test_poll_all(self):
        reg = ChannelRegistry()
        ch = CLIChannel()
        ch.enqueue("test message")
        reg.register(ch)
        msgs = reg.poll_all()
        assert len(msgs) == 1
        assert msgs[0].text == "test message"

    def test_poll_all_empty(self):
        reg = ChannelRegistry()
        reg.register(CLIChannel())
        assert reg.poll_all() == []
