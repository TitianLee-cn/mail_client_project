"""High-level client workflows composed from lower-level modules."""

from mailapp.mime.mime_builder import build_email_with_attachments, build_text_email
from mailapp.mime.mime_parser import extract_body, extract_headers, parse_eml_bytes
from mailapp.protocols.pop3_client import fetch_all_messages
from mailapp.protocols.smtp_client import send_email
from mailapp.recall.recall_service import request_recall
from mailapp.spam.classifier import is_spam
from mailapp.storage.mail_store import (
    get_email_by_mail_id,
    get_email_raw_content,
    list_user_emails,
    mark_email_as_spam,
    mark_email_as_read,
)


def compose_email(sender, recipients, subject, body, attachments=None):
    """Build an outgoing MIME email."""
    if isinstance(recipients, str):
        recipients = [recipients]
    if attachments:
        return build_email_with_attachments(sender, recipients, subject, body, attachments)
    return build_text_email(sender, recipients, subject, body)


def send_email_workflow(sender, password, recipients, subject, body, attachments=None):
    """Send a message via SMTP and return the client-side message id."""
    if isinstance(recipients, str):
        recipients = [recipients]
    return send_email(sender, password, recipients, subject, body, attachments)


def receive_email_workflow(username, password):
    """Fetch inbox emails via POP3 and summarize them."""
    raw_messages = fetch_all_messages(username, password)
    summaries = []
    for raw in raw_messages:
        msg = parse_eml_bytes(raw)
        headers = extract_headers(msg)
        body = extract_body(msg)
        summaries.append(
            {
                "subject": headers["subject"],
                "sender": headers["sender"],
                "is_spam": is_spam(f"{headers['subject']}\n{body}"),
            }
        )
    return summaries


def display_email(mail_id, username=None):
    """Return display fields for one email, including recall notice.

    If username is provided, mark the recipient copy as read.
    """
    email = get_email_by_mail_id(mail_id)

    if email["status"] == "recalled":
        if username:
            mark_email_as_read(mail_id, username)
        return {"mail_id": mail_id, "status": "recalled", "body": "This email has been recalled."}

    msg = parse_eml_bytes(get_email_raw_content(mail_id))

    if username:
        mark_email_as_read(mail_id, username)

    return {
        "mail_id": mail_id,
        "status": email["status"],
        "headers": extract_headers(msg),
        "body": extract_body(msg),
    }


def move_spam_emails(username):
    """Re-check inbox and mark detected spam."""
    moved = []
    for row in list_user_emails(username, "inbox"):
        msg = parse_eml_bytes(get_email_raw_content(row["mail_id"]))
        if is_spam(extract_body(msg)):
            mark_email_as_spam(row["mail_id"], username)
            moved.append(row["mail_id"])
    return moved


def recall_email_workflow(username, mail_id):
    """Request recall for a message."""
    return request_recall(username, mail_id)
