import argparse
import concurrent.futures
import smtplib
import sqlite3
import ssl
import time
import traceback
from email.message import EmailMessage
from pathlib import Path

import yaml

SMTP_HOST = "127.0.0.1"
SMTP_PORT = 2525

DB_PATH = Path("data/email.db")

DEFAULT_SENDER = "alice@example.com"
DEFAULT_RECIPIENT = "bob@example.com"


def send_one(
    index,
    batch_id,
    sender,
    password,
    recipient,
    smtp_host,
    smtp_port,
    security,
    cafile,
):
    """Simulate one SMTP client sending one email."""
    subject = f"concurrency test {batch_id} #{index:03d}"
    body = f"This is concurrent email number {index}."

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    start = time.perf_counter()

    context = ssl.create_default_context(cafile=cafile)
    if security == "ssl":
        server = smtplib.SMTP_SSL(
            smtp_host, smtp_port, timeout=15, context=context
        )
    else:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
    with server:
        if security == "starttls":
            server.starttls(context=context)
        server.login(sender, password)
        server.send_message(msg)

    end = time.perf_counter()

    return {
        "index": index,
        "subject": subject,
        "latency": end - start,
    }


def query_database(batch_id: str, recipient: str):
    """Check how many test emails were stored in SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        email_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM emails
            WHERE subject LIKE ?
            """,
            (f"concurrency test {batch_id}%",),
        ).fetchone()["count"]

        recipient_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM recipients
            JOIN emails USING(mail_id)
            WHERE emails.subject LIKE ?
              AND recipients.recipient = ?
            """,
            (f"concurrency test {batch_id}%", recipient),
        ).fetchone()["count"]

        recent_rows = conn.execute(
            """
            SELECT emails.mail_id,
                   emails.subject,
                   emails.sender,
                   recipients.recipient,
                   recipients.folder,
                   recipients.read_status,
                   recipients.deleted
            FROM emails
            JOIN recipients USING(mail_id)
            WHERE emails.subject LIKE ?
            ORDER BY emails.id DESC
            LIMIT 5
            """,
            (f"concurrency test {batch_id}%",),
        ).fetchall()

        return email_count, recipient_count, recent_rows

    finally:
        conn.close()


def ask_client_count(default: int = 10) -> int:
    """Ask user for concurrent client count when it is not provided by command line."""
    raw = input(f"Enter number of concurrent clients [{default}]: ").strip()

    if raw == "":
        return default

    try:
        value = int(raw)
    except ValueError:
        raise ValueError("Client count must be an integer.")

    if value <= 0:
        raise ValueError("Client count must be greater than 0.")

    return value


def parse_args():
    parser = argparse.ArgumentParser(
        description="SMTP concurrency test for the simulated mail server."
    )

    parser.add_argument(
        "-c",
        "--clients",
        type=int,
        default=None,
        help="Number of concurrent SMTP clients. If omitted, the script will ask interactively.",
    )

    parser.add_argument(
        "--sender",
        type=str,
        default=DEFAULT_SENDER,
        help=f"Sender email address. Default: {DEFAULT_SENDER}",
    )

    parser.add_argument(
        "--recipient",
        type=str,
        default=DEFAULT_RECIPIENT,
        help=f"Recipient email address. Default: {DEFAULT_RECIPIENT}",
    )

    parser.add_argument(
        "--password",
        default=None,
        help="SMTP password; defaults to the matching config.yaml demo user.",
    )

    parser.add_argument(
        "--smtp-host",
        type=str,
        default=SMTP_HOST,
        help=f"SMTP host. Default: {SMTP_HOST}",
    )

    parser.add_argument(
        "--smtp-port",
        type=int,
        default=SMTP_PORT,
        help=f"SMTP port. Default: {SMTP_PORT}",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

    if args.clients is None:
        client_count = ask_client_count(default=10)
    else:
        client_count = args.clients

    if client_count <= 0:
        raise ValueError("Client count must be greater than 0.")

    batch_id = str(int(time.time()))
    password = args.password or next(
        (
            item["password"]
            for item in config.get("default_users", [])
            if item["username"] == args.sender
        ),
        None,
    )
    if not password:
        raise ValueError("No password supplied for the SMTP sender.")
    security = str(config.get("smtp_security", "plain")).lower()
    cafile = config.get("ssl_cafile") or config.get("smtp_ssl_cafile")

    print("========== SMTP Concurrency Test ==========")
    print(f"Batch ID       : {batch_id}")
    print(f"SMTP server    : {args.smtp_host}:{args.smtp_port}")
    print(f"Client count   : {client_count}")
    print(f"Sender         : {args.sender}")
    print(f"Recipient      : {args.recipient}")
    print()

    start_all = time.perf_counter()

    successes = []
    failures = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=client_count) as executor:
        futures = [
            executor.submit(
                send_one,
                i,
                batch_id,
                args.sender,
                password,
                args.recipient,
                args.smtp_host,
                args.smtp_port,
                security,
                cafile,
            )
            for i in range(1, client_count + 1)
        ]

        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                successes.append(result)
                print(f"[OK] #{result['index']:03d} sent in {result['latency']:.3f}s")
            except Exception as exc:
                failures.append(exc)
                print("[ERROR]", repr(exc))
                traceback.print_exc()

    end_all = time.perf_counter()
    elapsed = end_all - start_all

    time.sleep(1.0)

    email_count, recipient_count, recent_rows = query_database(batch_id, args.recipient)

    latencies = [x["latency"] for x in successes]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    min_latency = min(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0
    throughput = len(successes) / elapsed if elapsed > 0 else 0.0

    print()
    print("========== Concurrency Test Result ==========")
    print(f"Expected emails       : {client_count}")
    print(f"Successful sends      : {len(successes)}")
    print(f"Failed sends          : {len(failures)}")
    print(f"Emails found in DB    : {email_count}")
    print(f"Recipients in DB      : {recipient_count}")
    print(f"Total elapsed time    : {elapsed:.3f}s")
    print(f"Throughput            : {throughput:.2f} emails/s")
    print(f"Average send latency  : {avg_latency:.3f}s")
    print(f"Min send latency      : {min_latency:.3f}s")
    print(f"Max send latency      : {max_latency:.3f}s")

    print()
    print("Recent stored rows:")
    for row in recent_rows:
        print(dict(row))

    print()

    if failures:
        raise RuntimeError("Concurrency test failed: some clients failed to send emails.")

    if email_count != client_count:
        raise RuntimeError(
            f"Concurrency test failed: expected {client_count} emails in emails table, "
            f"but found {email_count}."
        )

    if recipient_count != client_count:
        raise RuntimeError(
            f"Concurrency test failed: expected {client_count} recipient records, "
            f"but found {recipient_count}."
        )

    print("ALL CONCURRENCY TESTS PASSED.")


if __name__ == "__main__":
    main()
