"""Spam classifier interface with ML model fallback to keyword rules."""

from pathlib import Path

import joblib
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC

from mailapp.config import get_config
from mailapp.spam.features import build_vectorizer, fit_transform_texts, transform_texts

SPAM_KEYWORDS = {"lottery", "winner", "free", "prize", "click", "money", "urgent", "win"}
_MODEL_CACHE = {}


def train_classifier(texts, labels, model_type="naive_bayes", max_features=50000, ngram_range=(1, 2)):
    """Train a spam classifier and return a model bundle."""
    vectorizer = build_vectorizer(max_features=max_features, ngram_range=ngram_range)
    features = fit_transform_texts(vectorizer, texts)
    if model_type == "svm":
        classifier = LinearSVC()
    elif model_type == "naive_bayes":
        classifier = MultinomialNB()
    else:
        raise ValueError(f"Unsupported model_type: {model_type}")
    classifier.fit(features, labels)
    return {
        "vectorizer": vectorizer,
        "classifier": classifier,
        "model_type": model_type,
        "labels": sorted(set(labels)),
        "max_features": max_features,
        "ngram_range": ngram_range,
    }


def _model_path():
    path = Path(get_config().get("spam_model_path", "data/models/spam_model.joblib"))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def predict_spam(text):
    """Predict spam for one text using saved model when available."""
    bundle = load_model(_model_path(), cached=True)
    features = transform_texts(bundle["vectorizer"], [text])
    return bundle["classifier"].predict(features)[0] == "spam"


def predict_batch(texts):
    """Predict labels for a list of texts using saved model."""
    bundle = load_model(_model_path(), cached=True)
    features = transform_texts(bundle["vectorizer"], texts)
    return list(bundle["classifier"].predict(features))


def save_model(model_bundle, path):
    """Save a trained model bundle."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model_bundle, path)
    _MODEL_CACHE.pop(str(path.resolve()), None)


def load_model(path, cached=False):
    """Load a trained model bundle."""
    path = Path(path)
    cache_key = str(path.resolve())
    if cached and cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]
    bundle = joblib.load(path)
    if cached:
        _MODEL_CACHE[cache_key] = bundle
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
        except Exception:
            # TODO: log model errors and expose a health check.
            return keyword_spam_check(text)
    return keyword_spam_check(text)
