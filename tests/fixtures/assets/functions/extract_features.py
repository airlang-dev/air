"""Function asset for extracting features from text."""


def extract_features(text):
    """Extract features from text, returning a dict."""
    words = text.split() if isinstance(text, str) else []
    return {
        "type": "Features",
        "word_count": len(words),
        "char_count": len(text) if isinstance(text, str) else 0,
    }
