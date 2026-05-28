"""Minimal POP3 server using socketserver for the course demo."""

import socketserver
from pathlib import Path

from mailapp.auth.user_store import verify_user
from mailapp.common.constants import FOLDER_INBOX
from mailapp.storage.mail_store import (
    get_email_raw_content,
    list_user_emails,
    mark_email_as_deleted,
    mark_email_as_read,
)


class POP3Handler(socketserver.StreamRequestHandler):
    """Handle a small subset of POP3 commands."""

    def handle(self):
        self.username = None
        self.authenticated = False
        self._send("+OK MailApp POP3 ready")
        while True:
            line = self.rfile.readline().decode("utf-8", errors="replace").strip()
            if not line:
                break
            parts = line.split()
            command = parts[0].upper()
            args = parts[1:]
            if command == "USER" and args:
                self.handle_USER(args[0])
            elif command == "PASS" and args:
                self.handle_PASS(args[0])
            elif command == "STAT":
                self.handle_STAT()
            elif command == "LIST":
                self.handle_LIST()
            elif command == "RETR" and args:
                self.handle_RETR(args[0])
            elif command == "DELE" and args:
                self.handle_DELE(args[0])
            elif command == "QUIT":
                self.handle_QUIT()
                break
            else:
                self._send("-ERR unsupported command")

    def _send(self, line):
        self.wfile.write((line + "\r\n").encode("utf-8"))

    def _messages(self):
        if not self.authenticated:
            return []
        return list(list_user_emails(self.username, FOLDER_INBOX))

    def handle_USER(self, username):
        self.username = username
        self._send("+OK user accepted")

    def handle_PASS(self, password):
        if self.username and verify_user(self.username, password):
            self.authenticated = True
            self._send("+OK logged in")
        else:
            self._send("-ERR authentication failed")

    def handle_STAT(self):
        messages = self._messages()
        size = sum(len(get_email_raw_content(row["mail_id"])) for row in messages)
        self._send(f"+OK {len(messages)} {size}")

    def handle_LIST(self):
        messages = self._messages()
        self._send(f"+OK {len(messages)} messages")
        for index, row in enumerate(messages, start=1):
            self._send(f"{index} {len(get_email_raw_content(row['mail_id']))}")
        self._send(".")

    def handle_RETR(self, message_index):
        messages = self._messages()
        try:
            row = messages[int(message_index) - 1]
        except (ValueError, IndexError):
            self._send("-ERR no such message")
            return

        raw = get_email_raw_content(row["mail_id"])
        self._send(f"+OK {len(raw)} octets")
        self.wfile.write(raw.replace(b"\n", b"\r\n"))
        self.wfile.write(b"\r\n.\r\n")

        mark_email_as_read(row["mail_id"], self.username)

    def handle_DELE(self, message_index):
        messages = self._messages()
        try:
            row = messages[int(message_index) - 1]
        except (ValueError, IndexError):
            self._send("-ERR no such message")
            return
        mark_email_as_deleted(row["mail_id"], self.username)
        self._send("+OK marked deleted")

    def handle_QUIT(self):
        self._send("+OK bye")


class ThreadingPOP3Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def start_pop3_server(host, port):
    """Start POP3 server in a background thread and return server."""
    server = ThreadingPOP3Server((host, port), POP3Handler)
    import threading

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.thread = thread
    return server


def stop_pop3_server(server):
    """Stop POP3 server."""
    if server:
        server.shutdown()
        server.server_close()
