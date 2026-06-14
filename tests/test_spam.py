"""Tests for spam filtering, dataset loading, and model training."""

from mailapp.config import load_config
from mailapp.spam.classifier import is_spam, keyword_spam_check, save_model, train_classifier
from mailapp.spam.dataset import load_spam_dataset
from mailapp.spam.train_spam import train_and_save_model


def test_keyword_spam():
    assert keyword_spam_check("Win Lottery Now and claim free money")


def test_keyword_ham():
    assert not keyword_spam_check("Please review the computer network homework")


def test_directory_dataset_loading(tmp_path):
    ham_dir = tmp_path / "ham"
    spam_dir = tmp_path / "spam"
    ham_dir.mkdir()
    spam_dir.mkdir()
    (ham_dir / "normal.eml").write_text(
        "Subject: Project meeting\n\nPlease review the network homework.",
        encoding="utf-8",
    )
    (spam_dir / "spam.eml").write_text(
        "Subject: Win Lottery Now\n\nClaim free prize money today.",
        encoding="utf-8",
    )

    texts, labels = load_spam_dataset(tmp_path)

    assert labels.count("ham") == 1
    assert labels.count("spam") == 1
    assert any("Project meeting" in text for text in texts)
    assert any("Win Lottery Now" in text for text in texts)


def test_train_and_save_model_outputs_metrics(tmp_path):
    csv_path = tmp_path / "spam.csv"
    csv_path.write_text(
        "\n".join(
            [
                "text,label",
                "project meeting schedule,ham",
                "homework review notes,ham",
                "network class discussion,ham",
                "lottery prize money,spam",
                "free winner click,spam",
                "urgent cash prize,spam",
            ]
        ),
        encoding="utf-8",
    )
    model_path = tmp_path / "models" / "spam_model.joblib"
    metrics_path = tmp_path / "models" / "metrics.json"
    matrix_path = tmp_path / "models" / "matrix.png"

    train_and_save_model(
        dataset_path=csv_path,
        model_path=model_path,
        test_size=0.5,
        metrics_path=metrics_path,
        confusion_matrix_path=matrix_path,
        max_features=1000,
    )

    assert model_path.exists()
    assert metrics_path.exists()
    assert matrix_path.exists() or matrix_path.with_suffix(".txt").exists()


def test_is_spam_uses_saved_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "spam_model_path: data/models/spam_model.joblib\n",
        encoding="utf-8",
    )
    load_config()
    model_path = tmp_path / "data" / "models" / "spam_model.joblib"
    bundle = train_classifier(
        [
            "project meeting schedule",
            "homework review notes",
            "network class discussion",
            "lottery prize money",
            "free winner click",
            "urgent cash prize",
        ],
        ["ham", "ham", "ham", "spam", "spam", "spam"],
    )
    save_model(bundle, model_path)

    assert is_spam("free lottery prize money")
    assert not is_spam("network project meeting notes")
