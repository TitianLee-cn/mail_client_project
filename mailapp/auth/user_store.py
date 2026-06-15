"""User storage and password verification."""

import hashlib
import re

from mailapp.common.exceptions import AuthenticationError
from mailapp.storage.db import execute_query, fetch_all, fetch_one
from mailapp.storage.mailbox import ensure_user_mailbox

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username, password):
    """Create a user if it does not already exist."""
    existing = get_user(username)
    if existing:
        return dict(existing)
    execute_query(
        "INSERT INTO users(username, password_hash) VALUES(?, ?)",
        (username, _hash_password(password)),
    )
    ensure_user_mailbox(username)
    return dict(get_user(username))


def register_user(username, password):
    """Validate and create a new account, rejecting duplicate usernames."""
    username = (username or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(username):
        raise AuthenticationError("Username must be a valid email address")
    if len(password or "") < 6:
        raise AuthenticationError("Password must contain at least 6 characters")
    if get_user(username):
        raise AuthenticationError(f"Account already exists: {username}")
    return create_user(username, password)


def verify_user(username, password):
    """Return True when username/password matches."""
    user = get_user(username)
    if not user:
        return False
    return user["password_hash"] == _hash_password(password)


def get_user(username):
    """Fetch a user row by username."""
    return fetch_one("SELECT * FROM users WHERE username = ?", (username,))


def list_users():
    """Return all user rows."""
    return fetch_all("SELECT * FROM users ORDER BY username")


def ensure_default_users(users):
    """Create configured default users."""
    for user in users or []:
        create_user(user["username"], user["password"])


def require_user(username, password):
    """Raise AuthenticationError unless credentials are valid."""
    if not verify_user(username, password):
        raise AuthenticationError("Invalid username or password")
    return True
