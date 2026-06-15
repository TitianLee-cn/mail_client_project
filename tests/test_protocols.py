"""Socket-level SMTP/POP3 interoperability and RFC behavior tests."""

import poplib
import smtplib
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

from mailapp.auth.user_store import create_user
from mailapp.client.client_core import receive_email_workflow
from mailapp.config import load_config
from mailapp.mime.mime_builder import build_text_email
from mailapp.protocols.pop3_server import start_pop3_server, stop_pop3_server
from mailapp.protocols.smtp_server import start_smtp_server, stop_smtp_server
from mailapp.protocols.ssl_utils import create_server_ssl_context
from mailapp.storage.db import init_database
from mailapp.storage.mail_store import list_user_emails, store_incoming_email

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CERTFILE = PROJECT_ROOT / "certs" / "mailapp-cert.pem"
KEYFILE = PROJECT_ROOT / "certs" / "mailapp-key.pem"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "database_path": "data/email.db",
        "mailbox_root": "data/mailboxes",
        "spam_model_path": "data/models/spam_model.joblib",
        "smtp_auth_required": True,
        "smtp_auth_require_tls": True,
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    load_config()
    init_database()
    create_user("alice@example.com", "alice123")
    create_user("bob@example.com", "bob123")


def test_pop3_transaction_state_dot_stuffing_and_delete_commit(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email(
        "alice@example.com",
        ["bob@example.com"],
        "Dots",
        "first\r\n.dot-prefixed\r\nlast",
    )
    store_incoming_email("alice@example.com", ["bob@example.com"], msg.as_bytes())
    server = start_pop3_server(
        "127.0.0.1", 0, require_tls_for_auth=False
    )
    port = server.server_address[1]
    try:
        unauthenticated = poplib.POP3("127.0.0.1", port, timeout=5)
        with pytest.raises(poplib.error_proto):
            unauthenticated.stat()
        unauthenticated.quit()

        client = poplib.POP3("127.0.0.1", port, timeout=5)
        client.user("bob@example.com")
        client.pass_("bob123")
        assert client.stat()[0] == 1
        _response, lines, _octets = client.retr(1)
        assert b".dot-prefixed" in lines
        client.dele(1)
        client.rset()
        assert client.stat()[0] == 1
        client.dele(1)
        client.close()

        client = poplib.POP3("127.0.0.1", port, timeout=5)
        client.user("bob@example.com")
        client.pass_("bob123")
        assert client.stat()[0] == 1
        client.dele(1)
        client.quit()
        assert list_user_emails("bob@example.com", "inbox") == []
    finally:
        stop_pop3_server(server)


def test_pop3_stls_login(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    context = create_server_ssl_context(CERTFILE, KEYFILE)
    server = start_pop3_server(
        "127.0.0.1",
        0,
        ssl_context=context,
        require_tls_for_auth=True,
    )
    try:
        client = poplib.POP3("127.0.0.1", server.server_address[1], timeout=5)
        with pytest.raises(poplib.error_proto):
            client.user("bob@example.com")
            client.pass_("bob123")
        client.stls(context=ssl.create_default_context(cafile=CERTFILE))
        client.user("bob@example.com")
        client.pass_("bob123")
        client.quit()
    finally:
        stop_pop3_server(server)


def test_smtp_starttls_auth_and_ten_concurrent_clients(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    port = _free_port()
    context = create_server_ssl_context(CERTFILE, KEYFILE)
    controller = start_smtp_server(
        "127.0.0.1",
        port,
        tls_context=context,
        auth_required=True,
        auth_require_tls=True,
        require_starttls=True,
    )

    def send_one(index):
        msg = build_text_email(
            "alice@example.com",
            ["bob@example.com"],
            f"Concurrent {index}",
            "body",
        )
        with smtplib.SMTP("127.0.0.1", port, timeout=10) as client:
            client.starttls(context=ssl.create_default_context(cafile=CERTFILE))
            client.login("alice@example.com", "alice123")
            client.send_message(msg)

    try:
        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(send_one, range(10)))
        assert len(list_user_emails("bob@example.com", "inbox")) == 10
    finally:
        stop_smtp_server(controller)


def test_pop3_receive_classifies_and_moves_spam(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    msg = build_text_email(
        "alice@example.com",
        ["bob@example.com"],
        "Win Lottery Now",
        "Claim free money and prize",
    )
    mail_id = store_incoming_email(
        "alice@example.com", ["bob@example.com"], msg.as_bytes()
    )
    server = start_pop3_server(
        "127.0.0.1", 0, require_tls_for_auth=False
    )
    config = {
        "database_path": "data/email.db",
        "mailbox_root": "data/mailboxes",
        "client_download_root": "data/client_downloads",
        "spam_model_path": "data/models/missing.joblib",
        "pop3_host": "127.0.0.1",
        "pop3_port": server.server_address[1],
        "pop3_security": "plain",
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    load_config()
    try:
        rows = receive_email_workflow("bob@example.com", "bob123")
        target = next(row for row in rows if row["mail_id"] == mail_id)
        assert target["is_spam"]
        assert Path(target["saved_path"]).parent.name == "spam"
        assert any(
            row["mail_id"] == mail_id
            for row in list_user_emails("bob@example.com", "spam")
        )
    finally:
        stop_pop3_server(server)
