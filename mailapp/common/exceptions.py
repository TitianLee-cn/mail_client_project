"""Project-specific exception classes."""


class MailAppError(Exception):
    """Base exception for mail application errors."""


class AuthenticationError(MailAppError):
    """Raised when user authentication fails."""


class MailNotFoundError(MailAppError):
    """Raised when a mail_id cannot be found."""


class RecallError(MailAppError):
    """Raised when an email recall request is invalid."""


class SpamModelNotFoundError(MailAppError):
    """Raised when a requested spam model file is missing."""
