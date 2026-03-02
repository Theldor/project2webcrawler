"""
Dataset Cleaner for "Machine as Judge"
=====================================
Scans dataset/ for successful screenshots, cross-references with human labels from CSV,
and outputs:
  - dataset_manifest.csv  — path, url, label (only successful captures)
  - failed_urls.csv        — urls that have no screenshot (for review / re-capture)

Usage:
    python clean_dataset.py

Requires:
  - dataset/<category>/*.png (from capture.py)
  - DesignWithAI2_ Website Classifier - Sheet1.csv
  - capture.py (for URL list and domain logic)
"""

import csv
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Import from capture.py — single source of truth for URLs and paths
from capture import URLS, OUTPUT_DIR, domain_from_url

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

CSV_PATH = "DesignWithAI2_ Website Classifier - Sheet1.csv"
MANIFEST_PATH = "dataset_manifest.csv"
FAILED_URLS_PATH = "failed_urls.csv"

# Map CSV human category strings to our label format
LABEL_MAP = {
    "extractive": "1_Extractive",
    "persuasive": "2_Persuasive",
    "neutral/utilitarian": "3_Neutral",
    "grounding": "4_Grounding",
}


def normalize_url_for_match(url: str):
    """Normalize URL to (hostname, path) for matching. Hostname lowercase, no www."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    hostname = (parsed.hostname or "unknown").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    path = (parsed.path or "/").rstrip("/") or "/"
    return (hostname, path)


def load_csv_labels(csv_path: str):
    """Build {(hostname, path) -> normalized_label} from CSV. First match wins."""
    labels = {}
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").strip()
            if not url:
                continue
            cat = row.get("Human-defined Category", "").strip().lower()
            if not cat or cat not in LABEL_MAP:
                continue
            key = normalize_url_for_match(url)
            if key not in labels:  # first match wins
                labels[key] = LABEL_MAP[cat]
    return labels


def find_label(url: str, labels: dict) -> Optional[str]:
    """Look up label for url. Tries exact (hostname, path) then hostname-only."""
    key = normalize_url_for_match(url)
    if key in labels:
        return labels[key]
    hostname_only = (key[0], "/")
    if hostname_only in labels:
        return labels[hostname_only]
    # Try matching by hostname with any path
    for (h, p), lbl in labels.items():
        if h == key[0]:
            return lbl
    return None


def main() -> None:
    script_dir = Path(__file__).parent.resolve()
    dataset_dir = script_dir / OUTPUT_DIR
    csv_path = script_dir / CSV_PATH

    if not csv_path.exists():
        print(f"!! CSV not found: {csv_path}")
        return

    labels = load_csv_labels(str(csv_path))
    print(f"Loaded {len(labels)} URL–label pairs from CSV")

    manifest_rows: list[dict] = []
    failed_rows: list[dict] = []

    for category, urls in URLS.items():
        category_dir = dataset_dir / category
        if not category_dir.exists():
            for idx, url in enumerate(urls, start=1):
                failed_rows.append({"category": category, "url": url, "reason": "category_dir_missing"})
            continue

        for idx, url in enumerate(urls, start=1):
            domain = domain_from_url(url)
            filename = f"{idx:03d}_{domain}.png"
            filepath = category_dir / filename

            if filepath.exists():
                label = find_label(url, labels)
                if label is None:
                    label = category  # fallback to capture.py category
                manifest_rows.append({
                    "path": str(filepath.relative_to(script_dir)),
                    "url": url,
                    "label": label,
                })
            else:
                failed_rows.append({
                    "category": category,
                    "url": url,
                    "reason": "no_screenshot",
                })

    # Write manifest
    manifest_path = script_dir / MANIFEST_PATH
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["path", "url", "label"])
        w.writeheader()
        w.writerows(manifest_rows)
    print(f"Wrote {len(manifest_rows)} rows to {manifest_path}")

    # Write failed list
    failed_path = script_dir / FAILED_URLS_PATH
    with open(failed_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "url", "reason"])
        w.writeheader()
        w.writerows(failed_rows)
    print(f"Wrote {len(failed_rows)} failed URLs to {failed_path}")

    # Summary by label
    by_label: dict[str, int] = {}
    for row in manifest_rows:
        lbl = row["label"]
        by_label[lbl] = by_label.get(lbl, 0) + 1
    print("\nManifest by label:")
    for lbl in sorted(by_label.keys()):
        print(f"  {lbl}: {by_label[lbl]}")


if __name__ == "__main__":
    main()
