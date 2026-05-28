"""SQLite connection and query helpers."""

import sqlite3
from pathlib import Path

from mailapp.config import get_config


def _db_path():
    path = Path(get_config().get("database_path", "data/email.db"))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_connection():
    """Open a SQLite connection using config.yaml.

    The server may receive multiple SMTP/POP3 requests at the same time.
    Therefore, a longer SQLite timeout and WAL mode are enabled to make
    concurrent read/write operations more stable.
    """
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")

    return conn


def init_database():
    """Create database tables from schema.sql."""
    schema_path = Path(__file__).with_name("schema.sql")
    conn = get_connection()
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def execute_query(sql, params=None):
    """Execute a write query and return the cursor."""
    conn = get_connection()
    try:
        cur = conn.execute(sql, params or ())
        conn.commit()
        return cur
    finally:
        conn.close()


def fetch_one(sql, params=None):
    """Fetch one row."""
    conn = get_connection()
    try:
        return conn.execute(sql, params or ()).fetchone()
    finally:
        conn.close()


def fetch_all(sql, params=None):
    """Fetch all rows."""
    conn = get_connection()
    try:
        return conn.execute(sql, params or ()).fetchall()
    finally:
        conn.close()


def close_connection(conn):
    """Close a SQLite connection."""
    if conn:
        conn.close()
