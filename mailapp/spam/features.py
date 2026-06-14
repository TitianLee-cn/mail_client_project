"""Text feature extraction for spam classification."""

from sklearn.feature_extraction.text import TfidfVectorizer


def build_vectorizer(max_features=50000, ngram_range=(1, 2)):
    """Create a basic TF-IDF vectorizer."""
    return TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        max_features=max_features,
        ngram_range=ngram_range,
    )


def fit_transform_texts(vectorizer, texts):
    """Fit vectorizer and transform texts."""
    return vectorizer.fit_transform(texts)


def transform_texts(vectorizer, texts):
    """Transform texts with a fitted vectorizer."""
    return vectorizer.transform(texts)
