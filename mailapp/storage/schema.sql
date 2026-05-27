CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_id TEXT NOT NULL UNIQUE,
    message_id TEXT,
    sender TEXT NOT NULL,
    subject TEXT,
    eml_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'normal',
    is_spam INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    folder TEXT NOT NULL,
    read_status INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(mail_id) REFERENCES emails(mail_id)
);

CREATE TABLE IF NOT EXISTS mail_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mail_id TEXT NOT NULL,
    status TEXT NOT NULL,
    recalled_at TEXT,
    recall_reason TEXT,
    FOREIGN KEY(mail_id) REFERENCES emails(mail_id)
);
