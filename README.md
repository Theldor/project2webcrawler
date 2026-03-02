# Machine as Judge — Web Interface Dataset Crawler

A Playwright-based pipeline for building an image dataset to train a CNN classifier that judges web interfaces on their ethical design intent.

---

## Concept

This project explores the idea of the **"Machine as Judge"** — training a classifier to evaluate web interfaces not on aesthetics, but on their relationship to the user. The classifier learns to distinguish between interfaces that extract from users versus interfaces that serve them.

### Categories

| Label | Name | Design Intent |
|---|---|---|
| `1_Extractive` | Extractive | Works against user interests. High CTA density, dark patterns, aggressive tracking, infinite scroll, autoplay, scarcity manipulation. |
| `2_Persuasive` | Persuasive | Moves users toward an action honestly. Clear hierarchy, social proof, narrative scroll, deliberate endpoints. |
| `3_Neutral` | Neutral / Utilitarian | Helps users complete a task and leave. Dense information, navigation-forward, minimal tracking, search-primary. |
| `4_Grounding` | Grounding | Leaves users present, informed, or at rest. Long-form text, generous spacing, no manipulation, considered typography. |

---

## Scripts

### `capture.py` — Hand-Curated Ground Truth

Visits pre-labeled URLs from a hardcoded dictionary using Chromium (headed or headless). Primary dataset builder.

**How it works:**

1. Visits each URL at a fixed **1280×800** viewport
2. Waits 5 seconds after page load so cookie banners and modals render
3. Runs a JS heuristic classifier (15 signals measured in-browser) before the screenshot
4. Screenshots the visible viewport and saves it to `dataset/<category>/`
5. Prints a comparison of human-assigned vs. auto-classified label

No ad-blockers — extractive sites need to show their full visual noise.

**JS Auto-Classifier signals:**

| Signal | What it measures |
|---|---|
| `ctaCount` | Buttons/links with action copy (buy, sign up, subscribe…) |
| `fixedCount` | Fixed/sticky positioned elements |
| `trackerCount` | Known ad/analytics scripts (GTM, Meta Pixel, Hotjar…) |
| `autoplayCount` | Autoplay video or audio |
| `hasScarcity` | Scarcity language in copy ("only 3 left", "ends tonight") |
| `hasCountdown` | Countdown timers by class name or copy |
| `modalCount` | Dialogs, overlays, popups |
| `socialCount` | Testimonial/review/rating sections |
| `hasSearch` | Prominent search input |
| `navLinks` | Navigation link density |
| `articleWords` | Word count inside `<article>` / `<main>` |
| `hasTOC` | Table of contents element |
| `textRatio` | Words per image |
| `wordCount` | Total page word count |
| `formCount` | Number of forms |

The terminal output shows `✓` when auto matches human and `≠` when they disagree — disagreements are the most analytically interesting cases.

**Output:**
```
dataset/
├── 1_Extractive/
├── 2_Persuasive/
├── 3_Neutral/
└── 4_Grounding/
```

Each file is named `<index>_<domain>.png` (e.g. `001_apple_com.png`).

---

### `clean_dataset.py` — Manifest & Failed URLs

Builds a clean manifest from successful screenshots + human labels (CSV). Outputs `dataset_manifest.csv` and `failed_urls.csv` for training.

```bash
python clean_dataset.py
```

---

### `explore.py` — LLM-Powered URL Discovery & Classification

Crawls outward from the seed pages in `capture.py`, discovers new websites, and classifies them using Groq's Llama 3.2 Vision API. Expands the dataset beyond the hand-curated dictionary.

**How it works (3-phase pipeline):**

1. **Phase 1 — Crawl Seeds:** Visits every URL in `capture.py`'s dictionary, extracts external links, deduplicates by domain, and builds a candidate pool of up to 50 new URLs
2. **Phase 2 — Screenshot:** Navigates to each candidate using headless Chromium and saves a PNG to a staging path
3. **Phase 3 — Classify:** Sends each screenshot (base64-encoded) to Groq's Llama 3.2 Vision model, which returns a JSON classification. Moves the PNG to `dataset_explored/<category>/` and appends a row to `explore_log.csv`

**Output:**
```
dataset_explored/
├── 1_Extractive/
├── 2_Persuasive/
├── 3_Neutral/
└── 4_Grounding/
explore_log.csv    (url, predicted_category, confidence, reasoning, timestamp)
```

---

## Setup

**Requirements:** Python 3.14+

```bash
pip install playwright groq
playwright install chromium
```

For `explore.py`, you also need a [Groq API key](https://console.groq.com) (free tier, no credit card required):

```bash
# Unix / macOS
export GROQ_API_KEY=your-key-here

# Windows CMD
set GROQ_API_KEY=your-key-here
```

---

## Usage

```bash
# Build the hand-curated ground-truth dataset
python capture.py

# Build manifest from screenshots + CSV labels
python clean_dataset.py

# Discover and classify new URLs via LLM
python explore.py
```

---

## Configuration

**`capture.py`** — all constants at the top of the file:

| Constant | Default | Description |
|---|---|---|
| `VIEWPORT_WIDTH` | `1280` | Browser viewport width |
| `VIEWPORT_HEIGHT` | `800` | Browser viewport height |
| `POST_LOAD_DELAY` | `5` | Seconds to wait after load (lets modals appear) |
| `NAV_TIMEOUT` | `45000` | Max ms to wait per page load |
| `WAIT_UNTIL` | `domcontentloaded` | Page load strategy (`load` can hang on heavy sites) |
| `DELAY_BETWEEN_SITES` | `3` | Seconds between captures (reduces rate limiting) |
| `SKIP_EXISTING` | `True` | Skip URLs that already have a screenshot |
| `OUTPUT_DIR` | `dataset` | Root folder for screenshots |

**`explore.py`** — all constants at the top of the file:

| Constant | Default | Description |
|---|---|---|
| `MAX_NEW_URLS` | `50` | Max new URLs to discover per run |
| `GROQ_MODEL` | `llama-3.2-11b-vision-preview` | Groq vision model |
| `OUTPUT_DIR` | `dataset_explored` | Root folder for discovered screenshots |
| `LOG_FILE` | `explore_log.csv` | CSV log of all classifications |

---

## Notes

- The `dataset/` and `dataset_explored/` folders are excluded from version control — screenshots are local only
- Sites that block headless browsers or require login fail gracefully and are skipped
- The JS classifier in `capture.py` is a labeling aid, not the end product — disagreements with human labels are intentional signal
- `explore.py` requires `GROQ_API_KEY` set as an environment variable before running
- See [requirements.md](requirements.md) for the training/classifier roadmap
