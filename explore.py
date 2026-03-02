"""
explore.py — LLM-Powered URL Discovery & Classification
=========================================================
Phase 1: Crawls outward from the seed pages in capture.py's URLS dict,
         extracting external links and deduplicating by domain.
Phase 2: Screenshots each candidate URL using headless Chromium.
Phase 3: Sends each screenshot to Groq's Llama 3.2 Vision API, which
         classifies it into one of the four ethical design intent categories.

Output:
  dataset_explored/<category>/*.png
  explore_log.csv

Requirements:
    pip install groq
    set GROQ_API_KEY=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   (Windows CMD)
    python explore.py
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    from groq import Groq
except ImportError:
    print("ERROR: 'groq' package not installed. Run: pip install groq")
    sys.exit(1)

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

try:
    from capture import URLS as SEED_URLS
except ImportError:
    print("ERROR: capture.py not found. Place explore.py in the same directory.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

MAX_PER_CATEGORY = 15         # balanced cap per category
OUTPUT_DIR      = "dataset_explored"
LOG_FILE        = "explore_log.csv"
VIEWPORT_WIDTH  = 1280
VIEWPORT_HEIGHT = 800
POST_LOAD_DELAY = 5          # seconds — lets cookie banners / modals appear
NAV_TIMEOUT     = 30_000     # milliseconds — max wait per page load

# Hub pages whose outbound links are representative of each category.
# Each list contains 4-5 pages known to link outward to many similar sites.
DISCOVERY_HUBS: dict[str, list[str]] = {
    "1_Extractive": [
        "https://www.producthunt.com/",          # SaaS/app launches — heavy CTAs
        "https://appsumo.com/",                  # deal site — high commercial density
        "https://www.g2.com/",                   # software review/conversion site
        "https://www.capterra.com/",             # software directory
    ],
    "2_Persuasive": [
        "https://www.indiehackers.com/",         # startup stories — clean conversion
        "https://www.ycombinator.com/companies", # YC company directory
        "https://webflow.com/made-in-webflow",   # curated design showcase
        "https://www.crunchbase.com/",           # startup/company profiles
    ],
    "3_Neutral": [
        "https://news.ycombinator.com/",         # Hacker News — link aggregator
        "https://curlie.org/",                   # Open Directory Project successor
        "https://en.wikipedia.org/wiki/Portal:Technology", # Wikipedia outlinks
        "https://www.dmoz-odp.org/",             # web directory
    ],
    "4_Grounding": [
        "https://www.are.na/",                   # indie web / research boards
        "https://indieweb.org/",                 # personal site community, lots of blogrolls
        "https://wiby.me/",                      # curated indie/retro web index
        "https://www.kickscondor.com/",          # link curator, grounding-heavy
    ],
}

GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

SOCIAL_MEDIA_DOMAINS = {
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "linkedin.com", "youtube.com", "tiktok.com", "snapchat.com",
    "pinterest.com", "reddit.com", "tumblr.com", "twitch.tv",
    "twitch.com", "threads.net", "bsky.app", "mastodon.social",
}

CDN_PATTERNS = re.compile(
    r"(cdn\.|assets\.|static\.|media\.|img\.|images\.|fonts\.|"
    r"\.css($|\?)|\.js($|\?)|\.png($|\?)|\.jpg($|\?)|\.jpeg($|\?)|"
    r"\.gif($|\?)|\.svg($|\?)|\.ico($|\?)|\.woff|\.ttf|\.eot|"
    r"\.map($|\?)|\.xml($|\?)|\.json($|\?)|\.pdf($|\?))",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# CLAUDE VISION SYSTEM PROMPT
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert web interface design analyst specializing in ethical design intent. \
Your task is to classify a web interface screenshot into exactly one of the four categories below.

## Categories

### 1_Extractive
Works against user interests. Characterized by: high call-to-action (CTA) density, dark patterns, \
aggressive pop-ups or overlays, autoplay media, scarcity/countdown manipulation ("only 3 left", \
"ends in 10 minutes"), heavy tracker infrastructure, infinite scroll with no endpoint, sticky \
headers advertising purchase, notification permission prompts, or interruptive subscription walls. \
Example sites: Amazon, Facebook, Shein, Temu, DailyMail, TikTok, Slotomania, Adobe.

### 2_Persuasive
Honestly moves users toward a conversion action. Characterized by: single clear CTA above the fold, \
social proof elements (testimonials, press logos, star ratings, user counts), narrative scroll with \
a deliberate visual endpoint, moderate analytics, strong visual hierarchy that serves comprehension, \
clean typographic hierarchy. \
Example sites: Notion, Figma, GitHub, Patagonia, Discord, Headspace, Allbirds, Khan Academy.

### 3_Neutral
Helps users complete a task and leave. Characterized by: prominent search input as primary affordance, \
dense information architecture, high navigation link count, minimal or no CTAs, low or no tracker \
scripts, no persistent sticky overlays, database or utility feel, fast-loading, reference-oriented. \
Example sites: Wikipedia, MDN Web Docs, Craigslist, archive.org, USPS, USA.gov, W3Schools, iFixit.

### 4_Grounding
Leaves users present, informed, or at rest. Characterized by: long-form editorial text, generous \
whitespace and line-height, no or minimal CTAs, no manipulation patterns, considered serif or humanist \
typography, deliberate absence of infinite scroll, low saturation color palette, no autoplay or \
notifications, reading-focused layout, may have a table of contents. \
Example sites: Gwern.net, Craig Mod, Solar Low-Tech Magazine, Pudding.cool, Are.na, Maggieappleton.com.

## Response Format

Respond with ONLY a valid JSON object — no markdown, no explanation outside the JSON:

{
  "category": "<one of: 1_Extractive | 2_Persuasive | 3_Neutral | 4_Grounding>",
  "confidence": "<one of: high | medium | low>",
  "reasoning": "<one sentence explaining the single most decisive visual feature you observed>"
}
"""

