"""High-level email persistence across SQLite metadata and .eml files."""

import uuid
from pathlib import Path

from mailapp.common.constants import (
    FOLDER_INBOX,
    FOLDER_RECALLED,
    FOLDER_SENT,
    FOLDER_SPAM,
    STATUS_NORMAL,
    STATUS_RECALLED,
)
from mailapp.common.exceptions import MailNotFoundError
from mailapp.mime.mime_parser import extract_headers, parse_eml_bytes
from mailapp.storage.db import (
    execute_query,
    execute_transaction,
    fetch_all,
    fetch_one,
    get_connection,
)
from mailapp.storage.mailbox import (
    copy_email_to_folder,
    move_email_to_folder,
    save_eml_to_folder,
)


def generate_mail_id():
    """Generate the server-side unique mail id."""
    return str(uuid.uuid4())


def _bytes(raw_message):
    return raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message


def store_incoming_email(sender, recipients, raw_message):
    """Store a received email and return the server-generated mail_id.

    Every message initially remains POP3-visible in inbox. The client performs
    the required real-time spam classification after retrieval and then moves
    spam copies to the spam folder.
    """
    raw = _bytes(raw_message)
    message = parse_eml_bytes(raw)
    headers = extract_headers(message)
    mail_id = generate_mail_id()
    folder = FOLDER_INBOX
    first_path = None
    saved_paths = []
    recipients = list(dict.fromkeys(recipients))
    for recipient in recipients:
        path = save_eml_to_folder(recipient, folder, mail_id, raw)
        saved_paths.append(path)
        first_path = first_path or path
    if sender:
        saved_paths.append(copy_email_to_folder(sender, FOLDER_SENT, mail_id, raw))

    def insert_metadata(conn):
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
                0,
            ),
        )
        conn.executemany(
            "INSERT INTO recipients(mail_id, recipient, folder) VALUES(?, ?, ?)",
            [(mail_id, recipient, folder) for recipient in recipients],
        )

    try:
        execute_transaction(insert_metadata)
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise
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
    """Commit deletion of one recipient copy."""
    execute_query(
        "UPDATE recipients SET deleted = 1 WHERE mail_id = ? AND recipient = ?",
        (mail_id, username),
    )


def mark_emails_as_deleted(mail_ids, username, conn=None):
    """Commit a POP3 session's pending deletions in one transaction."""
    if not mail_ids:
        return
    sql = "UPDATE recipients SET deleted = 1 WHERE mail_id = ? AND recipient = ?"
    if conn is not None:
        conn.executemany(sql, [(mail_id, username) for mail_id in mail_ids])
        return
    connection = get_connection()
    try:
        connection.executemany(sql, [(mail_id, username) for mail_id in mail_ids])
        connection.commit()
    finally:
        connection.close()


def mark_email_as_spam(mail_id, username):
    """Move a recipient copy from inbox to spam on disk and in SQLite."""
    row = fetch_one(
        "SELECT folder FROM recipients WHERE mail_id = ? AND recipient = ? AND deleted = 0",
        (mail_id, username),
    )
    if not row:
        raise MailNotFoundError(f"Email is not visible to {username}: {mail_id}")
    source_folder = row["folder"]
    moved = None
    if source_folder != FOLDER_SPAM:
        moved = move_email_to_folder(
            username, mail_id, source_folder, FOLDER_SPAM
        )

    def update_spam_state(conn):
        conn.execute(
            "UPDATE recipients SET folder = ? WHERE mail_id = ? AND recipient = ?",
            (FOLDER_SPAM, mail_id, username),
        )
        conn.execute(
            "UPDATE emails SET is_spam = 1 WHERE mail_id = ?", (mail_id,)
        )

    try:
        execute_transaction(update_spam_state)
    except Exception:
        if moved is not None:
            move_email_to_folder(username, mail_id, FOLDER_SPAM, source_folder)
        raise


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


def list_pop3_maildrop(username):
    """Return a stable POP3 snapshot of the user's inbox."""
    return fetch_all(
        """
        SELECT e.*, r.recipient, r.folder, r.read_status, r.deleted, r.received_at
        FROM emails e
        JOIN recipients r ON e.mail_id = r.mail_id
        WHERE r.recipient = ? AND r.folder = ? AND r.deleted = 0
          AND e.status != ?
        ORDER BY e.created_at ASC, e.id ASC
        """,
        (username, FOLDER_INBOX, STATUS_RECALLED),
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


def user_can_access_email(username, mail_id):
    """Return whether username is sender or an undeleted recipient."""
    return bool(
        fetch_one(
            """
            SELECT 1
            FROM emails e
            LEFT JOIN recipients r ON e.mail_id = r.mail_id
            WHERE e.mail_id = ?
              AND (e.sender = ? OR (r.recipient = ? AND r.deleted = 0))
            LIMIT 1
            """,
            (mail_id, username, username),
        )
    )
