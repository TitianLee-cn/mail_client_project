"""Server-side email recall service."""

from datetime import datetime

from mailapp.common.constants import STATUS_RECALLED
from mailapp.common.exceptions import RecallError
from mailapp.storage.db import execute_query, fetch_all
from mailapp.storage.mail_store import get_email_by_mail_id, mark_email_as_recalled, move_recalled_copies


def request_recall(sender, mail_id):
    """Public recall request API."""
    return recall_email(sender, mail_id)


def can_recall(sender, mail_id):
    """Return True if sender owns the message and it is not recalled."""
    email = get_email_by_mail_id(mail_id)
    return email["sender"] == sender and email["status"] != STATUS_RECALLED


def recall_email(sender, mail_id):
    """Recall an email by moving recipient copies to recalled state."""
    if not can_recall(sender, mail_id):
        raise RecallError("Only the original sender can recall a non-recalled email")
    mark_email_as_recalled(mail_id)
    move_recalled_copies(mail_id)
    execute_query(
        "INSERT INTO mail_status(mail_id, status, recalled_at, recall_reason) VALUES(?, ?, ?, ?)",
        (mail_id, STATUS_RECALLED, datetime.utcnow().isoformat(), "sender requested recall"),
    )
    return {
        "mail_id": mail_id,
        "status": STATUS_RECALLED,
        "message": notify_recipients_recalled(mail_id),
    }


def notify_recipients_recalled(mail_id):
    """Build a recall notification string for recipients."""
    rows = fetch_all("SELECT recipient FROM recipients WHERE mail_id = ?", (mail_id,))
    recipients = ", ".join(row["recipient"] for row in rows)
    return f"Mail {mail_id} has been recalled. Recipients: {recipients}"


def get_recall_status(mail_id):
    """Return current recall status row or email status."""
    email = get_email_by_mail_id(mail_id)
    row = fetch_all(
        "SELECT * FROM mail_status WHERE mail_id = ? ORDER BY id DESC LIMIT 1",
        (mail_id,),
    )
    return dict(row[0]) if row else {"mail_id": mail_id, "status": email["status"]}
