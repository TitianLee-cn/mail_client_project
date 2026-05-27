"""POP3 client helpers using poplib."""

import poplib

from mailapp.config import get_config


def connect_pop3_server(username, password):
    """Connect and authenticate to the configured POP3 server."""
    config = get_config()
    client = poplib.POP3(config.get("pop3_host", "127.0.0.1"), config.get("pop3_port", 1110), timeout=10)
    client.user(username)
    client.pass_(password)
    return client


def list_messages(username, password):
    """Return POP3 LIST output."""
    client = connect_pop3_server(username, password)
    try:
        return client.list()
    finally:
        client.quit()


def retrieve_message(username, password, message_index):
    """Retrieve one message as raw bytes."""
    client = connect_pop3_server(username, password)
    try:
        _resp, lines, _octets = client.retr(message_index)
        return b"\n".join(lines)
    finally:
        client.quit()


def delete_message(username, password, message_index):
    """Mark a message deleted on the POP3 server."""
    client = connect_pop3_server(username, password)
    try:
        return client.dele(message_index)
    finally:
        client.quit()


def fetch_all_messages(username, password):
    """Fetch all current inbox messages as raw email bytes."""
    client = connect_pop3_server(username, password)
    try:
        count, _size = client.stat()
        messages = []
        for index in range(1, count + 1):
            _resp, lines, _octets = client.retr(index)
            messages.append(b"\n".join(lines))
        return messages
    finally:
        client.quit()
