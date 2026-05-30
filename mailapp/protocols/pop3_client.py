"""Enhanced POP3 client with SSL and STARTTLS options."""

import poplib
import ssl

from mailapp.config import get_config

SECURITY_PLAIN = "plain"
SECURITY_STARTTLS = "starttls"
SECURITY_SSL = "ssl"
VALID_SECURITY_MODES = {SECURITY_PLAIN, SECURITY_STARTTLS, SECURITY_SSL}


def _bool_config(config, specific_key, fallback_key="use_ssl", default=False):
    if specific_key in config:
        return bool(config.get(specific_key))
    return bool(config.get(fallback_key, default))


def _security_mode(config, use_ssl=None, starttls=None):
    if use_ssl is not None and starttls is not None and use_ssl and starttls:
        raise ValueError("POP3 cannot use implicit SSL and STLS at the same time.")
    if use_ssl is not None:
        return SECURITY_SSL if use_ssl else (SECURITY_STARTTLS if starttls else SECURITY_PLAIN)
    if starttls is not None:
        return SECURITY_STARTTLS if starttls else (SECURITY_SSL if _bool_config(config, "pop3_use_ssl") else SECURITY_PLAIN)

    raw_mode = str(config.get("pop3_security", "")).strip().lower()
    if raw_mode:
        aliases = {"none": SECURITY_PLAIN, "tls": SECURITY_SSL, "ssl_tls": SECURITY_SSL, "stls": SECURITY_STARTTLS}
        mode = aliases.get(raw_mode, raw_mode)
        if mode not in VALID_SECURITY_MODES:
            raise ValueError(f"Unsupported pop3_security mode: {raw_mode}")
        return mode
    if _bool_config(config, "pop3_use_ssl"):
        return SECURITY_SSL
    if bool(config.get("pop3_starttls", False)):
        return SECURITY_STARTTLS
    return SECURITY_PLAIN


def _client_ssl_context(config):
    cafile = config.get("ssl_cafile") or config.get("pop3_ssl_cafile")
    verify = bool(config.get("pop3_ssl_verify", config.get("ssl_verify", True)))
    if verify:
        return ssl.create_default_context(cafile=cafile)
    context = ssl._create_unverified_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def describe_security():
    """Return effective POP3 TLS settings for display/debugging."""
    config = get_config()
    return {
        "protocol": "POP3",
        "host": config.get("pop3_host", "127.0.0.1"),
        "port": config.get("pop3_port", 1110),
        "security": _security_mode(config),
        "verify_certificate": bool(config.get("pop3_ssl_verify", config.get("ssl_verify", True))),
        "cafile": config.get("ssl_cafile") or config.get("pop3_ssl_cafile") or "",
    }


def connect_pop3_server(username, password, use_ssl=None, starttls=None):
    """Connect and authenticate to the configured POP3 server."""
    config = get_config()
    host = config.get("pop3_host", "127.0.0.1")
    port = config.get("pop3_port", 1110)
    mode = _security_mode(config, use_ssl=use_ssl, starttls=starttls)
    context = _client_ssl_context(config)
    client = None

    try:
        if mode == SECURITY_SSL:
            client = poplib.POP3_SSL(host, port, timeout=10, context=context)
        else:
            client = poplib.POP3(host, port, timeout=10)
            if mode == SECURITY_STARTTLS:
                client.stls(context=context)

        client.user(username)
        client.pass_(password)
        return client
    except ssl.SSLError as exc:
        if client is not None:
            client.close()
        raise ConnectionError(f"POP3 TLS handshake failed for {host}:{port}: {exc}") from exc
    except (OSError, poplib.error_proto) as exc:
        if client is not None:
            client.close()
        raise ConnectionError(f"POP3 connection failed for {host}:{port} using {mode}: {exc}") from exc


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
