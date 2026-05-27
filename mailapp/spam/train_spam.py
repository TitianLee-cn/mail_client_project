"""Train and save the spam classifier."""

from sklearn.metrics import accuracy_score

from mailapp.config import get_config, load_config
from mailapp.spam.classifier import save_model, train_classifier
from mailapp.spam.dataset import load_spam_dataset, split_dataset
from mailapp.spam.features import transform_texts


def evaluate_model(model_bundle, X_test, y_test):
    """Print and return model accuracy."""
    features = transform_texts(model_bundle["vectorizer"], X_test)
    predictions = model_bundle["classifier"].predict(features)
    accuracy = accuracy_score(y_test, predictions)
    print(f"accuracy: {accuracy:.3f}")
    return accuracy


def train_and_save_model(dataset_path=None, model_path=None):
    """Train from CSV or toy data and save model."""
    texts, labels = load_spam_dataset(dataset_path)
    X_train, X_test, y_train, y_test = split_dataset(texts, labels, test_size=0.5)
    bundle = train_classifier(X_train, y_train)
    evaluate_model(bundle, X_test, y_test)
    save_model(bundle, model_path or get_config()["spam_model_path"])
    return bundle


def main():
    """CLI entry for python -m mailapp.spam.train_spam."""
    load_config()
    train_and_save_model(model_path=get_config()["spam_model_path"])


if __name__ == "__main__":
    main()
