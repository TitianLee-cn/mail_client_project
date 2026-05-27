"""Simple command line interface for demonstrating the mail pipeline."""

from getpass import getpass

from mailapp.client.client_core import display_email, receive_email_workflow, recall_email_workflow, send_email_workflow
from mailapp.common.constants import FOLDER_INBOX, FOLDER_SPAM
from mailapp.config import load_config
from mailapp.storage.db import init_database
from mailapp.storage.mail_store import list_user_emails


def show_menu():
    """Print CLI menu."""
    print("\n1. Send Email")
    print("2. Receive Email")
    print("3. List Inbox")
    print("4. List Spam")
    print("5. Read Email")
    print("6. Recall Email")
    print("0. Exit")


def _credentials():
    username = input("Username: ").strip()
    password = getpass("Password: ")
    return username, password


def handle_send_email():
    sender, password = _credentials()
    recipients = [x.strip() for x in input("Recipients comma-separated: ").split(",") if x.strip()]
    subject = input("Subject: ")
    body = input("Body: ")
    mail_id = send_email_workflow(sender, password, recipients, subject, body)
    print(f"Sent. Client message id: {mail_id}")


def handle_receive_email():
    username, password = _credentials()
    for item in receive_email_workflow(username, password):
        label = "[SPAM]" if item["is_spam"] else "[HAM]"
        print(f"{label} {item['sender']} - {item['subject']}")


def _list_folder(folder):
    username = input("Username: ").strip()
    for row in list_user_emails(username, folder):
        status = "RECALLED" if row["status"] == "recalled" else folder.upper()
        print(f"{row['mail_id']} | {status} | {row['sender']} | {row['subject']}")


def handle_list_inbox():
    _list_folder(FOLDER_INBOX)


def handle_list_spam():
    _list_folder(FOLDER_SPAM)


def handle_read_email():
    mail_id = input("mail_id: ").strip()
    data = display_email(mail_id)
    print(data)


def handle_recall_email():
    username = input("Sender username: ").strip()
    mail_id = input("mail_id: ").strip()
    print(recall_email_workflow(username, mail_id))


def handle_exit():
    print("Bye.")
    return False


def run_cli():
    """Run interactive CLI."""
    load_config()
    init_database()
    handlers = {
        "1": handle_send_email,
        "2": handle_receive_email,
        "3": handle_list_inbox,
        "4": handle_list_spam,
        "5": handle_read_email,
        "6": handle_recall_email,
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
        result = handler()
        if result is False:
            running = False
