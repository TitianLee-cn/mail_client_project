"""High-level email persistence across SQLite metadata and .eml files."""

import uuid
from pathlib import Path

from mailapp.common.constants import (
    FOLDER_INBOX,
    FOLDER_RECALLED,
    FOLDER_SENT,
    FOLDER_SPAM,
    STATUS_DELETED,
    STATUS_NORMAL,
    STATUS_RECALLED,
)
from mailapp.common.exceptions import MailNotFoundError
from mailapp.mime.mime_parser import (
    extract_headers,
    get_plain_text_for_spam_check,
    parse_eml_bytes,
)
from mailapp.spam.classifier import is_spam
from mailapp.storage.db import execute_query, fetch_all, fetch_one, get_connection
from mailapp.storage.mailbox import (
    move_email_to_folder,
    save_eml_to_folder,
)


def generate_mail_id():
    """Generate the server-side unique mail id."""
    return str(uuid.uuid4())


def _bytes(raw_message):
    return raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message


def store_incoming_email(sender, recipients, raw_message):
    """Store a received email for each recipient and return mail_id."""
    raw = _bytes(raw_message)
    message = parse_eml_bytes(raw)
    headers = extract_headers(message)
    mail_id = generate_mail_id()
    spam = is_spam(get_plain_text_for_spam_check(message))
    folder = FOLDER_SPAM if spam else FOLDER_INBOX
    first_path = None
    for recipient in recipients:
        path = save_eml_to_folder(recipient, folder, mail_id, raw)
        first_path = first_path or path
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO emails(mail_id, message_id, sender, subject, eml_path, status, is_spam)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mail_id,
                headers.get("message_id"),
                sender or headers.get("sender"),
                headers.get("subject"),
                str(first_path) if first_path else "",
                STATUS_NORMAL,
                int(spam),
            ),
        )
        for recipient in recipients:
            conn.execute(
                "INSERT INTO recipients(mail_id, recipient, folder) VALUES(?, ?, ?)",
                (mail_id, recipient, folder),
            )
        conn.commit()
    finally:
        conn.close()
    return mail_id


def store_sent_email(sender, recipients, raw_message):
    """Store a sender copy in the sent folder and metadata tables."""
    raw = _bytes(raw_message)
    message = parse_eml_bytes(raw)
    headers = extract_headers(message)
    mail_id = generate_mail_id()
    path = save_eml_to_folder(sender, FOLDER_SENT, mail_id, raw)
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO emails(mail_id, message_id, sender, subject, eml_path, status, is_spam)
            VALUES(?, ?, ?, ?, ?, ?, 0)
            """,
            (mail_id, headers.get("message_id"), sender, headers.get("subject"), str(path), STATUS_NORMAL),
        )
        for recipient in recipients:
            conn.execute(
                "INSERT INTO recipients(mail_id, recipient, folder) VALUES(?, ?, ?)",
                (mail_id, recipient, FOLDER_SENT),
            )
        conn.commit()
    finally:
        conn.close()
    return mail_id


def get_email_by_mail_id(mail_id):
    """Return email metadata by mail_id."""
    row = fetch_one("SELECT * FROM emails WHERE mail_id = ?", (mail_id,))
    if not row:
        raise MailNotFoundError(f"Email not found: {mail_id}")
    return row


def get_email_raw_content(mail_id):
    """Read raw .eml bytes for a mail_id."""
    row = get_email_by_mail_id(mail_id)
    path = Path(row["eml_path"])
    if path.exists():
        return path.read_bytes()
    rec = fetch_one(
        "SELECT recipient, folder FROM recipients WHERE mail_id = ? LIMIT 1",
        (mail_id,),
    )
    if rec:
        from mailapp.storage.mailbox import get_user_folder_path

        fallback = get_user_folder_path(rec["recipient"], rec["folder"]) / f"{mail_id}.eml"
        if fallback.exists():
            return fallback.read_bytes()
    raise MailNotFoundError(f"Email content not found: {mail_id}")

def mark_email_as_read(mail_id, username):
    """Mark a recipient copy as read."""
    execute_query(
        "UPDATE recipients SET read_status = 1 WHERE mail_id = ? AND recipient = ?",
        (mail_id, username),
    )
    
def mark_email_as_deleted(mail_id, username):
    """Mark a recipient copy deleted."""
    execute_query(
        "UPDATE recipients SET deleted = 1 WHERE mail_id = ? AND recipient = ?",
        (mail_id, username),
    )
    execute_query("UPDATE emails SET status = ? WHERE mail_id = ?", (STATUS_DELETED, mail_id))


def mark_email_as_spam(mail_id, username):
    """Move a recipient record to spam."""
    execute_query(
        "UPDATE recipients SET folder = ? WHERE mail_id = ? AND recipient = ?",
        (FOLDER_SPAM, mail_id, username),
    )
    execute_query("UPDATE emails SET is_spam = 1 WHERE mail_id = ?", (mail_id,))


def mark_email_as_recalled(mail_id):
    """Mark global email state as recalled."""
    execute_query("UPDATE emails SET status = ? WHERE mail_id = ?", (STATUS_RECALLED, mail_id))


def list_user_emails(username, folder=FOLDER_INBOX):
    """List visible emails for a user/folder."""
    return fetch_all(
        """
        SELECT e.*, r.recipient, r.folder, r.read_status, r.deleted
        FROM emails e
        JOIN recipients r ON e.mail_id = r.mail_id
        WHERE r.recipient = ? AND r.folder = ? AND r.deleted = 0
        ORDER BY e.created_at DESC
        """,
        (username, folder),
    )


def list_sent_emails(username):
    """List emails sent by a user."""
    return fetch_all(
        "SELECT * FROM emails WHERE sender = ? ORDER BY created_at DESC",
        (username,),
    )


def move_recalled_copies(mail_id):
    """Move recipient copies into recalled folder where possible."""
    rows = fetch_all("SELECT recipient, folder FROM recipients WHERE mail_id = ?", (mail_id,))
    for row in rows:
        if row["folder"] != FOLDER_RECALLED:
            move_email_to_folder(row["recipient"], mail_id, row["folder"], FOLDER_RECALLED)
    execute_query(
        "UPDATE recipients SET folder = ? WHERE mail_id = ?",
        (FOLDER_RECALLED, mail_id),
    )
