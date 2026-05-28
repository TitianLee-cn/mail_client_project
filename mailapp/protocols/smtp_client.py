"""SMTP client helpers using smtplib."""

import smtplib

from mailapp.common.exceptions import AuthenticationError
from mailapp.config import get_config
from mailapp.mime.mime_builder import build_email_with_attachments, build_text_email


def connect_smtp_server(host=None, port=None, use_ssl=None):
    """Connect to an SMTP server."""
    config = get_config()
    host = host or config.get("smtp_host", "127.0.0.1")
    port = port or config.get("smtp_port", 2525)
    use_ssl = config.get("use_ssl", False) if use_ssl is None else use_ssl
    if use_ssl:
        return smtplib.SMTP_SSL(host, port, timeout=10)
    return smtplib.SMTP(host, port, timeout=10)


def login_smtp(server, username, password):
    """Perform SMTP AUTH against the server.

    Raises AuthenticationError when the server advertises AUTH but the
    supplied credentials are rejected. When the server does not advertise
    AUTH (e.g. ``smtp_auth_required: false`` in config), returns False so
    callers can proceed with an unauthenticated session.
    """
    server.ehlo_or_helo_if_needed()
    if not server.has_extn("auth"):
        return False
    try:
        server.login(username, password)
    except smtplib.SMTPAuthenticationError as exc:
        raise AuthenticationError(f"SMTP AUTH rejected: {exc.smtp_error.decode(errors='replace')}") from exc
    return True


def send_mime_message(server, sender, recipients, mime_message):
    """Send an EmailMessage through an open SMTP connection."""
    server.send_message(mime_message, from_addr=sender, to_addrs=recipients)
    return mime_message.get("X-MailApp-Mail-ID")


def send_email(sender, password, recipients, subject, body, attachments=None):
    """High-level send helper for project SMTP server."""
    if isinstance(recipients, str):
        recipients = [recipients]
    msg = (
        build_email_with_attachments(sender, recipients, subject, body, attachments)
        if attachments
        else build_text_email(sender, recipients, subject, body)
    )
    server = connect_smtp_server()
    try:
        login_smtp(server, sender, password)
        return send_mime_message(server, sender, recipients, msg)
    finally:
        server.quit()
