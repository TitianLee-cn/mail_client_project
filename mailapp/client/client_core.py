"""Enhanced client workflows for the course demo.

This module is intentionally separate from ``client_core.py`` so the original
client remains unchanged while the richer demo client can support HTML,
attachments, local .eml downloads, attachment extraction, and SSL-aware POP3.
"""

from pathlib import Path

from mailapp.config import get_config
from mailapp.mime.mime_parser import (
    extract_attachments,
    extract_headers,
    parse_eml_bytes,
)
from mailapp.auth.user_store import require_user
from mailapp.common.exceptions import AuthenticationError
from mailapp.protocols.pop3_client import fetch_all_message_records
from mailapp.protocols.smtp_client import build_outgoing_email, send_email_receipt
from mailapp.recall.recall_service import list_recall_notifications, request_recall
from mailapp.spam.classifier import is_spam
from mailapp.storage.mail_store import (
    get_email_by_mail_id,
    get_email_raw_content,
    list_sent_emails,
    list_user_emails,
    mark_email_as_spam,
    mark_email_as_read,
    user_can_access_email,
)


def _client_root():
    """Return the root directory used for client-side downloads."""
    root = Path(get_config().get("client_download_root", "data/client_downloads"))
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def _safe_user_dir(username):
    return username.replace("@", "_at_").replace("/", "_")


def _safe_name(value):
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)


def user_download_dir(username, folder="inbox"):
    """Return and create the local download folder for a user."""
    path = _client_root() / _safe_user_dir(username) / folder
    path.mkdir(parents=True, exist_ok=True)
    return path


def _body_content(message, prefer_html=False):
    """Return body text and its content type.

    The shared parser prefers text/plain, which is good for spam checks. The
    enhanced reader can prefer text/html so HTML messages show their real
    markup instead of the plain fallback text.
    """
    prefer = ("html", "plain") if prefer_html else ("plain", "html")
    part = message.get_body(preferencelist=prefer)
    if part is not None:
        body_type = "html" if part.get_content_type() == "text/html" else "plain"
        return part.get_content(), body_type
    if message.is_multipart():
        return "", "plain"
    body_type = "html" if message.get_content_type() == "text/html" else "plain"
    return message.get_content(), body_type


def _save_html_body(username, mail_id, html_body):
    path = user_download_dir(username, "html") / f"{_safe_name(mail_id)}.html"
    path.write_text(html_body or "", encoding="utf-8")
    return path


def compose_email(sender, recipients, subject, body, attachments=None, html=False):
    """Build an outgoing MIME email."""
    if isinstance(recipients, str):
        recipients = [recipients]
    return build_outgoing_email(sender, recipients, subject, body, attachments=attachments, html=html)


def send_email_workflow(sender, password, recipients, subject, body, attachments=None, html=False):
    """Send a message via SMTP and return a receipt with recall-ready ids."""
    if isinstance(recipients, str):
        recipients = [recipients]
    return send_email_receipt(sender, password, recipients, subject, body, attachments=attachments, html=html)


def list_recallable_sent_emails(username, password):
    """List sent messages with the server-generated mail_id used for recall."""
    require_user(username, password)
    rows = []
    for row in list_sent_emails(username):
        if row["status"] == "recalled":
            continue
        rows.append(
            {
                "mail_id": row["mail_id"],
                "subject": row["subject"],
                "status": row["status"],
                "created_at": row["created_at"],
                "is_spam": bool(row["is_spam"]),
                "message_id": row["message_id"],
            }
        )
    return rows


def recall_email_workflow(username, password, mail_id):
    """Recall a message by the server-generated mail_id."""
    return request_recall(username, password, mail_id)


def _save_downloaded_eml(username, raw, mail_id, spam):
    folder = "spam" if spam else "inbox"
    download_dir = user_download_dir(username, folder)
    filename = f"{mail_id}.eml"
    path = download_dir / filename
    path.write_bytes(raw)
    return path


def receive_email_workflow(username, password, save_local=True):
    """Fetch POP3 messages, classify them, and optionally save .eml locally."""
    records = fetch_all_message_records(username, password)
    summaries = []
    for record in records:
        index = record["index"]
        raw = record["raw"]
        server_mail_id = record["mail_id"]
        msg = parse_eml_bytes(raw)
        headers = extract_headers(msg)
        spam_body, _spam_body_type = _body_content(msg, prefer_html=False)
        display_body, body_type = _body_content(msg, prefer_html=True)
        spam = is_spam(f"{headers['subject']}\n{spam_body}")
        if spam:
            mark_email_as_spam(server_mail_id, username)
        saved_path = (
            _save_downloaded_eml(username, raw, server_mail_id, spam)
            if save_local
            else None
        )
        local_id = _safe_name(server_mail_id)
        attachment_paths = [str(path) for path in extract_attachments(msg, user_download_dir(username, "attachments") / local_id)]
        html_path = _save_html_body(username, local_id, display_body) if body_type == "html" else None
        summaries.append(
            {
                "index": index,
                "subject": headers["subject"],
                "sender": headers["sender"],
                "mail_id": server_mail_id,
                "client_mail_id": headers["mail_id"],
                "message_id": headers["message_id"],
                "is_spam": spam,
                "body_type": body_type,
                "body_preview": display_body[:120].replace("\n", " "),
                "attachment_count": len(attachment_paths),
                "attachments": attachment_paths,
                "saved_path": str(saved_path) if saved_path else "",
                "html_path": str(html_path) if html_path else "",
            }
        )
    return summaries


def _extract_display_attachments(message, username, mail_id):
    output_dir = user_download_dir(username, "attachments") / _safe_name(mail_id)
    return [str(path) for path in extract_attachments(message, output_dir)]


def display_email(mail_id, username, password, save_attachments=True):
    """Return readable display fields for one stored email.

    HTML bodies and attachments are extracted during POP3 receive. Reading a
    message should not create another local copy of those files.
    """
    require_user(username, password)
    if not user_can_access_email(username, mail_id):
        raise AuthenticationError("This user cannot access the requested email")
    email = get_email_by_mail_id(mail_id)
    if email["status"] == "recalled":
        mark_email_as_read(mail_id, username)
        return {
            "mail_id": mail_id,
            "status": "recalled",
            "body": "This email has been recalled.",
            "body_type": "plain",
            "attachments": [],
        }

    msg = parse_eml_bytes(get_email_raw_content(mail_id))
    mark_email_as_read(mail_id, username)

    headers = extract_headers(msg)
    body, body_type = _body_content(msg, prefer_html=True)
    return {
        "mail_id": mail_id,
        "status": email["status"],
        "headers": headers,
        "body": body,
        "body_type": body_type,
        "attachments": [],
        "html_path": "",
    }


def list_mailbox_authenticated(username, password, folder):
    """List one mailbox folder after validating credentials."""
    require_user(username, password)
    return list_user_emails(username, folder)


def list_recall_notifications_authenticated(username, password):
    """List recall notifications after validating recipient credentials."""
    require_user(username, password)
    return list_recall_notifications(username)