VALID_CATEGORIES = {"1_Extractive", "2_Persuasive", "3_Neutral", "4_Grounding"}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def domain_from_url(url: str) -> str:
    """Extract a filesystem-safe domain name from a URL."""
    hostname = urlparse(url).hostname or "unknown"
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname.replace(".", "_")


def get_seed_domains() -> set[str]:
    """Return the set of domains already in capture.URLS (exclusion list)."""
    domains: set[str] = set()
    for url_list in SEED_URLS.values():
        for url in url_list:
            parsed = urlparse(url)
            host = parsed.hostname or ""
            if host.startswith("www."):
                host = host[4:]
            domains.add(host)
    return domains


def _normalize_domain(hostname: str) -> str:
    host = hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def extract_external_links(page, seed_url: str, seen_domains: set[str]) -> list[str]:
    """
    Extract external links from the currently loaded page, apply all filters,
    and return a list of candidate root URLs not yet in seen_domains.
    """
    seed_domain = _normalize_domain(urlparse(seed_url).hostname or "")

    try:
        hrefs: list[str] = page.evaluate(
            "Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
        )
    except Exception:
        return []

    candidates: list[str] = []
    candidate_domains: set[str] = set()

    for href in hrefs:
        parsed = urlparse(href)

        # 1. Scheme must be http or https
        if parsed.scheme not in ("http", "https"):
            continue

        # 2. Hostname must exist
        hostname = parsed.hostname
        if not hostname:
            continue

        candidate_domain = _normalize_domain(hostname)

        # 3. Skip same-domain (internal) links
        if candidate_domain == seed_domain:
            continue

        # 4. Skip domains already in capture.URLS or already seen (including subdomains)
        if any(candidate_domain == d or candidate_domain.endswith("." + d) for d in seen_domains):
            continue

        # 5. Skip social media domains (including subdomains)
        if any(social in candidate_domain for social in SOCIAL_MEDIA_DOMAINS):
            continue

        # 6. Skip CDN/resource URLs
        if CDN_PATTERNS.search(href):
            continue

        # 7. Skip deeply nested paths (depth > 2)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) > 2:
            continue

        # 8. Skip pure fragment anchors (resolve to same page)
        if parsed.fragment and not parsed.path and not parsed.netloc:
            continue

        # 9. Canonicalize to root
        root_url = f"{parsed.scheme}://{parsed.netloc}/"

        # 10. Deduplicate by domain within this batch
        if candidate_domain in candidate_domains:
            continue

        candidates.append(root_url)
        candidate_domains.add(candidate_domain)

    return candidates


