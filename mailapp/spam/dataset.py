"""Dataset loading for spam model training."""

import csv
from email import policy
from email.parser import BytesParser
from pathlib import Path

from sklearn.model_selection import train_test_split


TOY_TEXTS = [
    "hello bob please review the network project",
    "meeting notes and normal class discussion",
    "the lab report is attached for tomorrow",
    "please confirm the project presentation time",
    "winner lottery free prize click now",
    "urgent money prize winner",
    "claim your cash reward and exclusive offer",
    "limited deal buy now congratulations winner",
]
TOY_LABELS = ["ham", "ham", "ham", "ham", "spam", "spam", "spam", "spam"]


def _email_text(path):
    raw = path.read_bytes()
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        subject = message.get("Subject", "")
        body = message.get_body(preferencelist=("plain", "html"))
        return f"{subject}\n{body.get_content() if body else ''}"
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _load_directory_dataset(path):
    """Load Enron/Ling-Spam style ham and spam directory trees."""
    texts, labels = [], []
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        relative_parts = {
            part.lower() for part in file_path.relative_to(path).parts[:-1]
        }
        label = "spam" if any("spam" in part for part in relative_parts) else None
        if label is None and any(
            marker in part
            for part in relative_parts
            for marker in ("ham", "legit")
        ):
            label = "ham"
        if label:
            texts.append(_email_text(file_path))
            labels.append(label)
    if not texts:
        raise ValueError(
            f"No labeled mail found under {path}; expected ham/ and spam/ directories"
        )
    if set(labels) != {"ham", "spam"}:
        raise ValueError(
            f"Dataset must contain both ham and spam directories; found {set(labels)}"
        )
    return texts, labels


def load_spam_dataset(dataset_path):
    """Load text,label CSV or an Enron/Ling-Spam directory tree."""
    path = Path(dataset_path) if dataset_path else None
    if not path or not path.exists():
        return TOY_TEXTS, TOY_LABELS
    if path.is_dir():
        return _load_directory_dataset(path)
    texts, labels = [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            label = row["label"].strip().lower()
            if label not in {"ham", "spam"}:
                raise ValueError(f"Unsupported label: {label}")
            texts.append(row["text"])
            labels.append(label)
    if len(set(labels)) != 2:
        raise ValueError("Spam dataset must contain both ham and spam examples")
    return texts, labels


def split_dataset(texts, labels, test_size=0.2):
    """Split texts and labels for training/evaluation."""
    return train_test_split(
        texts,
        labels,
        test_size=test_size,
        random_state=42,
        stratify=labels,
    )
