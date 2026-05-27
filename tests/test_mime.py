"""Tests for MIME construction and parsing."""

from mailapp.mime.mime_builder import build_text_email
from mailapp.mime.mime_parser import extract_body, extract_headers, parse_eml_bytes


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
