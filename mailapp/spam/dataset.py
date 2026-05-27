"""Dataset loading for spam model training."""

import csv
from pathlib import Path

from sklearn.model_selection import train_test_split


TOY_TEXTS = [
    "hello bob please review the network project",
    "meeting notes and normal class discussion",
    "winner lottery free prize click now",
    "urgent money prize winner",
]
TOY_LABELS = ["ham", "ham", "spam", "spam"]


def load_spam_dataset(dataset_path):
    """Load text,label CSV or return a toy dataset if missing."""
    path = Path(dataset_path) if dataset_path else None
    if not path or not path.exists():
        # TODO: replace with Enron-Spam Dataset preprocessing.
        return TOY_TEXTS, TOY_LABELS
    texts, labels = [], []
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            labels.append(row["label"])
    return texts, labels


def split_dataset(texts, labels, test_size=0.2):
    """Split texts and labels for training/evaluation."""
    return train_test_split(texts, labels, test_size=test_size, random_state=42)
