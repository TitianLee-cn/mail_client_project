"""Enhanced SMTP client with HTML, attachments, and TLS options."""

import mimetypes
import smtplib
import ssl
import time
from pathlib import Path

from mailapp.common.exceptions import AuthenticationError
from mailapp.config import get_config
from mailapp.mime.mime_builder import build_html_email, build_text_email
from mailapp.protocols.ssl_utils import create_client_ssl_context
from mailapp.storage.db import fetch_one

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
        raise ValueError("SMTP cannot use implicit SSL and STARTTLS at the same time.")
    if use_ssl is not None:
        return SECURITY_SSL if use_ssl else (SECURITY_STARTTLS if starttls else SECURITY_PLAIN)
    if starttls is not None:
        return SECURITY_STARTTLS if starttls else (SECURITY_SSL if _bool_config(config, "smtp_use_ssl") else SECURITY_PLAIN)

    raw_mode = str(config.get("smtp_security", "")).strip().lower()
    if raw_mode:
        aliases = {
            "none": SECURITY_PLAIN,
            "tls": SECURITY_STARTTLS,
            "ssl_tls": SECURITY_SSL,
        }
        mode = aliases.get(raw_mode, raw_mode)
        if mode not in VALID_SECURITY_MODES:
            raise ValueError(f"Unsupported smtp_security mode: {raw_mode}")
        return mode
    if _bool_config(config, "smtp_use_ssl"):
        return SECURITY_SSL
    if bool(config.get("smtp_starttls", False)):
        return SECURITY_STARTTLS
    return SECURITY_PLAIN


def _client_ssl_context(config):
    cafile = config.get("ssl_cafile") or config.get("smtp_ssl_cafile")
    verify = bool(config.get("smtp_ssl_verify", config.get("ssl_verify", True)))
    return create_client_ssl_context(cafile=cafile, verify=verify)


def describe_security():
    """Return effective SMTP TLS settings for display/debugging."""
    config = get_config()
    return {
        "protocol": "SMTP",
        "host": config.get("smtp_host", "127.0.0.1"),
        "port": config.get("smtp_port", 2525),
        "security": _security_mode(config),
        "verify_certificate": bool(config.get("smtp_ssl_verify", config.get("ssl_verify", True))),
        "cafile": config.get("ssl_cafile") or config.get("smtp_ssl_cafile") or "",
    }


def connect_smtp_server(host=None, port=None, use_ssl=None, starttls=None):
    """Connect to the configured SMTP server and apply SSL/TLS if requested."""
    config = get_config()
    host = host or config.get("smtp_host", "127.0.0.1")
    port = port or config.get("smtp_port", 2525)
    mode = _security_mode(config, use_ssl=use_ssl, starttls=starttls)
    context = _client_ssl_context(config)

    try:
        if mode == SECURITY_SSL:
            return smtplib.SMTP_SSL(host, port, timeout=10, context=context)

        server = smtplib.SMTP(host, port, timeout=10)
        if mode == SECURITY_STARTTLS:
            server.ehlo_or_helo_if_needed()
            server.starttls(context=context)
            server.ehlo()
        return server
    except ssl.SSLError as exc:
        raise ConnectionError(f"SMTP TLS handshake failed for {host}:{port}: {exc}") from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise ConnectionError(f"SMTP connection failed for {host}:{port} using {mode}: {exc}") from exc


def login_smtp(server, username, password):
    """Perform SMTP AUTH when the server advertises it."""
    server.ehlo_or_helo_if_needed()
    if not server.has_extn("auth"):
        if get_config().get("smtp_auth_required", True):
            raise AuthenticationError("SMTP server does not advertise AUTH")
        return False
    try:
        server.login(username, password)
    except smtplib.SMTPAuthenticationError as exc:
        error = exc.smtp_error.decode(errors="replace") if isinstance(exc.smtp_error, bytes) else str(exc.smtp_error)
        raise AuthenticationError(f"SMTP AUTH rejected: {error}") from exc
    return True


def _add_attachments(msg, attachment_paths):
    for attachment_path in attachment_paths or []:
        path = Path(attachment_path).expanduser()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Attachment not found: {path}")

        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(
            path.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return msg


def build_outgoing_email(sender, recipients, subject, body, attachments=None, html=False):
    """Build an outgoing MIME message with optional HTML and attachments."""
    msg = build_html_email(sender, recipients, subject, body) if html else build_text_email(sender, recipients, subject, body)
    return _add_attachments(msg, attachments)


def send_mime_message(server, sender, recipients, mime_message):
    """Send an EmailMessage through an open SMTP connection."""
    server.send_message(mime_message, from_addr=sender, to_addrs=recipients)
    return mime_message.get("X-MailApp-Mail-ID")


def _lookup_server_mail_id(message_id, sender, attempts=10, delay=0.1):
    """Find the server-generated mail_id for a locally sent message."""
    if not message_id:
        return None
    for _attempt in range(attempts):
        row = fetch_one(
            """
            SELECT mail_id
            FROM emails
            WHERE message_id = ? AND sender = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (message_id, sender),
        )
        if row:
            return row["mail_id"]
        time.sleep(delay)
    return None


def send_email_receipt(sender, password, recipients, subject, body, attachments=None, html=False):
    """Send an email and return both client and server identifiers."""
    if isinstance(recipients, str):
        recipients = [recipients]
    msg = build_outgoing_email(sender, recipients, subject, body, attachments=attachments, html=html)
    client_mail_id = msg.get("X-MailApp-Mail-ID")
    message_id = msg.get("Message-ID")
    server = connect_smtp_server()
    try:
        login_smtp(server, sender, password)
        send_mime_message(server, sender, recipients, msg)
    finally:
        try:
            server.quit()
        except (OSError, smtplib.SMTPException):
            server.close()

    server_mail_id = _lookup_server_mail_id(message_id, sender)
    return {
        "client_mail_id": client_mail_id,
        "message_id": message_id,
        "server_mail_id": server_mail_id or "",
        "recall_mail_id": server_mail_id or "",
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "body_type": "html" if html else "plain",
        "attachment_count": len(attachments or []),
        "server_id_found": bool(server_mail_id),
        "server_id_note": (
            "Use server_mail_id for recall."
            if server_mail_id
            else "Server mail_id was not found. Use List Recallable Sent Mail after the server stores the message."
        ),
    }


def send_email(sender, password, recipients, subject, body, attachments=None, html=False):
    """High-level send helper for the enhanced CLI."""
    return send_email_receipt(sender, password, recipients, subject, body, attachments, html)["client_mail_id"]
