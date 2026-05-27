"""Filesystem mailbox management for saved .eml files."""

import shutil
from pathlib import Path

from mailapp.common.constants import FOLDER_INBOX, FOLDER_RECALLED, FOLDER_SENT, FOLDER_SPAM
from mailapp.config import get_config


def _root():
    root = Path(get_config().get("mailbox_root", "data/mailboxes"))
    if not root.is_absolute():
        root = Path.cwd() / root
    return root


def _safe_user_dir(username):
    return username.replace("@", "_at_").replace("/", "_")


def ensure_user_mailbox(username):
    """Ensure inbox/spam/sent/recalled folders exist for a user."""
    for folder in (FOLDER_INBOX, FOLDER_SPAM, FOLDER_SENT, FOLDER_RECALLED):
        get_user_folder_path(username, folder).mkdir(parents=True, exist_ok=True)


def get_user_folder_path(username, folder):
    """Return a user's folder path."""
    return _root() / _safe_user_dir(username) / folder


def save_eml_to_folder(username, folder, mail_id, raw_message):
    """Save raw email content as mail_id.eml."""
    ensure_user_mailbox(username)
    path = get_user_folder_path(username, folder) / f"{mail_id}.eml"
    data = raw_message.encode("utf-8") if isinstance(raw_message, str) else raw_message
    path.write_bytes(data)
    return path


def move_email_to_folder(username, mail_id, source_folder, target_folder):
    """Move a saved .eml between folders if it exists."""
    ensure_user_mailbox(username)
    src = get_user_folder_path(username, source_folder) / f"{mail_id}.eml"
    dst = get_user_folder_path(username, target_folder) / f"{mail_id}.eml"
    if src.exists():
        shutil.move(str(src), str(dst))
        return dst
    return None


def delete_email_file(username, folder, mail_id):
    """Delete a saved .eml file."""
    path = get_user_folder_path(username, folder) / f"{mail_id}.eml"
    if path.exists():
        path.unlink()
        return True
    return False


def list_eml_files(username, folder):
    """List saved .eml files for a folder."""
    path = get_user_folder_path(username, folder)
    if not path.exists():
        return []
    return sorted(path.glob("*.eml"))
