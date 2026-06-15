"""Spam classifier interface with ML model fallback to keyword rules."""

from pathlib import Path
from time import time

import joblib
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC

from mailapp.config import get_config
from mailapp.spam.features import build_vectorizer, fit_transform_texts, transform_texts

SPAM_KEYWORDS = {"lottery", "winner", "free", "prize", "click", "money", "urgent", "win"}
_MODEL_CACHE = {"path": None, "mtime": None, "bundle": None}


def train_classifier(texts, labels, model_type="naive_bayes"):
    """Train a spam classifier and return a model bundle."""
    vectorizer = build_vectorizer()
    features = fit_transform_texts(vectorizer, texts)
    if model_type == "svm":
        classifier = LinearSVC()
    elif model_type == "naive_bayes":
        classifier = MultinomialNB()
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    classifier.fit(features, labels)
    return {
        "vectorizer": vectorizer,
        "classifier": classifier,
        "model_type": model_type,
        "trained_at": time(),
        "training_samples": len(texts),
    }


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
    _MODEL_CACHE.update(path=None, mtime=None, bundle=None)


def load_model(path):
    """Load a trained model bundle."""
    path = Path(path)
    mtime = path.stat().st_mtime_ns
    if _MODEL_CACHE["path"] == path and _MODEL_CACHE["mtime"] == mtime:
        return _MODEL_CACHE["bundle"]
    bundle = joblib.load(path)
    if not {"vectorizer", "classifier"}.issubset(bundle):
        raise ValueError("Invalid spam model bundle")
    _MODEL_CACHE.update(path=path, mtime=mtime, bundle=bundle)
    return bundle


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
        except (OSError, ValueError, KeyError):
            return keyword_spam_check(text)
    return keyword_spam_check(text)


def model_status():
    """Return model availability and metadata for the CLI/report."""
    path = _model_path()
    if not path.exists():
        return {"available": False, "path": str(path), "mode": "keyword-fallback"}
    bundle = load_model(path)
    return {
        "available": True,
        "path": str(path),
        "mode": bundle.get("model_type", "unknown"),
        "training_samples": bundle.get("training_samples"),
        "trained_at": bundle.get("trained_at"),
    }
