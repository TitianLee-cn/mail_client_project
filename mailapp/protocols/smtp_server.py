"""SMTP server based on aiosmtpd."""

try:
    from aiosmtpd.controller import Controller
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    Controller = None

from mailapp.storage.mail_store import store_incoming_email


class SMTPHandler:
    """aiosmtpd handler that stores incoming messages."""

    async def handle_DATA(self, server, session, envelope):
        """Receive DATA content and persist it."""
        process_incoming_message(
            envelope.mail_from,
            envelope.rcpt_tos,
            envelope.content,
        )
        # TODO: add SMTP AUTH for a fuller RFC-style implementation.
        return "250 Message accepted for delivery"


def process_incoming_message(sender, recipients, raw_message):
    """Store one incoming SMTP message."""
    return store_incoming_email(sender, recipients, raw_message)


def start_smtp_server(host, port):
    """Start SMTP server and return its controller."""
    if Controller is None:
        raise RuntimeError("aiosmtpd is required to start SMTP server. Run: pip install -r requirements.txt")
    controller = Controller(SMTPHandler(), hostname=host, port=port)
    controller.start()
    return controller


def stop_smtp_server(controller):
    """Stop SMTP server controller."""
    if controller:
        controller.stop()