# ---------------------------------------------------------------------------
# PHASE 1: CRAWL SEEDS
# ---------------------------------------------------------------------------

def crawl_hubs(browser, known_domains: set[str]) -> list[tuple[str, str]]:
    """
    Visit each hub page in DISCOVERY_HUBS, extract external links, and
    return a balanced list of (category_hint, url) tuples capped at
    MAX_PER_CATEGORY per category.
    """
    seen_domains = set(known_domains)
    # category_hint -> list of root URLs found so far for that category
    buckets: dict[str, list[str]] = {cat: [] for cat in DISCOVERY_HUBS}

    total_hubs = sum(len(v) for v in DISCOVERY_HUBS.values())
    hub_idx = 0

    for category, hub_urls in DISCOVERY_HUBS.items():
        for hub_url in hub_urls:
            hub_idx += 1
            if len(buckets[category]) >= MAX_PER_CATEGORY:
                break

            print(f"  [HUB {hub_idx}/{total_hubs}] {category} | {hub_url}")

            page = browser.new_page(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
            )
            page.set_default_navigation_timeout(NAV_TIMEOUT)

            try:
                page.goto(hub_url, wait_until="networkidle")
                links = extract_external_links(page, hub_url, seen_domains)
                for link in links:
                    if len(buckets[category]) >= MAX_PER_CATEGORY:
                        break
                    parsed = urlparse(link)
                    domain = _normalize_domain(parsed.hostname or "")
                    if domain and domain not in seen_domains:
                        buckets[category].append(link)
                        seen_domains.add(domain)
                        print(f"    [FOUND] {link}")
            except PlaywrightTimeoutError:
                print(f"    !! TIMEOUT on hub")
            except Exception as exc:
                print(f"    !! FAILED on hub: {exc}")
            finally:
                page.close()

    # Interleave categories so Phase 2+3 sees variety, not all-extractive then all-grounding
    candidates: list[tuple[str, str]] = []
    max_len = max(len(v) for v in buckets.values()) if buckets else 0
    for i in range(max_len):
        for cat in DISCOVERY_HUBS:
            if i < len(buckets[cat]):
                candidates.append((cat, buckets[cat][i]))

    print(f"\n  Category breakdown: " +
          ", ".join(f"{cat}: {len(urls)}" for cat, urls in buckets.items()))
    return candidates


# ---------------------------------------------------------------------------
# PHASE 2: SCREENSHOT
# ---------------------------------------------------------------------------

def screenshot_url(browser, url: str, out_path: str) -> bool:
    """
    Navigate to url and save a screenshot to out_path.
    Returns True on success, False on failure.
    """
    page = browser.new_page(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
    )
    page.set_default_navigation_timeout(NAV_TIMEOUT)

    try:
        page.goto(url, wait_until="networkidle")
        time.sleep(POST_LOAD_DELAY)
        page.screenshot(path=out_path)
        return True
    except PlaywrightTimeoutError:
        print(f"  !! TIMEOUT: {url}")
        return False
    except Exception as exc:
        print(f"  !! FAILED: {url} — {exc}")
        return False
    finally:
        page.close()


# ---------------------------------------------------------------------------
# PHASE 3: CLASSIFY VIA GROQ VISION
# ---------------------------------------------------------------------------

