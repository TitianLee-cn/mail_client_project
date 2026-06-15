"""RFC 1939 POP3 server with USER/PASS authentication and TLS support."""

import socketserver
import ssl
import threading

from mailapp.auth.user_store import verify_user
from mailapp.storage.db import execute_transaction
from mailapp.storage.mail_store import (
    get_email_raw_content,
    list_pop3_maildrop,
    mark_email_as_read,
    mark_emails_as_deleted,
)

AUTHORIZATION = "AUTHORIZATION"
TRANSACTION = "TRANSACTION"
UPDATE = "UPDATE"


def _canonical_message(raw):
    """Return RFC-style CRLF data with exactly one final CRLF."""
    lines = raw.splitlines()
    return b"\r\n".join(lines) + b"\r\n"


def _dot_stuffed(raw):
    """Apply POP3 transparency to a canonical message."""
    canonical = _canonical_message(raw)
    return b"\r\n".join(
        b"." + line if line.startswith(b".") else line
        for line in canonical.split(b"\r\n")[:-1]
    ) + b"\r\n"


class POP3Handler(socketserver.StreamRequestHandler):
    """Serve one RFC 1939 maildrop session."""

    def setup(self):
        super().setup()
        self.state = AUTHORIZATION
        self.username = None
        self.maildrop = []
        self.deleted = set()
        self.tls_active = isinstance(self.connection, ssl.SSLSocket)

    def handle(self):
        self._send("+OK MailApp POP3 server ready")
        while self.state != UPDATE:
            raw_line = self.rfile.readline(513)
            if not raw_line:
                break
            if len(raw_line) > 512 or not raw_line.endswith(b"\n"):
                while raw_line and not raw_line.endswith(b"\n"):
                    raw_line = self.rfile.readline(513)
                self._send("-ERR command line too long")
                continue
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                self._send("-ERR empty command")
                continue
            parts = line.split()
            command = parts[0].upper()
            args = parts[1:]
            handler = getattr(self, f"command_{command}", None)
            if handler is None:
                self._send("-ERR unsupported command")
                continue
            handler(args)

    def _send(self, line):
        try:
            self.wfile.write((line + "\r\n").encode("utf-8"))
        except OSError:
            self.state = UPDATE

    def _require_state(self, required):
        if self.state != required:
            self._send(f"-ERR command invalid in {self.state} state")
            return False
        return True

    def _message(self, value):
        try:
            number = int(value)
        except (TypeError, ValueError):
            self._send("-ERR invalid message number")
            return None
        if number < 1 or number > len(self.maildrop) or number in self.deleted:
            self._send("-ERR no such message")
            return None
        return number, self.maildrop[number - 1]

    def _message_size(self, row):
        return len(_canonical_message(get_email_raw_content(row["mail_id"])))

    def command_USER(self, args):
        if not self._require_state(AUTHORIZATION):
            return
        if len(args) != 1:
            self._send("-ERR syntax: USER name")
            return
        self.username = args[0]
        self._send("+OK user accepted")

    def command_PASS(self, args):
        if not self._require_state(AUTHORIZATION):
            return
        if len(args) != 1 or not self.username:
            self._send("-ERR send USER before PASS")
            return
        if not self.tls_active and self.server.require_tls_for_auth:
            self._send("-ERR cleartext authentication requires STLS")
            return
        if not verify_user(self.username, args[0]):
            self.username = None
            self._send("-ERR authentication failed")
            return
        self.maildrop = list(list_pop3_maildrop(self.username))
        self.deleted.clear()
        self.state = TRANSACTION
        self._send(f"+OK maildrop has {len(self.maildrop)} messages")

    def command_STLS(self, args):
        if not self._require_state(AUTHORIZATION):
            return
        if args:
            self._send("-ERR STLS takes no arguments")
            return
        if self.tls_active:
            self._send("-ERR TLS is already active")
            return
        if self.server.ssl_context is None:
            self._send("-ERR TLS is not available")
            return
        self._send("+OK begin TLS negotiation")
        self.wfile.flush()
        self.connection = self.server.ssl_context.wrap_socket(
            self.connection, server_side=True
        )
        self.rfile = self.connection.makefile("rb")
        self.wfile = self.connection.makefile("wb", buffering=0)
        self.tls_active = True
        self.username = None

    def command_STAT(self, args):
        if not self._require_state(TRANSACTION):
            return
        if args:
            self._send("-ERR STAT takes no arguments")
            return
        rows = [
            row for number, row in enumerate(self.maildrop, 1)
            if number not in self.deleted
        ]
        self._send(f"+OK {len(rows)} {sum(self._message_size(row) for row in rows)}")

    def command_LIST(self, args):
        if not self._require_state(TRANSACTION):
            return
        if len(args) > 1:
            self._send("-ERR syntax: LIST [msg]")
            return
        if args:
            item = self._message(args[0])
            if item:
                number, row = item
                self._send(f"+OK {number} {self._message_size(row)}")
            return
        self._send("+OK scan listing follows")
        for number, row in enumerate(self.maildrop, 1):
            if number not in self.deleted:
                self._send(f"{number} {self._message_size(row)}")
        self._send(".")

    def command_UIDL(self, args):
        if not self._require_state(TRANSACTION):
            return
        if len(args) > 1:
            self._send("-ERR syntax: UIDL [msg]")
            return
        if args:
            item = self._message(args[0])
            if item:
                number, row = item
                self._send(f"+OK {number} {row['mail_id']}")
            return
        self._send("+OK unique-id listing follows")
        for number, row in enumerate(self.maildrop, 1):
            if number not in self.deleted:
                self._send(f"{number} {row['mail_id']}")
        self._send(".")

    def command_RETR(self, args):
        if not self._require_state(TRANSACTION):
            return
        if len(args) != 1:
            self._send("-ERR syntax: RETR msg")
            return
        item = self._message(args[0])
        if not item:
            return
        _number, row = item
        raw = get_email_raw_content(row["mail_id"])
        self._send(f"+OK {self._message_size(row)} octets")
        self.wfile.write(_dot_stuffed(raw))
        self.wfile.write(b".\r\n")
        mark_email_as_read(row["mail_id"], self.username)

    def command_DELE(self, args):
        if not self._require_state(TRANSACTION):
            return
        if len(args) != 1:
            self._send("-ERR syntax: DELE msg")
            return
        item = self._message(args[0])
        if not item:
            return
        number, _row = item
        self.deleted.add(number)
        self._send(f"+OK message {number} marked for deletion")

    def command_NOOP(self, args):
        if not self._require_state(TRANSACTION):
            return
        if args:
            self._send("-ERR NOOP takes no arguments")
            return
        self._send("+OK")

    def command_RSET(self, args):
        if not self._require_state(TRANSACTION):
            return
        if args:
            self._send("-ERR RSET takes no arguments")
            return
        self.deleted.clear()
        self._send(f"+OK maildrop has {len(self.maildrop)} messages")

    def command_CAPA(self, args):
        if args:
            self._send("-ERR CAPA takes no arguments")
            return
        self._send("+OK capability list follows")
        self._send("USER")
        self._send("UIDL")
        if self.state == AUTHORIZATION and not self.tls_active and self.server.ssl_context:
            self._send("STLS")
        self._send(".")

    def command_QUIT(self, args):
        if args:
            self._send("-ERR QUIT takes no arguments")
            return
        if self.state == TRANSACTION:
            mail_ids = [
                self.maildrop[number - 1]["mail_id"]
                for number in sorted(self.deleted)
            ]
            try:
                execute_transaction(
                    lambda conn: mark_emails_as_deleted(
                        mail_ids, self.username, conn=conn
                    )
                )
            except Exception:
                self._send("-ERR unable to update maildrop")
                self.state = UPDATE
                return
        self.state = UPDATE
        self._send("+OK MailApp POP3 server signing off")


class ThreadingPOP3Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        server_address,
        handler_class,
        *,
        ssl_context=None,
        implicit_tls=False,
        require_tls_for_auth=True,
    ):
        self.ssl_context = ssl_context
        self.implicit_tls = implicit_tls
        self.require_tls_for_auth = require_tls_for_auth
        super().__init__(server_address, handler_class)

    def get_request(self):
        sock, address = super().get_request()
        if self.implicit_tls:
            sock = self.ssl_context.wrap_socket(sock, server_side=True)
        return sock, address


def start_pop3_server(
    host,
    port,
    *,
    ssl_context=None,
    implicit_tls=False,
    require_tls_for_auth=True,
):
    """Start POP3 in a background thread and return the server."""
    if implicit_tls and ssl_context is None:
        raise ValueError("POP3 implicit TLS requires an SSL context")
    server = ThreadingPOP3Server(
        (host, port),
        POP3Handler,
        ssl_context=ssl_context,
        implicit_tls=implicit_tls,
        require_tls_for_auth=require_tls_for_auth,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.thread = thread
    return server


def stop_pop3_server(server):
    """Stop POP3 server."""
    if server:
        server.shutdown()
        server.server_close()
        if getattr(server, "thread", None):
            server.thread.join(timeout=5)
