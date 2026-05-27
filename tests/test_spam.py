"""Tests for spam keyword fallback."""

from mailapp.spam.classifier import keyword_spam_check


def test_keyword_spam():
    assert keyword_spam_check("Win Lottery Now and claim free money")


def test_keyword_ham():
    assert not keyword_spam_check("Please review the computer network homework")
