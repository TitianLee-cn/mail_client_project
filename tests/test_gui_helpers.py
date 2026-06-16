"""Tests for desktop GUI input and error helpers without opening a window."""

from mailapp.client.gui import (
    SPAM_ROW_TAG,
    friendly_error,
    format_mailbox_subject,
    mailbox_display_row,
    parse_recipients,
)
from mailapp.common.exceptions import AuthenticationError, RecallError
from mailapp.common.constants import FOLDER_INBOX, FOLDER_SPAM


def test_parse_recipients_deduplicates_and_accepts_semicolon():
    assert parse_recipients(
        "bob@example.com; carol@example.com, bob@example.com"
    ) == ["bob@example.com", "carol@example.com"]


def test_friendly_error_messages():
    assert "Authentication failed" in friendly_error(AuthenticationError("bad"))
    assert "Recall failed" in friendly_error(RecallError("not owner"))


def test_spam_mailbox_row_is_prefixed_and_tagged():
    row = {
        "subject": "Win Lottery Now",
        "sender": "alice@example.com",
        "status": "normal",
        "created_at": "2026-06-16 10:00:00",
        "mail_id": "mail-1",
        "is_spam": 1,
    }
    values, tags = mailbox_display_row(row, FOLDER_SPAM)
    assert values[0] == "[SPAM] Win Lottery Now"
    assert values[2] == "spam"
    assert tags == (SPAM_ROW_TAG,)


def test_spam_subject_prefix_is_not_duplicated():
    assert format_mailbox_subject("[SPAM] Win Lottery Now", True) == "[SPAM] Win Lottery Now"
    row = {
        "subject": "Project Update",
        "sender": "alice@example.com",
        "status": "normal",
        "created_at": "2026-06-16 10:00:00",
        "mail_id": "mail-2",
        "is_spam": 0,
    }
    values, tags = mailbox_display_row(row, FOLDER_INBOX)
    assert values[0] == "Project Update"
    assert tags == ()
