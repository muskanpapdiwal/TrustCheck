"""
TrustCheck - Flask app entry point.

Routes:
    GET  /         - input page (URL tab or paste/upload tab)
    POST /analyze  - runs the manual paste/CSV path fully (predict -> analyze
                     -> dashboard). URL scraping is added in a later step;
                     for now it degrades to asking the user to paste reviews.
"""

import io

import pandas as pd
from flask import Flask, flash, redirect, render_template, request, url_for

from analyzer import build_dashboard_data
from predictor import predict_reviews_batch
from scraper import scrape_product_reviews

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = "dev-only-secret-key-not-for-production"  # only used to flash form errors


def parse_pasted_text(pasted_reviews):
    """Freeform textarea input: one review per line, no rating info."""
    lines = [line.strip() for line in pasted_reviews.splitlines()]
    return [{"text": line, "rating": None} for line in lines if line]


def parse_csv_upload(uploaded_file):
    """
    CSV upload: requires a `review_text` column (case-insensitive), an
    optional `rating` column. Returns None if the file doesn't have a
    usable review_text column so the caller can show a friendly error.
    """
    raw_bytes = uploaded_file.read()
    df = pd.read_csv(io.BytesIO(raw_bytes))

    # Match "review_text" regardless of case, so "Review_Text" etc. also work.
    column_lookup = {col.lower(): col for col in df.columns}
    if "review_text" not in column_lookup:
        return None

    text_col = column_lookup["review_text"]
    rating_col = column_lookup.get("rating")

    reviews = []
    for _, row in df.iterrows():
        text = str(row[text_col]).strip()
        if not text or text.lower() == "nan":
            continue
        rating = None
        if rating_col is not None:
            try:
                rating = int(row[rating_col])
            except (ValueError, TypeError):
                rating = None
        reviews.append({"text": text, "rating": rating})
    return reviews


@app.route("/", methods=["GET"])
@app.route("/api/index", methods=["GET"])
@app.route("/api/index.py", methods=["GET"])
def index():
    """Show the input page: URL tab or paste/upload tab."""
    return render_template("index.html")


@app.route("/analyze", methods=["GET", "POST"])
@app.route("/api/index/analyze", methods=["GET", "POST"])
@app.route("/api/index.py/analyze", methods=["GET", "POST"])
def analyze():
    if request.method == "GET":
        return redirect(url_for("index"))

    input_mode = request.form.get("input_mode", "manual")
    platform_avg_rating_override = None

    if input_mode == "url":
        product_url = request.form.get("product_url", "").strip()
        scrape_result = scrape_product_reviews(product_url)

        if not scrape_result["success"]:
            # Scraping failed for any reason (blocked, JS-rendered, wrong
            # URL, network error, etc.) - degrade gracefully to the manual
            # input path instead of crashing or showing a blank page.
            flash(scrape_result["error"], "warning")
            return redirect(url_for("index"))

        raw_reviews = scrape_result["reviews"]
        platform_avg_rating_override = scrape_result["platform_avg_rating"]
    else:
        uploaded_file = request.files.get("csv_file")

        if uploaded_file and uploaded_file.filename:
            raw_reviews = parse_csv_upload(uploaded_file)
            if raw_reviews is None:
                flash(
                    "That CSV doesn't have a 'review_text' column - please check "
                    "the file and try again.",
                    "danger",
                )
                return redirect(url_for("index"))
        else:
            pasted_reviews = request.form.get("pasted_reviews", "")
            raw_reviews = parse_pasted_text(pasted_reviews)

    if not raw_reviews:
        flash("No reviews found - please paste some text or upload a CSV.", "danger")
        return redirect(url_for("index"))

    # Classify all reviews in one batched vectorize+predict call rather than
    # looping predict_review() per review - much faster for large review sets.
    predictions = predict_reviews_batch([raw["text"] for raw in raw_reviews])
    reviews = [
        {
            "text": raw["text"],
            "rating": raw["rating"],
            "label": prediction["label"],
            "raw_label": prediction["raw_label"],
            "confidence": prediction["confidence"],
        }
        for raw, prediction in zip(raw_reviews, predictions)
    ]

    dashboard_data = build_dashboard_data(reviews, platform_avg_rating_override)
    return render_template("dashboard.html", data=dashboard_data)


if __name__ == "__main__":
    app.run(debug=True)
