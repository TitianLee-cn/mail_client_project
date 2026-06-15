"""Tests for account registration validation."""

import pytest
import yaml

from mailapp.auth.user_store import register_user, verify_user
from mailapp.common.exceptions import AuthenticationError
from mailapp.config import load_config
from mailapp.storage.db import init_database


def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "database_path": "data/email.db",
                "mailbox_root": "data/mailboxes",
            }
        ),
        encoding="utf-8",
    )
    load_config()
    init_database()


def test_register_user_can_login(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    register_user("newuser@example.com", "secret123")
    assert verify_user("newuser@example.com", "secret123")


def test_registration_rejects_invalid_duplicate_and_short_password(
    tmp_path, monkeypatch
):
    _setup(tmp_path, monkeypatch)
    with pytest.raises(AuthenticationError, match="valid email"):
        register_user("not-an-email", "secret123")
    with pytest.raises(AuthenticationError, match="at least 6"):
        register_user("newuser@example.com", "123")
    register_user("newuser@example.com", "secret123")
    with pytest.raises(AuthenticationError, match="already exists"):
        register_user("newuser@example.com", "another123")
