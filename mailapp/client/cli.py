"""Standalone enhanced CLI for the mail client demo."""

from getpass import getpass
from pathlib import Path

from mailapp.client.client_core import (
    display_email,
    list_recallable_sent_emails,
    receive_email_workflow,
    recall_email_workflow,
    send_email_workflow,
)
from mailapp.common.constants import FOLDER_INBOX, FOLDER_SPAM
from mailapp.common.exceptions import AuthenticationError, MailNotFoundError, RecallError
from mailapp.config import load_config
from mailapp.protocols.pop3_client import describe_security as describe_pop3_security
from mailapp.protocols.smtp_client import describe_security as describe_smtp_security
from mailapp.storage.db import init_database
from mailapp.storage.mail_store import list_user_emails


def show_menu():
    """Print CLI menu."""
    print("\n1. Send Email")
    print("2. Receive Email via POP3")
    print("3. List Inbox")
    print("4. List Spam")
    print("5. Read Email")
    print("6. Recall Email")
    print("7. Show TLS Settings")
    print("8. List Recallable Sent Mail")
    print("0. Exit")


def _credentials():
    username = input("Username: ").strip()
    password = getpass("Password: ")
    return username, password


def _yes_no(prompt, default=False):
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _multiline_body():
    print("Body. End with a single dot on its own line:")
    lines = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def _attachment_paths():
    raw = input("Attachment paths comma-separated, empty for none: ").strip()
    paths = [x.strip().strip('"') for x in raw.split(",") if x.strip()]
    missing = [path for path in paths if not Path(path).expanduser().is_file()]
    if missing:
        raise FileNotFoundError("Missing attachment(s): " + ", ".join(missing))
    return paths


def _friendly_error(exc):
    """Convert common demo failures into concise user-facing messages."""
    if isinstance(exc, AuthenticationError):
        return f"Authentication failed: {exc}"
    if isinstance(exc, FileNotFoundError):
        return f"File not found: {exc}"
    if isinstance(exc, ConnectionError):
        return f"Connection problem: {exc}. Check that run_server.py is running and TLS settings match the server."
    if isinstance(exc, MailNotFoundError):
        return f"Mail not found: {exc}. Use List Inbox/Spam or List Recallable Sent Mail to copy a valid server mail_id."
    if isinstance(exc, RecallError):
        return f"Recall failed: {exc}. Only the original sender can recall a non-recalled message."
    return f"{exc.__class__.__name__}: {exc}"


def handle_send_email():
    sender, password = _credentials()
    recipients = [x.strip() for x in input("Recipients comma-separated: ").split(",") if x.strip()]
    if not recipients:
        print("At least one recipient is required.")
        return

    subject = input("Subject: ")
    html = _yes_no("Send as HTML", default=False)
    body = _multiline_body()
    attachments = _attachment_paths()
    receipt = send_email_workflow(sender, password, recipients, subject, body, attachments=attachments, html=html)
    print("Sent.")
    print(f"  client MIME id : {receipt['client_mail_id']}")
    print(f"  Message-ID     : {receipt['message_id']}")
    print(f"  server mail_id : {receipt['server_mail_id'] or '(not found yet)'}")
    if receipt["recall_mail_id"]:
        print(f"  recall with    : {receipt['recall_mail_id']}")
    print(f"  note           : {receipt['server_id_note']}")


def handle_receive_email():
    username, password = _credentials()
    summaries = receive_email_workflow(username, password, save_local=True)
    if not summaries:
        print("No POP3 messages.")
        return

    for item in summaries:
        label = "[SPAM]" if item["is_spam"] else "[HAM]"
        print(f"{item['index']:03d} {label} {item['sender']} - {item['subject']}")
        print(f"    body: {item['body_type']} | attachments: {item['attachment_count']}")
        if item["saved_path"]:
            print(f"    saved eml: {item['saved_path']}")
        if item["html_path"]:
            print(f"    saved html: {item['html_path']}")
        if item["body_preview"]:
            print(f"    preview: {item['body_preview']}")
        for attachment in item["attachments"]:
            print(f"    saved attachment: {attachment}")


