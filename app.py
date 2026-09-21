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
    CSV upload: requires a `review_text` or `review` column (case-insensitive),
    with optional `rating`, `date`, `reviewer` columns. Returns None if no usable column.
    """
    raw_bytes = uploaded_file.read()
    df = pd.read_csv(io.BytesIO(raw_bytes))

    column_lookup = {col.lower(): col for col in df.columns}
    text_col = None
    for candidate in ["review_text", "review", "text", "body", "content", "reviews"]:
        if candidate in column_lookup:
            text_col = column_lookup[candidate]
            break

    if not text_col:
        return None

    rating_col = None
    for candidate in ["rating", "stars", "score"]:
        if candidate in column_lookup:
            rating_col = column_lookup[candidate]
            break

    date_col = column_lookup.get("date")
    reviewer_col = column_lookup.get("reviewer") or column_lookup.get("user")

    reviews = []
    for _, row in df.iterrows():
        text = str(row[text_col]).strip()
        if not text or text.lower() == "nan":
            continue
        rating = None
        if rating_col is not None:
            try:
                rating = int(float(row[rating_col]))
            except (ValueError, TypeError):
                rating = None

        date = str(row[date_col]).strip() if date_col and str(row[date_col]).lower() != "nan" else None
        reviewer = str(row[reviewer_col]).strip() if reviewer_col and str(row[reviewer_col]).lower() != "nan" else None

        item = {"text": text, "rating": rating}
        if date:
            item["date"] = date
        if reviewer:
            item["reviewer"] = reviewer
        reviews.append(item)
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
    """Main TrustCheck Application."""
    if "analyze-single" in request.path or "analyze_single" in request.path or "analyze-single" in request.headers.get("x-matched-path", ""):
        return api_analyze_single()
    intel_data = get_default_intelligence()
    return render_template("index.html", intel=intel_data, intelligence=intel_data)


@app.route("/api/default-intelligence", methods=["GET"])
def api_default_intelligence():
    """Return default benchmark telemetry data in JSON."""
    return jsonify(get_default_intelligence())


@app.route("/analyze", methods=["GET", "POST"])
@app.route("/workbench", methods=["GET", "POST"])
@app.route("/api/analyze", methods=["GET", "POST"])
@app.route("/api/analyze.py", methods=["GET", "POST"])
def analyze_page():
    """Review Analyzer Page (GET), or process batch reviews (POST)."""
    if "analyze-single" in request.path or "analyze_single" in request.path or "analyze-single" in request.headers.get("x-matched-path", ""):
        return api_analyze_single()
    if request.method == "POST":
        return analyze()
    intel_data = get_default_intelligence()
    return render_template("index.html", intel=intel_data, intelligence=intel_data)


@app.route("/intelligence", methods=["GET"])
@app.route("/threats", methods=["GET"])
@app.route("/technology", methods=["GET"])
@app.route("/how-it-works", methods=["GET"])
@app.route("/architecture", methods=["GET"])
def redirect_to_analyze():
    """Redirect removed complex pages cleanly to home."""
    return redirect(url_for("index"))


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
    return render_template("index.html", data=dashboard_data, intelligence=intel_data)


def analyze():
    is_api = (
        request.is_json
        or request.headers.get("Accept") == "application/json"
        or request.args.get("format") == "json"
        or (request.form and request.form.get("format") == "json")
    )

    input_mode = request.form.get("input_mode") if request.form else (request.get_json(silent=True) or {}).get("input_mode", "manual")
    platform_avg_rating_override = None

    if input_mode == "url":
        product_url = (request.form.get("product_url") if request.form else (request.get_json(silent=True) or {}).get("product_url", "")).strip()
        scrape_result = scrape_product_reviews(product_url)

        if not scrape_result["success"]:
            if is_api:
                return jsonify({"success": False, "error": scrape_result["error"]}), 400
            flash(scrape_result["error"], "warning")
            return redirect(url_for("analyze_page"))

        raw_reviews = scrape_result["reviews"]
        platform_avg_rating_override = scrape_result["platform_avg_rating"]
    else:
        uploaded_file = request.files.get("csv_file") if request.files else None

        if uploaded_file and uploaded_file.filename:
            raw_reviews = parse_csv_upload(uploaded_file)
            if raw_reviews is None:
                err_msg = "That CSV doesn't have a 'review' or 'review_text' column - please check the file and try again."
                if is_api:
                    return jsonify({"success": False, "error": err_msg}), 400
                flash(err_msg, "danger")
                return redirect(url_for("analyze_page"))
        else:
            pasted_reviews = request.form.get("pasted_reviews") if request.form else (request.get_json(silent=True) or {}).get("pasted_reviews", "")
            raw_reviews = parse_pasted_text(pasted_reviews)

    if not raw_reviews:
        err_msg = "No reviews found - please paste some text or upload a CSV."
        if is_api:
            return jsonify({"success": False, "error": err_msg}), 400
        flash(err_msg, "danger")
        return redirect(url_for("analyze_page"))

    # Classify all reviews in one batched vectorize+predict call
    predictions = predict_reviews_batch([raw["text"] for raw in raw_reviews])
    reviews = [
        {
            "text": raw["text"],
            "rating": raw["rating"],
            "date": raw.get("date"),
            "reviewer": raw.get("reviewer"),
            "label": prediction["label"],
            "raw_label": prediction["raw_label"],
            "confidence": prediction["confidence"],
        }
        for raw, prediction in zip(raw_reviews, predictions)
    ]

    dashboard_data = build_dashboard_data(reviews, platform_avg_rating_override)
    if is_api:
        return jsonify({
            "success": True,
            "data": dashboard_data,
            "intelligence": get_default_intelligence()
        })
    return render_template("index.html", data=dashboard_data, intelligence=get_default_intelligence())


if __name__ == "__main__":
    app.run(debug=True)

