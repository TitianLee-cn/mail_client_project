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
    """Open a SQLite connection using config.yaml."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
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
