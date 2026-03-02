# Machine as Judge — Web Interface Dataset Crawler

A Playwright-based screenshot capture tool for building an image dataset to train a CNN classifier that judges web interfaces on their ethical design intent.

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

## How It Works

1. **Visits** each URL in the hardcoded dictionary using headless Chromium at a fixed **1280×800** viewport
2. **Waits** 5 seconds after page load so cookie banners, modals, and pop-ups render
3. **Classifies** the page automatically using JS heuristics (runs inside the browser before the screenshot)
4. **Screenshots** the visible viewport and saves it to `dataset/<category>/`
5. **Prints** a comparison of the human-assigned label vs. the auto-classified label

No ad-blockers are used — extractive sites need to show their full visual noise.

---

## Auto-Classifier

After each page loads, a JavaScript evaluation measures 15 signals:

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

Signals are scored against each category's feature profile. The highest score wins. The terminal output shows `✓` when auto matches human and `≠` when they disagree — disagreements are the most analytically interesting cases.

---

## Setup

**Requirements:** Python 3.14+

```bash
pip install playwright
playwright install chromium
```

---

## Usage

```bash
python capture.py
```

Screenshots are saved to:
```
dataset/
├── 1_Extractive/
├── 2_Persuasive/
├── 3_Neutral/
└── 4_Grounding/
```

Each file is named `<index>_<domain>.png` (e.g. `001_apple_com.png`).

---

## Configuration

All tunable constants are at the top of [capture.py](capture.py):

| Constant | Default | Description |
|---|---|---|
| `VIEWPORT_WIDTH` | `1280` | Browser viewport width |
| `VIEWPORT_HEIGHT` | `800` | Browser viewport height |
| `POST_LOAD_DELAY` | `5` | Seconds to wait after load (lets modals appear) |
| `NAV_TIMEOUT` | `30000` | Max ms to wait per page load |
| `OUTPUT_DIR` | `dataset` | Root folder for screenshots |

To add or change URLs, edit the `URLS` dictionary in [capture.py](capture.py).

---

## Notes

- The `dataset/` folder is excluded from version control (`.gitignore`) — screenshots are local only
- Sites that block headless browsers or require login will fail gracefully and be skipped
- The classifier is heuristic, not ML-based — it is a labeling aid, not the end product
