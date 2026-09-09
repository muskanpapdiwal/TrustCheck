"""
train_model.py - Offline training script for TrustCheck's fake-review classifier.

Run this manually whenever you want to (re)train the model:
    python model/train_model.py

It is NOT run on every web request - app.py just loads the pickled output
(model.pkl, vectorizer.pkl) at startup. See predictor.py.

WHAT IT DOES
------------
1. Loads the review dataset (see DATASET section below).
2. Splits it into train/test (80/20, stratified so both classes are
   represented proportionally in the test set).
3. Vectorizes review text with TF-IDF (unigrams + bigrams).
4. Trains TWO classifiers on the same features - Multinomial Naive Bayes and
   Logistic Regression - and prints accuracy/precision/recall/F1 for both on
   the held-out test split.
5. Keeps whichever model scored higher accuracy on the test split, and saves
   that model + the fitted vectorizer with pickle.

DATASET
-------
Expected file: model/data/fake_reviews_dataset.csv
Expected columns (matching the Kaggle "Fake Reviews Dataset" schema):
    text_    - the review text
    label    - "OR" (Original/genuine) or "CG" (Computer-Generated/fake)
    rating   - star rating (not used as a model feature - text only for now)
    category - product category (not used as a model feature)

If that file is not found, this script GENERATES A SMALL SYNTHETIC
PLACEHOLDER DATASET with the same column names/schema, so the full pipeline
(train -> save -> predict -> dashboard) works end-to-end today.

    IMPORTANT: the placeholder dataset is hand-written filler text, not real
    reviews. Swap in the real Kaggle dataset CSV at the path above and rerun
    this script before treating any reported accuracy as meaningful.
"""

import os
import pickle
import random

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(MODEL_DIR, "data", "fake_reviews_dataset.csv")
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")

RANDOM_STATE = 42


def generate_placeholder_dataset(path, n_per_class=150):
    """
    Build a small synthetic dataset with the same schema as the real Kaggle
    Fake Reviews Dataset (text_, label, rating, category), so the training
    pipeline can be exercised before the real dataset is available.

    Genuine (OR) templates are written to look like real customer feedback:
    specific details, mixed sentiment, minor complaints.

    Fake (CG) templates mimic the well-documented signature of computer-
    generated review spam: generic superlatives, heavy repetition, and
    excessive exclamation marks.
    """
    random.seed(RANDOM_STATE)

    products = [
        "phone case", "bluetooth earbuds", "kitchen blender", "yoga mat",
        "office chair", "laptop stand", "water bottle", "wireless mouse",
        "running shoes", "backpack", "desk lamp", "power bank", "air fryer",
        "coffee maker", "notebook", "camera tripod", "wall charger",
        "gaming keyboard", "face wash", "wrist watch",
    ]
    parts = ["hinge", "strap", "lid", "clip", "button", "casing", "handle"]
    reasons = ["home office", "college dorm", "daily commute", "gym bag", "kitchen"]

    genuine_templates = [
        "I've been using this {p} for about three weeks now and overall it "
        "holds up well, though the {part} feels a bit flimsy.",
        "Bought this {p} for my {reason} and it does the job, but the "
        "instructions were confusing at first.",
        "The {p} arrived a day late but works fine. Battery life is shorter "
        "than advertised, closer to a few hours less than claimed.",
        "Not bad for the price. The {p} is sturdy, though the color was "
        "slightly different from the photos online.",
        "My second {p} from this brand - the first one broke after a year, "
        "so hoping this one lasts longer.",
        "Works as expected. Setup took about ten minutes and the {p} has "
        "been reliable so far.",
        "Decent {p}, but customer support was slow to respond when I had a "
        "question about the warranty.",
        "I compared this {p} with a similar one from another brand and this "
        "one feels more solid, despite costing a bit more.",
        "The {p} is okay - does what it says, nothing special, but no "
        "complaints after two months of daily use.",
        "Had to return the first {p} because of a manufacturing defect, but "
        "the replacement works perfectly.",
        "Good {p} for the {reason}, though it's a little heavier than I "
        "expected from the listing photos.",
        "Three stars - the {p} works, but the {part} started squeaking "
        "after a couple of weeks.",
    ]

    fake_templates = [
        "This {p} is AMAZING!!! Best purchase ever, changed my life "
        "completely!!!",
        "Excellent product highly recommend to everyone amazing quality "
        "fast shipping perfect!!!",
        "Five stars!!! This {p} exceeded all my expectations, absolutely "
        "perfect in every way!!!",
        "Great great great, love love love this {p}, will buy again and "
        "again!!!",
        "Incredible value for money, this {p} is simply the best on the "
        "market, buy now!!!",
        "Wow just wow, this {p} is a game changer, everyone needs one, "
        "super amazing!!!",
        "Perfect perfect perfect, no flaws whatsoever, this {p} is pure "
        "perfection!!!",
        "Highly recommended product, super fast delivery, amazing seller, "
        "amazing {p}, five stars!!!",
        "Outstanding quality outstanding service outstanding {p}, best in "
        "class, must buy!!!",
        "This {p} is a total game changer!!! Amazing amazing amazing, "
        "worth every penny!!!",
        "Best {p} in the whole world, five stars, perfect, amazing, buy it "
        "right now!!!",
        "Super duper amazing {p}, exceeded expectations, will recommend to "
        "all my friends and family!!!",
    ]

    rows = []

    def fill(template):
        return template.format(
            p=random.choice(products),
            part=random.choice(parts),
            reason=random.choice(reasons),
        )

    for _ in range(n_per_class):
        rows.append({
            "text_": fill(random.choice(genuine_templates)),
            "label": "OR",
            "rating": random.choice([2, 3, 3, 4, 4, 5]),
            "category": "placeholder_category",
        })
        rows.append({
            "text_": fill(random.choice(fake_templates)),
            "label": "CG",
            "rating": random.choice([5, 5, 5, 1]),
            "category": "placeholder_category",
        })

    df = pd.DataFrame(rows).sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    print(f"[placeholder] No dataset found at {path}")
    print(f"[placeholder] Generated {len(df)} synthetic rows and saved them there instead.")
    print("[placeholder] Swap in the real Kaggle Fake Reviews Dataset and rerun this "
          "script before trusting the reported accuracy.\n")
    return df


