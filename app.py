"""
TrustCheck - Flask app entry point.

Routes:
    GET  /         - input page (URL tab or paste/upload tab)
    POST /analyze  - runs the manual paste/CSV path fully (predict -> analyze
                     -> dashboard). URL scraping is added in a later step;
                     for now it degrades to asking the user to paste reviews.
"""

import io
import os

import pandas as pd
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from analyzer import build_dashboard_data, explain_review, get_default_intelligence
from predictor import predict_reviews_batch
from scraper import scrape_product_reviews

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = "dev-only-secret-key-not-for-production"  # only used to flash form errors


from urllib.parse import parse_qs, urlencode

class VercelPathMiddleware:
    """Ensure Vercel serverless functions route multi-page requests based on the actual requested URL."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get("QUERY_STRING", "")
        params = parse_qs(query_string)

        if "path" in params and params["path"][0]:
            raw_path = params["path"][0]
            environ["PATH_INFO"] = "/" + raw_path.lstrip("/")
            remaining_params = {k: v for k, v in params.items() if k != "path"}
            environ["QUERY_STRING"] = urlencode(remaining_params, doseq=True)
        elif not environ.get("PATH_INFO") or environ.get("PATH_INFO") in ("/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)


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


@app.route("/api/analyze-single", methods=["GET", "POST"])
@app.route("/analyze-single", methods=["GET", "POST"])
@app.route("/api/analyze_single", methods=["GET", "POST"])
@app.route("/api/analyze_single.py", methods=["GET", "POST"])
def api_analyze_single():
    """Instant reactive single-review analyzer endpoint."""
    data = request.get_json(silent=True) or request.form
    text = (data.get("text") or "").strip() if data else ""
    if not text:
        return jsonify({"error": "No review text provided."}), 400

    forensics = explain_review(text)
    return jsonify(forensics)


@app.route("/", methods=["GET"])
@app.route("/api/index", methods=["GET"])
@app.route("/api/index.py", methods=["GET"])
def index():
    """Simple AI SaaS Landing Page."""
    if request.is_json or "analyze-single" in request.path or "analyze_single" in request.path or "analyze-single" in request.headers.get("x-matched-path", ""):
        return api_analyze_single()
    intel_data = get_default_intelligence()
    return render_template("landing.html", intel=intel_data, intelligence=intel_data)


@app.route("/analyze", methods=["GET", "POST"])
@app.route("/workbench", methods=["GET", "POST"])
@app.route("/api/analyze", methods=["GET", "POST"])
@app.route("/api/analyze.py", methods=["GET", "POST"])
def analyze_page():
    """Review Analyzer Page (GET), or process batch reviews (POST)."""
    if request.is_json or "analyze-single" in request.path or "analyze_single" in request.path or "analyze-single" in request.headers.get("x-matched-path", ""):
        return api_analyze_single()
    if request.method == "POST":
        return analyze()
    intel_data = get_default_intelligence()
    return render_template("analyze.html", intel=intel_data, intelligence=intel_data)


@app.route("/intelligence", methods=["GET"])
@app.route("/threats", methods=["GET"])
@app.route("/technology", methods=["GET"])
@app.route("/how-it-works", methods=["GET"])
@app.route("/architecture", methods=["GET"])
def redirect_to_analyze():
    """Redirect removed complex pages cleanly to the analyzer."""
    return redirect(url_for("analyze_page"))


@app.route("/dashboard", methods=["GET"])
def dashboard_page():
    """Batch Audit Results View."""
    intel_data = get_default_intelligence()
    sample_reviews = [
        {
            "text": r["text"],
            "rating": r.get("rating"),
            "label": r.get("label", "Genuine"),
            "raw_label": "OR",
            "confidence": r.get("confidence", 90),
        }
        for r in intel_data["recent_reviews"]
    ]
    dashboard_data = build_dashboard_data(sample_reviews)
    return render_template("dashboard.html", data=dashboard_data, intelligence=intel_data)


def analyze():
    input_mode = request.form.get("input_mode", "manual")
    platform_avg_rating_override = None

    if input_mode == "url":
        product_url = request.form.get("product_url", "").strip()
        scrape_result = scrape_product_reviews(product_url)

        if not scrape_result["success"]:
            flash(scrape_result["error"], "warning")
            return redirect(url_for("analyze_page"))

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
                return redirect(url_for("analyze_page"))
        else:
            pasted_reviews = request.form.get("pasted_reviews", "")
            raw_reviews = parse_pasted_text(pasted_reviews)

    if not raw_reviews:
        flash("No reviews found - please paste some text or upload a CSV.", "danger")
        return redirect(url_for("analyze_page"))

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
    return render_template("dashboard.html", data=dashboard_data, intelligence=get_default_intelligence())


if __name__ == "__main__":
    app.run(debug=True)

