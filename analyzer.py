"""
analyzer.py - Turns a list of per-review predictions into dashboard stats.

Input: a list of dicts, one per review, each already carrying a prediction:
    {
        "text": str,
        "rating": int | None,     # star rating, if we have one
        "label": "Genuine" | "Fake",
        "raw_label": "OR" | "CG",
        "confidence": float,      # 0-100, confidence in the predicted label
    }

Output: a single dict with everything dashboard.html needs to render.
"""

import re
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# --- Trust Score formula -----------------------------------------------
# TRUST_SCORE = 100 - (pct_fake * avg_fake_confidence / 100)
#
# Reasoning (documented here so it can be explained in the viva):
#   - Start from a perfect score of 100.
#   - Subtract a penalty that grows with TWO things at once:
#       1) pct_fake       - how large a share of reviews look fake
#       2) avg_fake_conf  - how confidently the model believes those
#                           flagged reviews actually are fake (0-100,
#                           rescaled to 0-1 by dividing by 100)
#   - Multiplying the two means: a product with a few *weakly* suspected
#     fake reviews is barely penalized (low pct_fake AND/OR low
#     confidence), while a product with many *strongly* suspected fakes
#     is penalized close to the full pct_fake amount.
#   - If there are no fake reviews at all, the penalty term is 0 and the
#     score is a perfect 100.
#   - Score is clamped to [0, 100] and rounded to the nearest integer.
# -------------------------------------------------------------------------

RATING_BUCKETS = [1, 2, 3, 4, 5]

WORD_RE = re.compile(r"[a-zA-Z]{4,}")  # words of 4+ letters only - skips noise like "it", "so"
TOP_KEYWORD_COUNT = 8


def _round1(value):
    return round(value, 1)


def _top_keywords(review_group, top_n=TOP_KEYWORD_COUNT):
    """
    Most frequent non-stopword words (4+ letters) across a group of reviews.
    A quick, transparent stand-in for "what language pattern got these
    reviews flagged" - not the TF-IDF features the model actually used
    internally, but an easy-to-explain approximation for the dashboard.
    """
    counts = Counter()
    for review in review_group:
        words = (w.lower() for w in WORD_RE.findall(review["text"]))
        counts.update(w for w in words if w not in ENGLISH_STOP_WORDS)
    return counts.most_common(top_n)


def build_dashboard_data(reviews, platform_avg_rating_override=None):
    total = len(reviews)
    genuine = [r for r in reviews if r["label"] == "Genuine"]
    fake = [r for r in reviews if r["label"] == "Fake"]

    genuine_count = len(genuine)
    fake_count = len(fake)

    pct_genuine = _round1((genuine_count / total) * 100) if total else 0.0
    pct_fake = _round1((fake_count / total) * 100) if total else 0.0

    avg_fake_confidence = (
        sum(r["confidence"] for r in fake) / fake_count if fake_count else 0.0
    )
    trust_score = 100 - (pct_fake * avg_fake_confidence / 100)
    trust_score = int(round(max(0, min(100, trust_score))))

    # Platform average: the star average a shopper currently sees on the
    # product page (fakes and all). When we scraped the page directly, the
    # site's own displayed average (platform_avg_rating_override) is more
    # accurate than averaging just our scraped sample - use it when we have
    # it, otherwise fall back to the mean of whatever ratings we do have.
    # Genuine average = mean rating of only the reviews we believe are real.
    # The gap between the two is the "meaningful insight" the spec asks for.
    all_ratings = [r["rating"] for r in reviews if r["rating"] is not None]
    genuine_ratings = [r["rating"] for r in genuine if r["rating"] is not None]

    if platform_avg_rating_override is not None:
        platform_avg_rating = _round1(platform_avg_rating_override)
    else:
        platform_avg_rating = _round1(sum(all_ratings) / len(all_ratings)) if all_ratings else None
    avg_rating_genuine = _round1(sum(genuine_ratings) / len(genuine_ratings)) if genuine_ratings else None

    rating_distribution = {
        "genuine": [sum(1 for r in genuine if r["rating"] == star) for star in RATING_BUCKETS],
        "fake": [sum(1 for r in fake if r["rating"] == star) for star in RATING_BUCKETS],
    }

    most_suspicious = sorted(fake, key=lambda r: r["confidence"], reverse=True)[:5]

    top_keywords = {
        "genuine": _top_keywords(genuine),
        "fake": _top_keywords(fake),
    }

    return {
        "total": total,
        "genuine_count": genuine_count,
        "fake_count": fake_count,
        "pct_genuine": pct_genuine,
        "pct_fake": pct_fake,
        "trust_score": trust_score,
        "platform_avg_rating": platform_avg_rating,
        "avg_rating_genuine": avg_rating_genuine,
        "rating_distribution": rating_distribution,
        "rating_buckets": RATING_BUCKETS,
        "top_keywords": top_keywords,
        "most_suspicious": most_suspicious,
        "reviews": reviews,
    }