def load_dataset():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
    else:
        df = generate_placeholder_dataset(DATA_PATH)

    df = df.dropna(subset=["text_", "label"])
    df["text_"] = df["text_"].astype(str)
    return df


def evaluate(name, model, X_test, y_test):
    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, predictions, average="binary", pos_label="CG"
    )
    print(f"--- {name} ---")
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision (fake/CG): {precision:.4f}")
    print(f"Recall    (fake/CG): {recall:.4f}")
    print(f"F1-score  (fake/CG): {f1:.4f}")
    print(classification_report(y_test, predictions))
    return accuracy


def main():
    df = load_dataset()
    print(f"Loaded {len(df)} labeled reviews "
          f"({(df['label'] == 'OR').sum()} genuine / {(df['label'] == 'CG').sum()} fake)\n")

    X_train_text, X_test_text, y_train, y_test = train_test_split(
        df["text_"], df["label"],
        test_size=0.2, random_state=RANDOM_STATE, stratify=df["label"],
    )

    # TF-IDF: unigrams + bigrams, drop very rare terms, cap vocabulary size
    # so the model stays small and fast to load.
    vectorizer = TfidfVectorizer(
        max_features=5000, ngram_range=(1, 2), stop_words="english", min_df=2,
    )
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    nb_model = MultinomialNB()
    nb_model.fit(X_train, y_train)
    nb_accuracy = evaluate("Multinomial Naive Bayes", nb_model, X_test, y_test)

    lr_model = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    lr_model.fit(X_train, y_train)
    lr_accuracy = evaluate("Logistic Regression", lr_model, X_test, y_test)

    if lr_accuracy >= nb_accuracy:
        best_model, best_name = lr_model, "Logistic Regression"
    else:
        best_model, best_name = nb_model, "Multinomial Naive Bayes"

    print(f"Winner: {best_name} (accuracy {max(nb_accuracy, lr_accuracy):.4f}) "
          f"- saving this one for the app to use.")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(best_model, f)
    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved vectorizer to {VECTORIZER_PATH}")


if __name__ == "__main__":
    main()
