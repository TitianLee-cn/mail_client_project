"""Parse raw EML messages and extract headers, body, and attachments."""

from email import policy
from email.parser import BytesParser
from pathlib import Path


def parse_eml_file(eml_path):
    """Parse an .eml file into an EmailMessage."""
    return parse_eml_bytes(Path(eml_path).read_bytes())


def parse_eml_bytes(raw_bytes):
    """Parse raw email bytes into an EmailMessage."""
    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode("utf-8")
    return BytesParser(policy=policy.default).parsebytes(raw_bytes)


def extract_headers(message):
    """Return common headers as a dict."""
    return {
        "sender": message.get("From", ""),
        "recipients": message.get_all("To", []),
        "subject": message.get("Subject", ""),
        "date": message.get("Date", ""),
        "message_id": message.get("Message-ID", ""),
        "mail_id": message.get("X-MailApp-Mail-ID", ""),
    }


def extract_body(message):
    """Extract the best body text available, preferring text/plain."""
    if message.is_multipart():
        html = None
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            ctype = part.get_content_type()
            if ctype == "text/plain":
                return part.get_content()
            if ctype == "text/html":
                html = part.get_content()
        return html or ""
    return message.get_content()


def extract_attachments(message, output_dir):
    """Save attachments to output_dir and return saved paths."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    saved = []
    for part in message.walk():
        if part.get_content_disposition() != "attachment":
            continue
        filename = part.get_filename() or "attachment.bin"
        path = output / filename
        path.write_bytes(part.get_payload(decode=True) or b"")
        saved.append(path)
    return saved


def get_plain_text_for_spam_check(message):
    """Return text suitable for spam classification."""
    headers = extract_headers(message)
    return f"{headers.get('subject', '')}\n{extract_body(message)}"
