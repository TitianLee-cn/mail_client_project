"""Tests for keyword fallback and trained TF-IDF classifiers."""

import csv

import yaml

from mailapp.config import load_config
from mailapp.spam.classifier import is_spam, keyword_spam_check, model_status
from mailapp.spam.train_spam import train_and_save_model


def test_keyword_spam():
    assert keyword_spam_check("Win Lottery Now and claim free money")


def test_keyword_ham():
    assert not keyword_spam_check("Please review the computer network homework")


def test_train_evaluate_and_use_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "spam_model_path": "data/models/spam_model.joblib",
        "spam_report_path": "data/models/spam_metrics.json",
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    load_config()
    dataset = tmp_path / "dataset.csv"
    rows = []
    for index in range(12):
        rows.append({"text": f"project meeting report schedule {index}", "label": "ham"})
        rows.append({"text": f"lottery cash prize winner offer {index}", "label": "spam"})
    with dataset.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    _bundle, metrics = train_and_save_model(
        dataset_path=dataset,
        model_type="naive_bayes",
        test_size=0.25,
    )

    assert metrics["accuracy"] >= 0.8
    assert metrics["confusion_matrix"]
    assert model_status()["available"]
    assert is_spam("lottery cash prize winner")
    assert not is_spam("project meeting report schedule")
