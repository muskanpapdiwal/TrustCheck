"""
scraper.py - Best-effort review scraping for product URLs.

Amazon and Flipkart get dedicated CSS-selector parsers (their markup is
common enough to be worth hand-targeting). Any OTHER site is treated as
"generic": we don't know its markup, so we only look for embedded JSON-LD
structured review data (schema.org Review/AggregateRating) - many
e-commerce platforms publish this for SEO regardless of how their visible
HTML is built, so this works on plenty of sites without a dedicated parser.
Sites that don't publish it come back with zero reviews and fall through to
the manual paste/CSV path, same as a fully blocked Amazon/Flipkart request.

Scraping live e-commerce sites is inherently fragile: markup changes often,
pages may be JS-rendered, and bot-detection frequently blocks plain HTTP
requests. This module is written defensively for that reality:

    1. Try `requests` + BeautifulSoup first (fast, no browser needed), with
       a couple of retries under different realistic browser headers.
       Within that, prefer any embedded JSON-LD structured review data
       (schema.org Review/AggregateRating) over scraping visible HTML,
       since structured data survives markup/class-name changes that break
       CSS-selector scraping.
    2. If that finds zero reviews, fall back to a headless browser driven by
       undetected-chromedriver (a Selenium wrapper that patches away the
       automation fingerprints plain Selenium leaves behind, e.g. the
       navigator.webdriver flag and injected `cdc_` variables that many
       anti-bot scripts check for) - handles JS-rendered review sections
       and gets past simple bot checks a plain HTTP request can't.
    3. If BOTH fail for any reason, return an empty result with a reason -
       NEVER raise an exception up to the caller. app.py treats an empty
       result as "scraping failed" and falls back to the manual paste/CSV
       input path, per the project spec.

PAGINATION: a single product page only shows a handful of reviews (Amazon's
product page shows ~8 "top reviews"; Flipkart's reviews page shows ~10 per
page). To get a representative sample rather than just page 1, the Amazon
and Flipkart paths follow `pageNumber=` / `page=` query params up to
MAX_REVIEW_PAGES pages, stopping early once a page adds no new reviews
(end of pagination, or the site just re-serves the last page past the end).
Generic (non-Amazon/Flipkart) sites have no known pagination convention, so
only the single page given is scraped.

This is a best-effort scraper for a student project demo, not a production
scraping pipeline - site structure changes or anti-bot measures can break it
at any time, which is exactly why the manual fallback path exists.
"""

import json
import os
import re
import subprocess
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 10
RETRY_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 1.5

# How many review-listing pages to follow per product. Amazon/Flipkart show
# roughly 8-10 reviews per page, so 10 pages is ~80-100 reviews - enough for
# a meaningful sample without hammering the site or making a single analyze
# request take forever.
MAX_REVIEW_PAGES = 10

# Rotate between a couple of realistic desktop browser fingerprints across
# retries - some sites block on the first request from a given UA/header
# combination but allow the next.
BROWSER_PROFILES = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
            "Gecko/20100101 Firefox/126.0"
        ),
        "sec-ch-ua": None,
    },
]

COMMON_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
    "DNT": "1",
}

# Phrases e-commerce sites show on their bot-check / CAPTCHA interstitial
# pages, used to tell "we got blocked" apart from "page structure changed".
BOT_BLOCK_SIGNATURES = [
    "enter the characters you see",
    "robot check",
    "captcha",
    "unusual traffic",
    "access denied",
    "automated access",
    "verify you are a human",
    "pardon the interruption",
]


def detect_platform(url):
    if "amazon." in url:
        return "amazon"
    if "flipkart." in url:
        return "flipkart"
    # Any other site: no dedicated parser, but _parse_html() still tries
    # generic JSON-LD structured review data on it before giving up.
    return "generic"


def _amazon_review_page_url(url, page_num):
    """
    Amazon review pagination lives at /product-reviews/{ASIN}/?pageNumber=N -
    NOT on the plain /dp/{ASIN} product page. Extract the ASIN regardless of
    which URL shape was given (dp, gp/product, or an existing
    product-reviews link) and rebuild the reviews-listing URL for this page.
    """
    match = re.search(r"/(?:dp|gp/product|product-reviews)/([A-Za-z0-9]{10})", url)
    if not match:
        return None
    asin = match.group(1)
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/product-reviews/{asin}/?pageNumber={page_num}"


