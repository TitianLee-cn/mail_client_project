"""Train, evaluate, and persist the spam classifier."""

import argparse
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from mailapp.config import get_config, load_config
from mailapp.spam.classifier import save_model, train_classifier
from mailapp.spam.dataset import load_spam_dataset, split_dataset
from mailapp.spam.features import transform_texts


def evaluate_model(model_bundle, X_test, y_test):
    """Return accuracy, per-class metrics, and confusion matrix."""
    features = transform_texts(model_bundle["vectorizer"], X_test)
    predictions = model_bundle["classifier"].predict(features)
    accuracy = accuracy_score(y_test, predictions)
    metrics = {
        "accuracy": accuracy,
        "classification_report": classification_report(
            y_test, predictions, labels=["ham", "spam"], output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            y_test, predictions, labels=["ham", "spam"]
        ).tolist(),
        "labels": ["ham", "spam"],
        "test_samples": len(y_test),
    }
    print(f"accuracy: {accuracy:.3f}")
    print(f"confusion_matrix: {metrics['confusion_matrix']}")
    return metrics


def train_and_save_model(
    dataset_path=None,
    model_path=None,
    report_path=None,
    model_type="naive_bayes",
    test_size=0.2,
):
    """Train from CSV or toy data and save model."""
    texts, labels = load_spam_dataset(dataset_path)
    X_train, X_test, y_train, y_test = split_dataset(
        texts, labels, test_size=test_size
    )
    bundle = train_classifier(X_train, y_train, model_type=model_type)
    metrics = evaluate_model(bundle, X_test, y_test)
    bundle["metrics"] = metrics
    target = Path(model_path or get_config()["spam_model_path"])
    save_model(bundle, target)
    report_target = Path(
        report_path or get_config().get("spam_report_path", "data/models/spam_metrics.json")
    )
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(
        json.dumps(
            {
                **metrics,
                "model_type": model_type,
                "dataset_path": str(dataset_path or "built-in-demo"),
                "training_samples": len(X_train),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return bundle, metrics


def main():
    """CLI entry for python -m mailapp.spam.train_spam."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        help="CSV with text,label columns or a directory containing ham/spam trees",
    )
    parser.add_argument("--model", choices=("naive_bayes", "svm"), default="naive_bayes")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()
    load_config()
    train_and_save_model(
        dataset_path=args.dataset,
        model_path=get_config()["spam_model_path"],
        model_type=args.model,
        test_size=args.test_size,
    )


if __name__ == "__main__":
    main()
