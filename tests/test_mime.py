"""Tests for MIME construction and parsing."""

from mailapp.mime.mime_builder import build_html_email, build_text_email
from mailapp.mime.mime_parser import (
    extract_attachments,
    extract_body,
    extract_headers,
    parse_eml_bytes,
)
from mailapp.protocols.smtp_client import build_outgoing_email


def test_build_text_email():
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Hello", "Network class")
    assert msg["From"] == "alice@example.com"
    assert msg["Message-ID"]
    assert msg["X-MailApp-Mail-ID"]
    assert "Network class" in msg.get_content()


def test_parse_text_email():
    msg = build_text_email("alice@example.com", ["bob@example.com"], "Hello", "Network class")
    parsed = parse_eml_bytes(msg.as_bytes())
    headers = extract_headers(parsed)
    assert headers["sender"] == "alice@example.com"
    assert headers["subject"] == "Hello"
    assert "Network class" in extract_body(parsed)


def test_html_has_plain_fallback():
    msg = build_html_email(
        "alice@example.com",
        ["bob@example.com"],
        "HTML",
        "<h1>Win Lottery</h1><p>Claim prize</p>",
    )
    plain = msg.get_body(preferencelist=("plain",)).get_content()
    assert "Win Lottery" in plain
    assert msg.get_body(preferencelist=("html",)).get_content_type() == "text/html"


def test_attachment_round_trip_uses_safe_filename(tmp_path):
    source = tmp_path / "report.txt"
    source.write_text("network report", encoding="utf-8")
    msg = build_outgoing_email(
        "alice@example.com",
        ["bob@example.com"],
        "Attachment",
        "See attachment",
        attachments=[source],
    )
    parsed = parse_eml_bytes(msg.as_bytes())
    paths = extract_attachments(parsed, tmp_path / "downloads")
    assert paths[0].name == "report.txt"
    assert paths[0].read_text(encoding="utf-8") == "network report"