def _flipkart_review_page_url(url, page_num):
    """
    Flipkart paginates reviews via ?page=N on a /product-reviews/{id} path.
    A plain product page uses /p/{id} instead - swap that segment for
    /product-reviews/{id}, keeping the pid query param either way.
    """
    parsed = urlparse(url)
    path = parsed.path
    if "/product-reviews/" not in path:
        if "/p/" in path:
            path = path.replace("/p/", "/product-reviews/", 1)
        else:
            return None
    query_params = parse_qs(parsed.query)
    query_params["page"] = [str(page_num)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, path, "", new_query, ""))


def _review_page_url(platform, url, page_num):
    if platform == "amazon":
        return _amazon_review_page_url(url, page_num)
    if platform == "flipkart":
        return _flipkart_review_page_url(url, page_num)
    return None


def _looks_bot_blocked(html_text):
    lowered = html_text.lower()
    return any(signature in lowered for signature in BOT_BLOCK_SIGNATURES)


def _extract_rating_from_text(text):
    """Pulls a star rating like '4.0 out of 5 stars' or '4/5' out of text."""
    if not text:
        return None
    match = re.search(r"([1-5](?:\.\d)?)\s*(?:out of 5|/5|stars)", text, re.IGNORECASE)
    if match:
        try:
            return round(float(match.group(1)))
        except ValueError:
            return None
    return None


def _parse_json_ld_reviews(soup):
    """
    Look for schema.org Product/Review structured data embedded in
    <script type="application/ld+json"> tags. Many product pages carry this
    for SEO regardless of how the visible HTML is built, so it survives
    class-name/markup churn that breaks CSS-selector scraping.
    """
    reviews = []
    platform_avg_rating = None

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue

            aggregate = candidate.get("aggregateRating")
            if isinstance(aggregate, dict) and aggregate.get("ratingValue"):
                platform_avg_rating = _extract_rating_from_text(str(aggregate["ratingValue"]) + " out of 5")

            raw_reviews = candidate.get("review")
            if raw_reviews is None:
                continue
            raw_reviews = raw_reviews if isinstance(raw_reviews, list) else [raw_reviews]

            for raw_review in raw_reviews:
                if not isinstance(raw_review, dict):
                    continue
                text = raw_review.get("reviewBody") or raw_review.get("description")
                if not text:
                    continue
                rating = None
                rating_obj = raw_review.get("reviewRating")
                if isinstance(rating_obj, dict) and rating_obj.get("ratingValue"):
                    rating = _extract_rating_from_text(str(rating_obj["ratingValue"]) + " out of 5")
                reviews.append({"text": text.strip(), "rating": rating})

    return reviews, platform_avg_rating


def _parse_amazon(soup):
    reviews = []
    for block in soup.select('div[data-hook="review"]'):
        # Amazon has used both "reviewText" (current) and "review-body"
        # (older) as the data-hook for the review text container - try both.
        body = block.select_one('div[data-hook="reviewText"], span[data-hook="review-body"]')
        rating_el = block.select_one('i[data-hook="review-star-rating"], i[data-hook="cmps-review-star-rating"]')
        text = body.get_text(strip=True, separator=" ") if body else None
        if not text:
            continue
        reviews.append({
            "text": text,
            "rating": _extract_rating_from_text(rating_el.get_text() if rating_el else None),
        })

    avg_rating_el = soup.select_one('span[data-hook="rating-out-of-text"], i[data-hook="average-star-rating"]')
    platform_avg_rating = _extract_rating_from_text(avg_rating_el.get_text() if avg_rating_el else None)
    return reviews, platform_avg_rating


RATING_TOKEN_RE = re.compile(r"^[1-5](\.\d)?$")


