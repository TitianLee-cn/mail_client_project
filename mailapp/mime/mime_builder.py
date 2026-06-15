"""Build MIME email messages for text, HTML, and attachments."""

import mimetypes
from html.parser import HTMLParser
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())


def _html_to_text(value):
    parser = _HTMLTextExtractor()
    parser.feed(value or "")
    return " ".join(parser.parts)


def generate_message_id():
    """Generate an RFC-like Message-ID."""
    return make_msgid(domain="mailapp.local")


def _base_message(sender, recipients, subject):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = generate_message_id()
    msg["X-MailApp-Mail-ID"] = str(uuid.uuid4())
    return msg


def build_text_email(sender, recipients, subject, body):
    """Build a plain text EmailMessage."""
    msg = _base_message(sender, recipients, subject)
    msg.set_content(body or "")
    return msg


def build_html_email(sender, recipients, subject, html_body):
    """Build multipart/alternative HTML mail with a meaningful text fallback."""
    msg = _base_message(sender, recipients, subject)
    msg.set_content(_html_to_text(html_body) or "This email contains HTML content.")
    msg.add_alternative(html_body or "", subtype="html")
    return msg


def build_email_with_attachments(sender, recipients, subject, body, attachment_paths):
    """Build a text email and attach ordinary files."""
    msg = build_text_email(sender, recipients, subject, body)
    for attachment_path in attachment_paths or []:
        path = Path(attachment_path)
        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        data = path.read_bytes()
        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=path.name,
        )
    return msg
