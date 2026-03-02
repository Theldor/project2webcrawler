# Requirements: Machine as Judge — Training & Classification System

This document outlines the work needed to build a human rating interface, train an image classifier, and deploy a live website classifier with percentage outputs.

---

## Decided / Resolved

| Topic | Decision |
|-------|----------|
| **training.html display** | Live site in iframe. Raters can skip if site doesn't load (bot blocking, etc.). |
| **Label source** | Re-tag and re-rate all sites via training.html (CSV is starting point only). |
| **Multiple raters** | Keep all ratings; aggregate by averaging to produce final labels. |
| **Persistence** | Simple backend (to be built). |
| **Classifier deployment** | Public on the internet. |
| **URL restrictions** | None. |
| **Screenshot preview** | Show captured screenshot alongside the percentage output. |
| **Retraining** | One-off for now. |
| **Classifier output** | Show the four percentages only. |
| **Failed captures** | Only use sites with successful captures. Use data-cleaning flow (see below). |
| **MVP** | Get to classifier.html based on the current dataset (existing CSV + screenshots). |
| **Tech stack** | Whatever is fastest to build. |

---

## End Goals

1. **training.html** — Frontend for human raters to tag websites from our curated list with one of four design-intent categories (Extractive, Persuasive, Neutral, Grounding).

2. **Trained model** — CNN (or similar) trained on the labeled screenshot dataset, outputting class probabilities.

3. **classifier.html** — Frontend where a user enters a website URL; the system captures it, runs the model, and displays the screenshot alongside percentage predictions (e.g., 40% Extractive, 20% Persuasive, 30% Neutral, 10% Grounding).

---

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  training.html  │     │  Backend / API   │     │ classifier.html │
│  Human rating   │────▶│  - Capture URLs  │◀────│  User pastes    │
│  interface      │     │  - Serve data    │     │  URL → % output │
└─────────────────┘     │  - Run inference │     └─────────────────┘
                        └──────────────────┘
                                    │
                                    ▼
                        ┌──────────────────┐
                        │  Trained Model   │
                        │  (4-class prob)  │
                        └──────────────────┘
