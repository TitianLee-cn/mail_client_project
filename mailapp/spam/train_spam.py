"""Train, evaluate, and save the spam classifier."""

import argparse
import json
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from mailapp.config import get_config, load_config
from mailapp.spam.classifier import save_model, train_classifier
from mailapp.spam.dataset import load_spam_dataset, split_dataset
from mailapp.spam.features import transform_texts


def _ordered_labels(*label_groups):
    labels = []
    for preferred in ("ham", "spam"):
        if any(preferred in group for group in label_groups):
            labels.append(preferred)
    for group in label_groups:
        for label in sorted(set(group)):
            if label not in labels:
                labels.append(label)
    return labels


def _save_confusion_matrix_plot(matrix, labels, output_path):
    """Save a confusion matrix image when matplotlib is available."""
    if not output_path:
        return ""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt
        from sklearn.metrics import ConfusionMatrixDisplay
    except Exception:
        fallback = output_path.with_suffix(".txt")
        fallback.write_text(
            "labels: " + ", ".join(labels) + "\n" + "\n".join(" ".join(map(str, row)) for row in matrix),
            encoding="utf-8",
        )
        return str(fallback)

    display = ConfusionMatrixDisplay(confusion_matrix=matrix, display_labels=labels)
    display.plot(cmap="Blues", values_format="d")
    plt.title("Spam Classifier Confusion Matrix")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    return str(output_path)


def evaluate_model(model_bundle, X_test, y_test, metrics_path=None, confusion_matrix_path=None):
    """Print metrics and optionally save evaluation artifacts."""
    features = transform_texts(model_bundle["vectorizer"], X_test)
    predictions = model_bundle["classifier"].predict(features)
    accuracy = accuracy_score(y_test, predictions)
    labels = _ordered_labels(y_test, predictions)
    matrix = confusion_matrix(y_test, predictions, labels=labels)
    report = classification_report(y_test, predictions, labels=labels, zero_division=0)
    report_dict = classification_report(y_test, predictions, labels=labels, output_dict=True, zero_division=0)
    matrix_artifact = _save_confusion_matrix_plot(matrix, labels, confusion_matrix_path)

    print(f"accuracy: {accuracy:.3f}")
    print(report)

    metrics = {
        "accuracy": float(accuracy),
        "labels": labels,
        "confusion_matrix": matrix.tolist(),
        "classification_report": report_dict,
        "confusion_matrix_artifact": matrix_artifact,
        "test_samples": len(y_test),
    }
    if metrics_path:
        metrics_path = Path(metrics_path)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def train_and_save_model(
    dataset_path=None,
    model_path=None,
    model_type="naive_bayes",
    test_size=0.2,
    metrics_path=None,
    confusion_matrix_path=None,
    max_features=50000,
    max_ngram=2,
):
    """Train from CSV or toy data and save model."""
    texts, labels = load_spam_dataset(dataset_path)
    X_train, X_test, y_train, y_test = split_dataset(texts, labels, test_size=test_size)
    bundle = train_classifier(
        X_train,
        y_train,
        model_type=model_type,
        max_features=max_features,
        ngram_range=(1, max_ngram),
    )
    model_path = Path(model_path or get_config()["spam_model_path"])
    if metrics_path is None:
        metrics_path = model_path.with_name("spam_metrics.json")
    if confusion_matrix_path is None:
        confusion_matrix_path = model_path.with_name("spam_confusion_matrix.png")
    metrics = evaluate_model(bundle, X_test, y_test, metrics_path=metrics_path, confusion_matrix_path=confusion_matrix_path)
    bundle["metrics"] = metrics
    save_model(bundle, model_path)
    return bundle


def parse_args():
    """Parse training CLI arguments."""
    parser = argparse.ArgumentParser(description="Train a TF-IDF spam classifier.")
    parser.add_argument("--dataset", default=None, help="CSV file or directory containing ham/spam emails.")
    parser.add_argument("--model", default=None, help="Output joblib model path.")
    parser.add_argument("--model-type", choices=("naive_bayes", "svm"), default="naive_bayes")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--metrics", default=None, help="Output JSON metrics path.")
    parser.add_argument("--confusion-matrix", default=None, help="Output confusion matrix image path.")
    parser.add_argument("--max-features", type=int, default=50000)
    parser.add_argument("--max-ngram", type=int, choices=(1, 2), default=2)
    return parser.parse_args()


def main():
    """CLI entry for python -m mailapp.spam.train_spam."""
    args = parse_args()
    load_config()
    model_path = args.model or get_config()["spam_model_path"]
    train_and_save_model(
        dataset_path=args.dataset,
        model_path=model_path,
        model_type=args.model_type,
        test_size=args.test_size,
        metrics_path=args.metrics,
        confusion_matrix_path=args.confusion_matrix,
        max_features=args.max_features,
        max_ngram=args.max_ngram,
    )


if __name__ == "__main__":
    main()
