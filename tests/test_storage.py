"""Tests for SQLite and mailbox storage."""

import yaml

from mailapp.config import load_config
from mailapp.mime.mime_builder import build_text_email
from mailapp.storage.db import init_database
from mailapp.storage.mail_store import list_user_emails, store_incoming_email


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


def test_store_incoming_email(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Hello", "Normal text")
    mail_id = store_incoming_email("alice@example.com", ["bob@example.com"], msg.as_bytes())
    rows = list_user_emails("bob@example.com", "inbox")
    assert mail_id
    assert len(rows) == 1
    assert rows[0]["subject"] == "Hello"


def test_list_user_emails(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Project", "Please review")
    store_incoming_email("alice@example.com", ["bob@example.com"], msg.as_bytes())
    assert len(list_user_emails("bob@example.com", "inbox")) == 1