def classify_screenshot(client: Groq, image_path: str) -> dict | None:
    """
    Send the screenshot at image_path to Groq's Llama 3.2 Vision API.
    Returns dict with keys: category, confidence, reasoning.
    Returns None on any error.
    """
    import base64
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT + "\n\nClassify this web interface screenshot. Respond with JSON only.",
                    },
                ],
            }],
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if the model wraps the JSON
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        result = json.loads(raw)

        # Validate required keys and category value
        if "category" not in result or "confidence" not in result or "reasoning" not in result:
            raise ValueError(f"Missing required keys in response: {result}")
        if result["category"] not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: {result['category']}")

        return result

    except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
        print(f"  !! PARSE ERROR: could not parse model response — {exc}")
        return None
    except Exception as exc:
        print(f"  !! UNEXPECTED ERROR: {exc}")
        return None


# ---------------------------------------------------------------------------
# LOG MANAGEMENT
# ---------------------------------------------------------------------------

def init_log(log_path: str) -> None:
    """Write CSV headers if the log file does not already exist."""
    if not os.path.exists(log_path):
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["url", "predicted_category", "confidence", "reasoning", "timestamp"])


def append_log(log_path: str, url: str, result: dict) -> None:
    """Append one result row to the CSV log."""
    ts = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            url,
            result["category"],
            result.get("confidence", ""),
            result.get("reasoning", ""),
            ts,
        ])


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable is not set.")
        print("  Windows: set GROQ_API_KEY=your-key-here")
        print("  Unix:    export GROQ_API_KEY=your-key-here")
        sys.exit(1)

    client = Groq(api_key=api_key)
    init_log(LOG_FILE)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    known_domains = get_seed_domains()
    print(f"[INIT] {len(known_domains)} existing domains loaded from capture.py (excluded from discovery).")

    stats = {"captured": 0, "classified": 0, "failed_nav": 0, "failed_api": 0}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        # ── PHASE 1: CRAWL HUBS ───────────────────────────────────────────
        total_hubs = sum(len(v) for v in DISCOVERY_HUBS.values())
        print(f"\n[PHASE 1] Crawling {total_hubs} hub pages "
              f"(up to {MAX_PER_CATEGORY} URLs per category)...\n")
        candidates = crawl_hubs(browser, known_domains)
        print(f"\n[PHASE 1] Complete. {len(candidates)} candidate URLs discovered.\n")

        # ── PHASE 2 + 3: SCREENSHOT + CLASSIFY ───────────────────────────
        print(f"[PHASE 2+3] Screenshotting and classifying {len(candidates)} candidates...\n")

        for idx, (category_hint, url) in enumerate(candidates, start=1):
            domain = domain_from_url(url)
            print(f"  [{idx}/{len(candidates)}] {url} (hint: {category_hint})")

            staging_path = os.path.join(OUTPUT_DIR, f"_staging_{domain}.png")

            success = screenshot_url(browser, url, staging_path)
            if not success:
                stats["failed_nav"] += 1
                if os.path.exists(staging_path):
                    os.remove(staging_path)
                continue

            stats["captured"] += 1

            result = classify_screenshot(client, staging_path)
            if result is None:
                stats["failed_api"] += 1
                os.remove(staging_path)
                continue

            stats["classified"] += 1
            category   = result["category"]
            confidence = result.get("confidence", "?")
            reasoning  = result.get("reasoning", "")
            print(f"    -> {category} ({confidence}) — {reasoning}")

            category_dir = os.path.join(OUTPUT_DIR, category)
            os.makedirs(category_dir, exist_ok=True)
            final_path = os.path.join(category_dir, f"{idx:03d}_{domain}.png")
            os.rename(staging_path, final_path)

            append_log(LOG_FILE, url, result)

        browser.close()

    print("\n" + "=" * 50)
    print("Done.")
    print(f"  Screenshots taken  : {stats['captured']}")
    print(f"  Classified by LLM  : {stats['classified']}")
    print(f"  Nav failures       : {stats['failed_nav']}")
    print(f"  API failures       : {stats['failed_api']}")
    print(f"  Output directory   : {os.path.abspath(OUTPUT_DIR)}/")
    print(f"  Log file           : {os.path.abspath(LOG_FILE)}")
    print("=" * 50)


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()
