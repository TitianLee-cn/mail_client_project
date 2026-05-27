"""SMTP client helpers using smtplib."""

import smtplib

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
    """Try SMTP AUTH; local demo server may not support it."""
    try:
        server.login(username, password)
    except smtplib.SMTPException:
        # TODO: enable AUTH in the SMTP server for stricter demos.
        return False
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