```

The classifier must capture live URLs (screenshot), so a backend is required for that step. Inference can run on the backend or, if the model is exported (e.g., ONNX/TensorFlow.js), in the browser.

---

## Phase 1: Human Rating Interface (training.html)

### Purpose
Allow human raters to view websites and assign design-intent labels. Output feeds the training dataset.

### Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| 1.1 | **Website source** | Load URLs from `DesignWithAI2_ Website Classifier - Sheet1.csv` (or synced export). Map to the 4 categories: `1_Extractive`, `2_Persuasive`, `3_Neutral`, `4_Grounding`. |
| 1.2 | **Display mode** | **Live site in iframe.** Raters see the actual webpage. Option to skip / mark "unratable" when site blocks the bot or doesn't render correctly. |
| 1.3 | **Rating UI** | Clear controls to select one of the four categories. |
| 1.4 | **Navigation** | Previous / Next through the list. Progress indicator (e.g., "Site 45 of 354"). Skip button for blocked or broken sites. |
| 1.5 | **Persistence** | **Simple backend.** Store ratings via API. Format: `url, human_label, rater_id, timestamp`. Backend to be implemented. |
| 1.6 | **Resume support** | Load existing ratings so raters can continue where they left off. Highlight already-rated vs unrated. |
| 1.7 | **Multiple raters** | Keep all ratings. Aggregate by **averaging** (e.g., encode categories as 0–3, average, round to nearest class) to produce final training labels. |

### Technical Notes
- Backend required for persistence. training.html will call API to fetch URLs and submit ratings.

---

## Phase 2: Dataset Preparation & Model Training

### Purpose
Produce a labeled dataset and train a model that outputs class probabilities.

### Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| 2.1 | **Label source** | Use human labels from training.html (averaged across raters). For MVP: use existing CSV as ground truth. Map each screenshot file to a label. |
| 2.2 | **Dataset structure** | Standard image-classification layout: `dataset/<category>/<id>.png` or a manifest CSV: `path, label`. |
| 2.3 | **Splits** | Train / validation / test. Split by **site/URL**, not by random image, to avoid leakage. Suggested: ~70% / 15% / 15%. |
| 2.4 | **Class balance** | Check and, if needed, handle imbalance (e.g., oversampling, class weights, or collecting more samples for underrepresented classes). |
| 2.5 | **Model architecture** | Transfer learning from a pretrained CNN (ResNet50, EfficientNet, ViT). Replace final layer with 4-class head. Softmax output → class probabilities. |
| 2.6 | **Training** | Standard supervised training. Output: model checkpoint (PyTorch/TensorFlow) and optionally ONNX for deployment. |
| 2.7 | **Evaluation** | Accuracy, per-class precision/recall, confusion matrix. Document performance before deployment. |

### Deliverables
- Training script (e.g., `train.py`)
- Trained model file(s)
- Optional: export to ONNX or TensorFlow.js for browser inference
- `requirements.txt` for the training environment

---

## Data Cleaning: Failed Captures

**Goal:** Produce a clean dataset that includes only sites with successful screenshots. Make it easy to inspect, fix, and regenerate.

### Approach

1. **Run capture.py** — Log which URLs succeed and which fail (capture.py already prints `!! FAILED` per URL).
2. **Generate manifest** — Add a `clean_dataset.py` (or extend capture.py) that:
   - Scans `dataset/<category>/` for existing `.png` files
   - Cross-references with the CSV to attach human labels
   - Outputs a **clean manifest** (e.g., `dataset_manifest.csv`): `path, url, label`
   - Optionally outputs a **failed URLs report** (`failed_urls.txt` or `failed_urls.csv`) for manual review
3. **Optional re-capture** — Script or flag to re-run capture only for failed URLs (e.g., after fixing `wait_until`), then re-scan.
4. **Train from manifest** — `train.py` reads `dataset_manifest.csv` and loads only images that exist; skips or errors on missing files.

### Manifest Format (example)

```csv
path,url,label
dataset/1_Extractive/001_apple_com.png,https://www.apple.com,1_Extractive
dataset/2_Persuasive/003_metmuseum_org.png,https://www.metmuseum.org/,2_Persuasive
```

### Easy Workflow

| Step | Command / Action |
|------|------------------|
| 1 | Run `python capture.py` (with `wait_until="load"`) |
| 2 | Run `python clean_dataset.py` → produces `dataset_manifest.csv` + `failed_urls.csv` |
| 3 | Review `failed_urls.csv`; remove from CSV or fix URLs if needed |
| 4 | Run `python train.py` using `dataset_manifest.csv` |

### clean_dataset.py (draft responsibilities)

- Read `DesignWithAI2_ Website Classifier - Sheet1.csv` and `capture.py` URLS (or a single source of truth)
- For each URL, determine expected screenshot path (e.g., `dataset/<category>/<idx>_<domain>.png`)
- Check if file exists
- If yes: add row to manifest with normalized label
- If no: add to failed list
- Write manifest and failed report

---

## Phase 3: Live Website Classifier (classifier.html)

### Purpose
User pastes a URL → system captures the page → model predicts → show percentages per category.

### Functional Requirements

| # | Requirement | Details |
|---|-------------|---------|
| 3.1 | **URL input** | User enters or pastes a website URL (with basic validation). |
| 3.2 | **Capture** | Backend uses Playwright to screenshot the URL at 1280×800 (same as training). Use `wait_until="load"` to avoid timeouts. |
| 3.3 | **Inference** | Run the trained model on the captured image. Output: four probabilities summing to 1. |
| 3.4 | **Display** | Show the four percentages (Extractive, Persuasive, Neutral, Grounding). **Screenshot displayed alongside** the results. |
| 3.5 | **Error handling** | Handle timeouts, blocked sites, invalid URLs. Show clear error messages. |

### Technical Notes
- **Backend required**: Capturing live URLs cannot be done purely in the browser. Deploy **publicly on the internet**. Use a small API (Flask, FastAPI, etc.) with:
  - `POST /capture` or `POST /classify` — accepts URL, returns screenshot + predictions (or predictions only).
- **Model serving**: Run inference in Python (PyTorch/TensorFlow). For a simple setup, keep everything in one backend process.
- **Frontend**: classifier.html calls the API, receives percentages, and renders the UI.

---

## Phase 4: Integration & Polish

| # | Task | Details |
|---|------|---------|
| 4.1 | **Fix capture.py** | Change `wait_until` from `networkidle` to `load` to reduce timeouts during data collection. |
| 4.2 | **Unify data** | Ensure CSV, screenshots, and human ratings from training.html are aligned. Single source of truth for labels. |
| 4.3 | **Data cleaning** | Filter to only sites with successful captures. See "Data Cleaning" section below. |
| 4.4 | **Documentation** | README updates: how to run training, rating, capture, and classifier. |
| 4.5 | **Deployment** | Public internet. classifier.html and training.html served by the same backend or static server. |

---

## File Structure (Target)

```
project2webcrawler-main/
├── capture.py              # Screenshot capture (existing, update wait_until)
├── clean_dataset.py        # Build manifest from captures + CSV; output failed_urls (new)
├── train.py                # Model training script (new)
├── app.py                  # Backend API for capture + inference (new)
├── training.html           # Human rating interface (new)
├── classifier.html         # URL → % classifier interface (new)
├── requirements.txt        # Python deps for capture, train, app
├── requirements.md         # This file
├── dataset/                # Screenshots by category
│   ├── 1_Extractive/
│   ├── 2_Persuasive/
│   ├── 3_Neutral/
│   └── 4_Grounding/
├── models/                 # Trained model checkpoints (new)
├── dataset_manifest.csv    # Clean list: path, url, label (from clean_dataset.py)
├── failed_urls.csv         # URLs that failed capture (for review)
└── DesignWithAI2_ Website Classifier - Sheet1.csv
```

---

## Dependency Summary

| Component | Dependencies |
|-----------|---------------|
| Capture | `playwright` |
| Training | `torch` or `tensorflow`, `torchvision`/`tensorflow` image utils, `pandas` |
| Backend API | `flask` or `fastapi`, `playwright`, model inference lib |
| Frontends | Plain HTML/CSS/JS, or a minimal framework if desired |

---

## Suggested Implementation Order

### MVP (classifier.html from current dataset)

1. Fix `capture.py` (`wait_until="load"`), run full capture.
2. Add `clean_dataset.py` to produce `dataset_manifest.csv` from successful captures + CSV labels.
3. Implement `train.py` and train the model on the clean manifest.
4. Add backend `app.py` with capture + inference endpoints.
5. Build `classifier.html` — URL input, call API, show screenshot + four percentages.
6. Test end-to-end.

### Post-MVP (training.html + backend)

7. Build simple backend for ratings (store/retrieve).
8. Build `training.html` — iframe, re-tag flow, submit to backend.
9. When ready: retrain model from averaged human ratings (future iteration).
