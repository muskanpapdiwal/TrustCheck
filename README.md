# TrustCheck

A fake review detection dashboard for e-commerce products. Paste in reviews
(or a CSV), or give it an Amazon/Flipkart product URL, and it classifies each
review as **Genuine** or **Fake** with a confidence score, then shows the
results on a dashboard.

BCA final-year project - built for a working, simple, well-organized system
rather than advanced architecture.

## Project structure

```
.
├── app.py               # Flask app + routes
├── scraper.py           # URL -> list of raw reviews (best-effort, graceful fallback)
├── predictor.py         # loads model, takes review text -> label + confidence
├── analyzer.py          # takes predictions -> aggregated dashboard stats
├── model/
│   ├── train_model.py   # offline training script (run manually, not per-request)
│   ├── model.pkl        # saved trained classifier
│   ├── vectorizer.pkl   # saved TF-IDF vectorizer
│   └── data/
│       └── fake_reviews_dataset.csv
├── templates/
│   ├── index.html       # input form (URL or paste/upload)
│   └── dashboard.html   # results dashboard
├── static/
│   ├── style.css        # custom UI styles
│   └── bg-network.js    # interactive canvas particle background
├── requirements.txt     # Python dependencies
└── README.md
```

## How to run it

```bash
# Clone the repository
git clone https://github.com/muskanpapdiwal/TrustCheck.git
cd TrustCheck

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# (Optional) Pre-trained models are included, but you can retrain anytime:
# python model/train_model.py

# Run the Flask app
python app.py
```

Then open `http://127.0.0.1:5000/` in a browser.

## How to retrain the model

```bash
python model/train_model.py
```

This script:

1. Looks for `model/data/fake_reviews_dataset.csv` with columns `text_`
   (review text) and `label` (`OR` = genuine/"Original Review", `CG` =
   fake/"Computer-Generated") - matching the Kaggle "Fake Reviews Dataset"
   schema. `rating` and `category` columns are also expected but not used as
   model features.
2. **If that file isn't there**, it generates a small synthetic placeholder
   dataset with the same column names so the pipeline still runs end-to-end.
   The placeholder text is hand-written filler, not real reviews - swap in
   the real Kaggle dataset CSV before trusting any reported accuracy.
3. Splits the data 80/20 (train/test, stratified).
4. Trains TF-IDF (unigrams + bigrams) + **Multinomial Naive Bayes**, and
   TF-IDF + **Logistic Regression**, on the same features.
5. Prints accuracy/precision/recall/F1 for both models on the held-out test
   split.
6. Saves whichever model scored higher accuracy to `model/model.pkl`, and
   the fitted vectorizer to `model/vectorizer.pkl`.

`app.py` loads `model.pkl`/`vectorizer.pkl` once at startup (via
`predictor.py`) - it does **not** retrain on every request, so restart the
Flask app after retraining for it to pick up a new model.

## Trust Score formula

Documented in `analyzer.py`:

```
TRUST_SCORE = 100 - (pct_fake * avg_fake_confidence / 100)
```

- Start from a perfect score of 100.
- Subtract a penalty that grows with **two things at once**: how large a
  share of reviews look fake (`pct_fake`), and how confidently the model
  believes those flagged reviews actually are fake (`avg_fake_confidence`,
  0-100, rescaled to 0-1). Multiplying the two means a product with a few
  *weakly* suspected fakes is barely penalized, while a product with many
  *strongly* suspected fakes is penalized close to the full `pct_fake`
  amount.
- If there are no fake reviews at all, the penalty is 0 and the score is a
  perfect 100.
- The result is clamped to `[0, 100]` and rounded to the nearest integer.

The dashboard also shows **average rating of genuine reviews only** next to
the **platform's displayed average rating** (mean of all reviews, fakes
included, or the site's own displayed average when scraped directly) - the
gap between the two is often the most telling signal that a product's
rating is inflated by fake reviews.

## Input modes

- **Product URL** (`scraper.py`): Amazon and Flipkart get dedicated
  CSS-selector parsers, with pagination (following `pageNumber=`/`page=`
  query params, capped at `MAX_REVIEW_PAGES`) to collect more than just the
  first page of reviews. Any other site is treated as "generic" and only
  scraped via embedded JSON-LD structured review data (`schema.org`
  Review/AggregateRating) - works on sites that publish it for SEO, empty
  otherwise. Every path tries `requests` + BeautifulSoup first; if that
  finds zero reviews (e.g. the page is JS-rendered), it falls back to a
  headless browser via `undetected-chromedriver` (patches away automation
  fingerprints plain Selenium leaves behind, so it gets past simple bot
  checks vanilla Selenium can't - though not stronger anti-bot services
  like Akamai/PerimeterX). If both fail for any reason - blocked,
  unsupported site, network error - the app shows a clear message and
  redirects to the manual input tab instead of crashing. Site markup and
  anti-bot measures change often, so this is best-effort, not guaranteed.
  Note: Amazon's dedicated reviews-listing page requires being signed in,
  so pagination there stops after the product page's public ~8 reviews.
- **Paste / CSV upload** (`app.py`): freeform pasted text (one review per
  line, no rating), or a CSV with a required `review_text` column and an
  optional `rating` column.

## Limitations

- The bundled placeholder training data is synthetic filler for wiring up
  the pipeline - retrain on the real Kaggle Fake Reviews Dataset (or another
  labeled review dataset) before treating predictions as meaningful.
- Scraping is best-effort; e-commerce sites actively try to block automated
  requests, and markup changes without notice. The manual paste/CSV path is
  the reliable fallback by design.
- No database/persistence in v1 - each request is processed in memory and
  results aren't saved. Add SQLite later if history is needed.
