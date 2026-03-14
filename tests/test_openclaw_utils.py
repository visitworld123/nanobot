"""Tests for nanobot.base.helpers — path safety, truncation, decode."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch


def test_safe_path_within_workspace():
    from nanobot.base.helpers import safe_path, WORKSPACE_DIR
    result = safe_path("test.txt")
    assert str(result).startswith(str(WORKSPACE_DIR.resolve()))


def test_safe_path_escape_rejected():
    from nanobot.base.helpers import safe_path
    with pytest.raises(ValueError, match="escapes workspace"):
        safe_path("../../etc/passwd")


def test_truncate_short():
    from nanobot.base.helpers import truncate
    text = "hello"
    assert truncate(text, 100) == text


def test_truncate_long():
    from nanobot.base.helpers import truncate
    text = "a" * 200
    result = truncate(text, 100)
    assert "truncated" in result
    assert len(result) < len(text) + 50


def test_decode_output_utf8():
    from nanobot.base.helpers import decode_output
    assert decode_output(b"hello") == "hello"


def test_decode_output_fallback():
    from nanobot.base.helpers import decode_output
    # Invalid UTF-8 that's valid latin-1
    result = decode_output(b"\xff\xfe")
    assert isinstance(result, str)
