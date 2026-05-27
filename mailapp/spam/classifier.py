"""Spam classifier interface with ML model fallback to keyword rules."""

from pathlib import Path

import joblib
from sklearn.naive_bayes import MultinomialNB

from mailapp.config import get_config
from mailapp.spam.features import build_vectorizer, fit_transform_texts, transform_texts

SPAM_KEYWORDS = {"lottery", "winner", "free", "prize", "click", "money", "urgent", "win"}


def train_classifier(texts, labels, model_type="naive_bayes"):
    """Train a spam classifier and return a model bundle."""
    vectorizer = build_vectorizer()
    features = fit_transform_texts(vectorizer, texts)
    if model_type != "naive_bayes":
        # TODO: add SVM model selection.
        model_type = "naive_bayes"
    classifier = MultinomialNB()
    classifier.fit(features, labels)
    return {"vectorizer": vectorizer, "classifier": classifier, "model_type": model_type}


def _model_path():
    path = Path(get_config().get("spam_model_path", "data/models/spam_model.joblib"))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def predict_spam(text):
    """Predict spam for one text using saved model when available."""
    bundle = load_model(_model_path())
    features = transform_texts(bundle["vectorizer"], [text])
    return bundle["classifier"].predict(features)[0] == "spam"


def predict_batch(texts):
    """Predict labels for a list of texts using saved model."""
    bundle = load_model(_model_path())
    features = transform_texts(bundle["vectorizer"], texts)
    return list(bundle["classifier"].predict(features))


def save_model(model_bundle, path):
    """Save a trained model bundle."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, path)


def load_model(path):
    """Load a trained model bundle."""
    return joblib.load(Path(path))


def keyword_spam_check(text):
    """Keyword fallback spam detector."""
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in SPAM_KEYWORDS)


def is_spam(text):
    """Main spam interface used by the project pipeline."""
    path = _model_path()
    if path.exists():
        try:
            return bool(predict_spam(text))
        except Exception:
            # TODO: log model errors and expose a health check.
            return keyword_spam_check(text)
    return keyword_spam_check(text)
