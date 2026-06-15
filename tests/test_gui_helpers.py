"""Tests for desktop GUI input and error helpers without opening a window."""

from mailapp.client.gui import friendly_error, parse_recipients
from mailapp.common.exceptions import AuthenticationError, RecallError


def test_parse_recipients_deduplicates_and_accepts_semicolon():
    assert parse_recipients(
        "bob@example.com; carol@example.com, bob@example.com"
    ) == ["bob@example.com", "carol@example.com"]


def test_friendly_error_messages():
    assert "Authentication failed" in friendly_error(AuthenticationError("bad"))
    assert "Recall failed" in friendly_error(RecallError("not owner"))
