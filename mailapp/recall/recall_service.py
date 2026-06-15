"""Authenticated and transactional server-side email recall."""

from datetime import datetime, timezone

from mailapp.auth.user_store import require_user
from mailapp.common.constants import FOLDER_RECALLED, STATUS_RECALLED
from mailapp.common.exceptions import MailNotFoundError, RecallError
from mailapp.storage.db import execute_transaction, fetch_all
from mailapp.storage.mailbox import move_email_to_folder
from mailapp.storage.mail_store import get_email_by_mail_id


def request_recall(sender, password, mail_id):
    """Authenticate the sender and recall a server-generated mail_id."""
    require_user(sender, password)
    return recall_email(sender, mail_id)


def can_recall(sender, mail_id):
    """Return True if sender owns the message and it is not recalled."""
    email = get_email_by_mail_id(mail_id)
    return email["sender"] == sender and email["status"] != STATUS_RECALLED


def recall_email(sender, mail_id):
    """Atomically update recall metadata and move all recipient copies."""
    moved = []
    recipients = []

    def apply_recall(conn):
        row = conn.execute(
            "SELECT sender, status FROM emails WHERE mail_id = ?", (mail_id,)
        ).fetchone()
        if not row:
            raise MailNotFoundError(f"Email not found: {mail_id}")
        if row["sender"] != sender:
            raise RecallError("Only the original sender can recall this email")
        if row["status"] == STATUS_RECALLED:
            raise RecallError("Email has already been recalled")

        recipient_rows = conn.execute(
            "SELECT recipient, folder FROM recipients WHERE mail_id = ?",
            (mail_id,),
        ).fetchall()
        for recipient_row in recipient_rows:
            recipient = recipient_row["recipient"]
            source_folder = recipient_row["folder"]
            recipients.append(recipient)
            if source_folder == FOLDER_RECALLED:
                continue
            destination = move_email_to_folder(
                recipient, mail_id, source_folder, FOLDER_RECALLED
            )
            if destination is not None:
                moved.append((recipient, source_folder))

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE emails SET status = ? WHERE mail_id = ?",
            (STATUS_RECALLED, mail_id),
        )
        conn.execute(
            "UPDATE recipients SET folder = ? WHERE mail_id = ?",
            (FOLDER_RECALLED, mail_id),
        )
        conn.execute(
            """
            INSERT INTO mail_status(mail_id, status, recalled_at, recall_reason)
            VALUES(?, ?, ?, ?)
            """,
            (mail_id, STATUS_RECALLED, now, "sender requested recall"),
        )
        notification = f"Mail {mail_id} was recalled by {sender} at {now}."
        conn.executemany(
            """
            INSERT INTO recall_notifications(mail_id, recipient, message)
            VALUES(?, ?, ?)
            """,
            [(mail_id, recipient, notification) for recipient in recipients],
        )

    try:
        execute_transaction(apply_recall)
    except Exception:
        for recipient, source_folder in reversed(moved):
            move_email_to_folder(
                recipient, mail_id, FOLDER_RECALLED, source_folder
            )
        raise

    return {
        "mail_id": mail_id,
        "status": STATUS_RECALLED,
        "message": notify_recipients_recalled(mail_id),
    }


def notify_recipients_recalled(mail_id):
    """Return the persisted recall notification summary."""
    rows = fetch_all(
        """
        SELECT recipient, message
        FROM recall_notifications
        WHERE mail_id = ?
        ORDER BY id
        """,
        (mail_id,),
    )
    if not rows:
        return f"Mail {mail_id} was recalled."
    recipients = ", ".join(row["recipient"] for row in rows)
    return f"Mail {mail_id} was recalled. Recipients notified: {recipients}"


def list_recall_notifications(username):
    """List persisted recall notifications for a recipient."""
    return fetch_all(
        """
        SELECT * FROM recall_notifications
        WHERE recipient = ?
        ORDER BY created_at DESC, id DESC
        """,
        (username,),
    )


def get_recall_status(mail_id):
    """Return current recall status row or email status."""
    email = get_email_by_mail_id(mail_id)
    rows = fetch_all(
        "SELECT * FROM mail_status WHERE mail_id = ? ORDER BY id DESC LIMIT 1",
        (mail_id,),
    )
    return dict(rows[0]) if rows else {"mail_id": mail_id, "status": email["status"]}
