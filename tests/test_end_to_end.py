"""Function-level end-to-end tests for the minimal mail pipeline."""

import yaml

from mailapp.auth.user_store import create_user
from mailapp.config import load_config
from mailapp.mime.mime_builder import build_text_email
from mailapp.protocols.smtp_server import process_incoming_message
from mailapp.recall.recall_service import request_recall
from mailapp.storage.db import init_database
from mailapp.spam.classifier import is_spam
from mailapp.storage.mail_store import (
    get_email_raw_content,
    list_user_emails,
    mark_email_as_spam,
)


def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "database_path": "data/email.db",
        "mailbox_root": "data/mailboxes",
        "spam_model_path": "data/models/spam_model.joblib",
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    load_config()
    init_database()
    create_user("alice@example.com", "alice123")
    create_user("bob@example.com", "bob123")


def test_send_receive_minimal_flow(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Hello", "Normal body")
    mail_id = process_incoming_message("alice@example.com", ["bob@example.com"], msg.as_bytes())
    rows = list_user_emails("bob@example.com", "inbox")
    assert rows[0]["mail_id"] == mail_id


def test_spam_filter_minimal_flow(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Win Lottery Now", "free prize")
    mail_id = process_incoming_message(
        "alice@example.com", ["bob@example.com"], msg.as_bytes()
    )
    assert len(list_user_emails("bob@example.com", "inbox")) == 1
    assert is_spam(get_email_raw_content(mail_id).decode(errors="replace"))
    mark_email_as_spam(mail_id, "bob@example.com")
    assert len(list_user_emails("bob@example.com", "spam")) == 1
    assert len(list_user_emails("bob@example.com", "inbox")) == 0


def test_recall_minimal_flow(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Recall", "Normal body")
    mail_id = process_incoming_message("alice@example.com", ["bob@example.com"], msg.as_bytes())
    request_recall("alice@example.com", "alice123", mail_id)
    assert len(list_user_emails("bob@example.com", "inbox")) == 0
