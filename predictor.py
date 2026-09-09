"""
predictor.py - Loads the trained model/vectorizer once and classifies reviews.

The model and vectorizer are pickled by model/train_model.py (run offline).
This module loads them ONCE at import time (i.e. once when the Flask app
starts), not on every request - training/loading a model per-request would
be far too slow.
"""

import os
import pickle

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")

# Maps the raw dataset labels to the friendly labels shown in the UI.
LABEL_NAMES = {"OR": "Genuine", "CG": "Fake"}


class ModelNotTrainedError(RuntimeError):
    """Raised when model.pkl / vectorizer.pkl haven't been generated yet."""


def _load_pickle(path):
    if not os.path.exists(path):
        raise ModelNotTrainedError(
            f"Missing {path}. Run `python model/train_model.py` first to train "
            f"and save the model before starting the app."
        )
    with open(path, "rb") as f:
        return pickle.load(f)


_model = _load_pickle(MODEL_PATH)
_vectorizer = _load_pickle(VECTORIZER_PATH)


def predict_reviews_batch(texts):
    """
    Classify a list of reviews in one shot.

    Vectorizing and predicting all texts together (one sklearn call each)
    is much faster than calling predict_review() in a per-review loop -
    for a real scraped product with hundreds of reviews, that's hundreds of
    tiny transform() calls instead of one batched one.

    Returns a list of dicts, same order as `texts`, one per review:
        {
            "label": "Genuine" | "Fake",
            "raw_label": "OR" | "CG",
            "confidence": float in [0, 100]  # confidence in the predicted label
        }
    """
    if not texts:
        return []

    features = _vectorizer.transform(texts)

    raw_labels = _model.predict(features)
    probabilities = _model.predict_proba(features)
    classes = list(_model.classes_)

    results = []
    for raw_label, review_probabilities in zip(raw_labels, probabilities):
        # classes[] gives the column order matching predict_proba's columns,
        # so we look up the probability of whichever class was actually predicted.
        confidence = review_probabilities[classes.index(raw_label)] * 100
        results.append({
            "label": LABEL_NAMES[raw_label],
            "raw_label": raw_label,
            "confidence": round(float(confidence), 2),
        })
    return results


def predict_review(text):
    """Classify a single review's text. See predict_reviews_batch() for the shape returned."""
    return predict_reviews_batch([text])[0]
