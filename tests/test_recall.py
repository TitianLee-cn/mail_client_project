"""Tests for email recall service."""

import pytest
import yaml

from mailapp.common.exceptions import RecallError
from mailapp.config import load_config
from mailapp.mime.mime_builder import build_text_email
from mailapp.recall.recall_service import request_recall
from mailapp.storage.db import init_database
from mailapp.storage.mail_store import get_email_by_mail_id, list_user_emails, store_incoming_email


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


def test_sender_can_recall_own_email(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Recall me", "Body")
    mail_id = store_incoming_email("alice@example.com", ["bob@example.com"], msg.as_bytes())
    result = request_recall("alice@example.com", mail_id)
    assert result["status"] == "recalled"
    assert get_email_by_mail_id(mail_id)["status"] == "recalled"
    assert list_user_emails("bob@example.com", "inbox") == []


def test_other_user_cannot_recall_email(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email("alice@example.com", ["bob@example.com"], "No", "Body")
    mail_id = store_incoming_email("alice@example.com", ["bob@example.com"], msg.as_bytes())
    with pytest.raises(RecallError):
        request_recall("bob@example.com", mail_id)
