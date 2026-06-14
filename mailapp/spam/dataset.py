"""Dataset loading and email text extraction for spam model training."""

import csv
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path

from sklearn.model_selection import train_test_split


TOY_TEXTS = [
    "hello bob please review the network project",
    "meeting notes and normal class discussion",
    "winner lottery free prize click now",
    "urgent money prize winner",
]
TOY_LABELS = ["ham", "ham", "spam", "spam"]


def _label_from_path(path):
    parts = {part.lower() for part in path.parts}
    if {"spam", "spam_2", "junk"} & parts:
        return "spam"
    if {"ham", "easy_ham", "hard_ham", "inbox"} & parts:
        return "ham"
    return None


def _strip_html(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()


def _message_text(raw):
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
    except Exception:
        return raw.decode("utf-8", errors="ignore")

    parts = [message.get("Subject", "")]
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() in ("text/plain", "text/html"):
                content = part.get_content()
                parts.append(_strip_html(content) if part.get_content_type() == "text/html" else content)
    else:
        content = message.get_content()
        parts.append(_strip_html(content) if message.get_content_type() == "text/html" else content)
    return "\n".join(part for part in parts if part)


def _load_csv(path):
    texts, labels = [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            text = (row.get("text") or row.get("message") or row.get("body") or "").strip()
            label = (row.get("label") or row.get("class") or "").strip().lower()
            if text and label in {"spam", "ham"}:
                texts.append(text)
                labels.append(label)
    return texts, labels


def _load_directory(path):
    texts, labels = [], []
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        label = _label_from_path(file_path.relative_to(path))
        if label is None:
            continue
        try:
            text = _message_text(file_path.read_bytes()).strip()
        except OSError:
            continue
        if text:
            texts.append(text)
            labels.append(label)
    return texts, labels


def load_spam_dataset(dataset_path=None):
    """Load CSV or ham/spam directory data, falling back to a toy dataset."""
    path = Path(dataset_path) if dataset_path else None
    if not path or not path.exists():
        return TOY_TEXTS, TOY_LABELS
    texts, labels = _load_directory(path) if path.is_dir() else _load_csv(path)
    if not texts:
        raise ValueError(f"No spam/ham samples found in dataset: {path}")
    return texts, labels


def split_dataset(texts, labels, test_size=0.2):
    """Split texts and labels for training/evaluation."""
    stratify = labels if min(labels.count(label) for label in set(labels)) > 1 else None
    try:
        return train_test_split(texts, labels, test_size=test_size, random_state=42, stratify=stratify)
    except ValueError:
        return train_test_split(texts, labels, test_size=test_size, random_state=42)