def _parse_flipkart(soup):
    """
    Flipkart's current frontend is built on an atomic/utility CSS-in-JS
    system (class names like "css-1jxf684" are hashed per style, not
    per-component), so there are no stable semantic class names the way
    older sites (or Amazon's data-hook attributes) have. Instead of
    matching a specific class name, this:

      1. Finds review-text nodes by length/shape (Flipkart's review-body
         class HAS been observed as "css-1jxf684", tried first since it's
         cheap and precise when it still matches).
      2. Falls back to any reasonably long text span if that class is gone.
      3. For each review's rating, climbs from the text node up through
         its ancestors until it finds one whose text contains a lone
         digit/decimal token (e.g. "4.0") - this is the review's own
         rating badge, scoped to just that review's container so it
         doesn't pick up a neighboring review's rating or the page-wide
         rating histogram.
    """
    reviews = []
    seen_texts = set()

    text_nodes = soup.select("span.css-1jxf684")
    if not text_nodes:
        # Class name may have changed - fall back to any leaf span/div whose
        # OWN (non-nested) text looks like a real review sentence, rather
        # than a big wrapper that just concatenates lots of child text.
        text_nodes = []
        for el in soup.find_all(["span", "div", "p"]):
            if el.find_all(["div", "span"]):
                continue  # not a leaf node
            direct_text = "".join(el.find_all(string=True, recursive=False)).strip()
            if len(direct_text) > 40:
                text_nodes.append(el)

    for text_el in text_nodes:
        text = text_el.get_text(strip=True, separator=" ")
        if not text or len(text) < 15 or text in seen_texts:
            continue

        rating = None
        ancestor = text_el
        for _ in range(8):
            ancestor = ancestor.parent
            if ancestor is None:
                break
            token = ancestor.find(string=RATING_TOKEN_RE)
            if token:
                rating = _extract_rating_from_text(str(token).strip() + " out of 5")
                break

        seen_texts.add(text)
        reviews.append({"text": text, "rating": rating})

    # The page-wide average rating isn't reliably extractable as plain text
    # on Flipkart's current layout - analyzer.py falls back to averaging
    # whatever per-review ratings we did find when this is None.
    platform_avg_rating = None
    return reviews, platform_avg_rating


def _parse_html(soup, platform):
    # Structured data first - most resilient to markup changes.
    reviews, platform_avg_rating = _parse_json_ld_reviews(soup)
    if reviews:
        return reviews, platform_avg_rating

    # Fall back to platform-specific CSS-selector scraping.
    if platform == "amazon":
        return _parse_amazon(soup)
    if platform == "flipkart":
        return _parse_flipkart(soup)
    return [], None


def _fetch_page_html(url):
    """
    Fetch one URL with retries across browser profiles/UAs.
    Returns (html_text, blocked). html_text is None if every attempt failed
    outright (network error, 5xx, or a bot-check page every time).
    """
    was_blocked = False

    for attempt in range(RETRY_ATTEMPTS):
        profile = BROWSER_PROFILES[attempt % len(BROWSER_PROFILES)]
        headers = {**COMMON_HEADERS, "User-Agent": profile["User-Agent"]}
        if profile.get("sec-ch-ua"):
            headers["sec-ch-ua"] = profile["sec-ch-ua"]

        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
            continue

        response.raise_for_status()

        if _looks_bot_blocked(response.text):
            was_blocked = True
            time.sleep(RETRY_BACKOFF_SECONDS)
            continue

        return response.text, False

    return None, was_blocked


def _scrape_with_requests(url, platform):
    """
    Walks review-listing pages (see PAGINATION note at the top of this file)
    up to MAX_REVIEW_PAGES, accumulating reviews and de-duplicating by text.

    Page 1 always uses the URL exactly as given - on Amazon specifically,
    the dedicated /product-reviews/ listing requires being signed in, while
    the plain product page's inline "top reviews" are public. Only pages 2+
    use the constructed pagination URL; if that page turns out to need a
    login too, it will simply parse to 0 reviews and pagination stops there
    without losing what page 1 already found.

    Returns (reviews, platform_avg_rating, blocked). `blocked` is True only
    when we got NO reviews at all and at least one page looked bot-blocked,
    so the caller can report a more specific reason than "found nothing".
    """
    all_reviews = []
    seen_texts = set()
    platform_avg_rating = None
    ever_blocked = False

    for page_num in range(1, MAX_REVIEW_PAGES + 1):
        if page_num == 1:
            page_url = url
        else:
            page_url = _review_page_url(platform, url, page_num)
            if page_url is None:
                break  # can't rebuild a pagination URL for this platform/URL shape

        html_text, blocked = _fetch_page_html(page_url)
        ever_blocked = ever_blocked or blocked
        if html_text is None:
            break  # this page failed outright - stop rather than guess further pages exist

        soup = BeautifulSoup(html_text, "html.parser")
        reviews, avg = _parse_html(soup, platform)
        if avg is not None:
            platform_avg_rating = avg

        new_reviews = [r for r in reviews if r["text"] not in seen_texts]
        if not new_reviews:
            break  # nothing new on this page - reached the end of pagination (or a login wall)

        seen_texts.update(r["text"] for r in new_reviews)
        all_reviews.extend(new_reviews)

    blocked_with_nothing = ever_blocked and not all_reviews
    return all_reviews, platform_avg_rating, blocked_with_nothing


CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def _installed_chrome_major_version():
    """
    undetected-chromedriver needs to know the installed Chrome's major
    version to fetch a matching driver - left to guess, it can grab a
    driver newer than the actually-installed browser (Chrome auto-updates
    silently) and fail to connect at all. Reads the version from the
    browser's own file metadata via PowerShell so this stays correct as
    Chrome updates, rather than hardcoding a version number that goes
    stale. Returns None (letting uc fall back to its own detection) if it
    can't be determined for any reason.
    """
    chrome_path = next((p for p in CHROME_PATHS if os.path.exists(p)), None)
    if chrome_path is None:
        return None
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"(Get-Item '{chrome_path}').VersionInfo.ProductVersion"],
            capture_output=True, text=True, timeout=10,
        )
        return int(result.stdout.strip().split(".")[0])
    except Exception:
        return None


def _scrape_with_selenium(url, platform):
    """
    Fallback for JS-rendered pages (or simple bot checks) that a plain HTTP
    request can't get past. Uses undetected-chromedriver instead of plain
    Selenium - it patches away the automation fingerprints (the
    navigator.webdriver flag, injected `cdc_` variables, etc.) that many
    anti-bot scripts specifically check for, so it gets past checks vanilla
    Selenium doesn't. Imports it lazily so the rest of the app works fine
    even if it or a Chrome install isn't available - any failure here just
    means "no reviews found", handled by the caller.

    Paginates the same way _scrape_with_requests does (see PAGINATION note
    at the top of this file), just loading each page in a real browser.
    """
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument(f"user-agent={BROWSER_PROFILES[0]['User-Agent']}")

    all_reviews = []
    seen_texts = set()
    platform_avg_rating = None

    # Note: undetected-chromedriver has a known cosmetic-only issue on
    # Windows where its __del__ finalizer re-attempts cleanup after
    # driver.quit() already succeeded, printing a harmless "handle is
    # invalid" traceback to stderr. It doesn't affect the reviews already
    # returned below.
    driver = uc.Chrome(options=options, version_main=_installed_chrome_major_version())
    try:
        driver.set_page_load_timeout(REQUEST_TIMEOUT * 2)

        for page_num in range(1, MAX_REVIEW_PAGES + 1):
            # Page 1 uses the URL as given (public on Amazon); only later
            # pages switch to the constructed pagination URL - see
            # _scrape_with_requests for why.
            if page_num == 1:
                page_url = url
            else:
                page_url = _review_page_url(platform, url, page_num)
                if page_url is None:
                    break
            driver.get(page_url)
            time.sleep(2)  # let lazy-loaded review sections render
            soup = BeautifulSoup(driver.page_source, "html.parser")

            reviews, avg = _parse_html(soup, platform)
            if avg is not None:
                platform_avg_rating = avg

            new_reviews = [r for r in reviews if r["text"] not in seen_texts]
            if not new_reviews:
                break

            seen_texts.update(r["text"] for r in new_reviews)
            all_reviews.extend(new_reviews)
    finally:
        driver.quit()

    return all_reviews, platform_avg_rating


def scrape_product_reviews(url):
    """
    Attempt to scrape reviews for a product URL.

    Always returns a dict, never raises:
        {
            "success": bool,
            "reviews": [{"text": str, "rating": int|None}, ...],
            "platform_avg_rating": float | None,
            "error": str | None,   # human-readable reason when success=False
        }
    """
    platform = detect_platform(url)

    try:
        reviews, platform_avg_rating, blocked = _scrape_with_requests(url, platform)
    except Exception:
        reviews, platform_avg_rating, blocked = [], None, False

    if not reviews:
        try:
            reviews, platform_avg_rating = _scrape_with_selenium(url, platform)
        except Exception:
            reviews, platform_avg_rating = [], None

    if not reviews:
        if blocked:
            error = (
                "This site blocked the automated request with a bot-check/CAPTCHA "
                "page. Please paste the reviews instead."
            )
        else:
            error = (
                "Couldn't fetch reviews automatically for this URL - the page "
                "structure wasn't recognized, or it may be blocking automated "
                "requests. Please paste the reviews instead."
            )
        return {
            "success": False,
            "reviews": [],
            "platform_avg_rating": None,
            "error": error,
        }

    return {
        "success": True,
        "reviews": reviews,
        "platform_avg_rating": platform_avg_rating,
        "error": None,
    }
