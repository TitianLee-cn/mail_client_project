"""SMTP server based on aiosmtpd."""

try:
    from aiosmtpd.controller import Controller
    from aiosmtpd.smtp import AuthResult, LoginPassword
except ImportError:  # pragma: no cover - exercised only when dependency is missing.
    Controller = None
    AuthResult = None
    LoginPassword = None

from mailapp.auth.user_store import verify_user
from mailapp.common.logger import get_logger
from mailapp.config import get_config
from mailapp.storage.mail_store import store_incoming_email

logger = get_logger(__name__)


class SMTPHandler:
    """aiosmtpd handler that stores incoming messages."""

    async def handle_DATA(self, server, session, envelope):
        """Receive DATA content and persist it."""
        # When AUTH is enforced, refuse to relay mail whose MAIL FROM does not
        # match the authenticated user. This is a small anti-spoofing check.
        auth_user = getattr(session, "auth_data", None)
        if auth_user and envelope.mail_from and auth_user != envelope.mail_from:
            return "553 5.7.1 Sender address does not match authenticated user"
        process_incoming_message(
            envelope.mail_from,
            envelope.rcpt_tos,
            envelope.content,
        )
        return "250 Message accepted for delivery"


def smtp_authenticator(server, session, envelope, mechanism, auth_data):
    """aiosmtpd AUTH callback backed by the project user store.

    Supports PLAIN and LOGIN mechanisms over an authenticated SMTP session.
    """
    if AuthResult is None:  # pragma: no cover - guarded above.
        raise RuntimeError("aiosmtpd is required for SMTP AUTH")
    if mechanism not in ("LOGIN", "PLAIN"):
        return AuthResult(success=False, handled=False)
    if not isinstance(auth_data, LoginPassword):
        return AuthResult(success=False, handled=False)
    try:
        username = auth_data.login.decode("utf-8")
        password = auth_data.password.decode("utf-8")
    except (AttributeError, UnicodeDecodeError):
        return AuthResult(success=False, handled=True, message="535 5.7.8 Malformed credentials")
    if verify_user(username, password):
        logger.info("SMTP AUTH success for %s", username)
        return AuthResult(success=True, auth_data=username)
    logger.info("SMTP AUTH failure for %s", username)
    return AuthResult(success=False, handled=True, message="535 5.7.8 Authentication credentials invalid")


def process_incoming_message(sender, recipients, raw_message):
    """Store one incoming SMTP message."""
    return store_incoming_email(sender, recipients, raw_message)


def start_smtp_server(
    host,
    port,
    *,
    auth_required=None,
    auth_require_tls=None,
    tls_context=None,
    require_starttls=None,
    implicit_tls=False,
):
    """Start SMTP server and return its controller.

    AUTH defaults follow ``config.yaml``:
      - ``smtp_auth_required`` (default True): require AUTH before MAIL FROM.
      - ``smtp_auth_require_tls`` (default False): require STARTTLS before AUTH.
    """
    if Controller is None:
        raise RuntimeError("aiosmtpd is required to start SMTP server. Run: pip install -r requirements.txt")
    config = get_config() or {}
    if auth_required is None:
        auth_required = config.get("smtp_auth_required", True)
    if auth_require_tls is None:
        auth_require_tls = config.get("smtp_auth_require_tls", False)
    if require_starttls is None:
        require_starttls = config.get("smtp_require_starttls", False)
    if implicit_tls and tls_context is None:
        raise ValueError("SMTP implicit TLS requires an SSL context")
    kwargs = {
        "authenticator": smtp_authenticator,
        "auth_required": auth_required,
        "auth_require_tls": auth_require_tls,
        "require_starttls": require_starttls,
        "enable_SMTPUTF8": True,
    }
    if implicit_tls:
        kwargs["ssl_context"] = tls_context
    else:
        kwargs["tls_context"] = tls_context
    controller = Controller(SMTPHandler(), hostname=host, port=port, **kwargs)
    controller.start()
    return controller


def stop_smtp_server(controller):
    """Stop SMTP server controller."""
    if controller:
        controller.stop()