def _list_folder(folder):
    username = input("Username: ").strip()
    rows = list_user_emails(username, folder)
    if not rows:
        print(f"No messages in {folder}.")
        return
    for index, row in enumerate(rows, start=1):
        status = "RECALLED" if row["status"] == "recalled" else folder.upper()
        print(f"{index:03d} | {row['mail_id']} | {status} | {row['sender']} | {row['subject']}")


def handle_list_inbox():
    _list_folder(FOLDER_INBOX)


def handle_list_spam():
    _list_folder(FOLDER_SPAM)


def handle_read_email():
    username = input("Username: ").strip()
    mail_ref = input("mail_id or inbox number: ").strip()
    mail_id = _resolve_mail_reference(username, mail_ref)
    data = display_email(mail_id, username, save_attachments=True)
    print(f"mail_id: {data['mail_id']}")
    print(f"status: {data['status']}")
    print(f"body_type: {data['body_type']}")

    headers = data.get("headers") or {}
    if headers:
        print(f"from: {headers.get('sender', '')}")
        print(f"to: {', '.join(headers.get('recipients', []))}")
        print(f"subject: {headers.get('subject', '')}")
        print(f"date: {headers.get('date', '')}")

    if data.get("html_path"):
        print(f"html file: {data['html_path']}")

    print("\nHTML Body:" if data["body_type"] == "html" else "\nBody:")
    print(data["body"])

    attachments = data.get("attachments") or []
    if attachments:
        print("\nAttachments saved:")
        for path in attachments:
            print(path)


def _resolve_mail_reference(username, mail_ref):
    """Resolve a server mail_id or a 1-based inbox number such as 01/001."""
    if not mail_ref:
        raise ValueError("Please enter a mail_id or inbox number.")
    if not mail_ref.isdigit():
        return mail_ref

    index = int(mail_ref)
    if index <= 0:
        raise ValueError("Inbox number starts from 1.")

    rows = list_user_emails(username, FOLDER_INBOX)
    if index > len(rows):
        raise ValueError(f"Inbox number {mail_ref} is out of range. Current inbox has {len(rows)} message(s).")
    return rows[index - 1]["mail_id"]


def handle_recall_email():
    username = input("Sender username: ").strip()
    mail_id = input("server mail_id to recall: ").strip()
    result = recall_email_workflow(username, mail_id)
    print(result)


def handle_show_tls_settings():
    for item in (describe_smtp_security(), describe_pop3_security()):
        print(
            f"{item['protocol']} {item['host']}:{item['port']} | "
            f"security={item['security']} | "
            f"verify_certificate={item['verify_certificate']} | "
            f"cafile={item['cafile'] or '(system trust store)'}"
        )


def handle_list_recallable_sent_mail():
    username = input("Sender username: ").strip()
    rows = list_recallable_sent_emails(username)
    if not rows:
        print("No sent mail found for this sender.")
        return
    print("Use the mail_id below when choosing Recall Email:")
    for row in rows:
        print(
            f"{row['mail_id']} | status={row['status']} | "
            f"spam={row['is_spam']} | {row['created_at']} | {row['subject']}"
        )


def handle_exit():
    print("Bye.")
    return False


def run_cli():
    """Run the enhanced interactive CLI."""
    load_config()
    init_database()
    handlers = {
        "1": handle_send_email,
        "2": handle_receive_email,
        "3": handle_list_inbox,
        "4": handle_list_spam,
        "5": handle_read_email,
        "6": handle_recall_email,
        "7": handle_show_tls_settings,
        "8": handle_list_recallable_sent_mail,
        "0": handle_exit,
    }
    running = True
    while running:
        show_menu()
        choice = input("Choice: ").strip()
        handler = handlers.get(choice)
        if not handler:
            print("Invalid choice")
            continue
        try:
            result = handler()
        except Exception as exc:
            print(f"Error: {_friendly_error(exc)}")
            continue
        if result is False:
            running = False
