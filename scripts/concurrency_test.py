import concurrent.futures
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from pathlib import Path


SMTP_HOST = "127.0.0.1"
SMTP_PORT = 2525

DB_PATH = Path("data/email.db")

SENDER = "alice@example.com"
RECIPIENT = "bob@example.com"


def send_one(index: int, batch_id: str):
    subject = f"concurrency test {batch_id} #{index}"
    body = f"This is concurrent email number {index}."

    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.send_message(msg)

    return subject


def count_emails_in_db(batch_id: str):
    conn = sqlite3.connect(DB_PATH)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM emails WHERE subject LIKE ?",
            (f"concurrency test {batch_id}%",),
        ).fetchone()[0]
        return count
    finally:
        conn.close()


def main():
    batch_id = str(int(time.time()))
    client_count = 10

    print(f"[INFO] Starting concurrency test with {client_count} clients")
    print(f"[INFO] Batch id: {batch_id}")

    subjects = []
    errors = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=client_count) as executor:
        futures = [
            executor.submit(send_one, i, batch_id)
            for i in range(1, client_count + 1)
        ]

        for future in concurrent.futures.as_completed(futures):
            try:
                subject = future.result()
                subjects.append(subject)
                print(f"[OK] Sent: {subject}")
            except Exception as exc:
                errors.append(exc)
                print(f"[ERROR] {exc}")

    time.sleep(1)

    db_count = count_emails_in_db(batch_id)

    print("\n========== Concurrency Test Result ==========")
    print(f"Expected sent emails : {client_count}")
    print(f"Successful sends     : {len(subjects)}")
    print(f"Errors               : {len(errors)}")
    print(f"Emails found in DB   : {db_count}")

    if errors:
        raise RuntimeError("Some SMTP clients failed")

    if db_count != client_count:
        raise RuntimeError(
            f"Database count mismatch: expected {client_count}, got {db_count}"
        )

    print("\nALL CONCURRENCY TESTS PASSED.")


if __name__ == "__main__":
    main()