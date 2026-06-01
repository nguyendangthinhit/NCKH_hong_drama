"""
Export 5k samples per domain for human verification.

Strategy:
- Showbiz: take ALL minority classes + fill with Trung lập + trash samples
- Education: take ALL rare classes + balanced sample from common classes + trash

Output: Excel files with columns [comment_id, text, llm_label, is_trash, event_id, verified_label]
        verified_label is empty — human fills it in.

Usage:
    python sampling_labeling/export_5k_for_verification.py
    python sampling_labeling/export_5k_for_verification.py --domain showbiz
    python sampling_labeling/export_5k_for_verification.py --domain education
"""

import argparse
import json
import random
from pathlib import Path

import pandas as pd

SEED = 42
TARGET_PER_DOMAIN = 5000

SHOW_DIR = Path("data/processed/process_showbiz/analyzed_data/full")
EDU_DIR = Path("data/processed/process_education/analyzed_dataa/full")
OUTPUT_DIR = Path("sampling_labeling/data_labels")

SHOW_VALID_EMOTIONS = {"Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập"}
EDU_VALID_STANCES = {"tích cực", "tiêu cực", "trung lập", "ý kiến riêng"}

# "Ứng hộ" is a typo in data, normalize to "Ủng hộ"
EMOTION_NORMALIZE = {"Ứng hộ": "Ủng hộ"}


def flatten_event(event_json, domain):
    """Flatten comments + replies from one event into flat list."""
    label_field = "emotion" if domain == "showbiz" else "stance"
    rows = []
    for c in event_json.get("comments", []):
        rows.append({
            "comment_id": c["comment_id"],
            "text": c.get("text", ""),
            "llm_label": c.get(label_field),
            "is_trash": c.get("is_trash", False),
            "event_id": event_json["id_content"],
        })
        for r in c.get("replies", []):
            rows.append({
                "comment_id": r["comment_id"],
                "text": r.get("text", ""),
                "llm_label": r.get(label_field),
                "is_trash": r.get("is_trash", False),
                "event_id": event_json["id_content"],
            })
    return rows


def load_all(domain):
    """Load all comments for a domain."""
    input_dir = SHOW_DIR if domain == "showbiz" else EDU_DIR
    all_rows = []
    for f in sorted(input_dir.glob("*.json")):
        with open(f, encoding="utf-8") as fh:
            event = json.load(fh)
        all_rows.extend(flatten_event(event, domain))
    return all_rows


def sample_showbiz(all_rows):
    """
    Showbiz sampling: ALL minority + capped Trung lập + Trash to balance.
    Target: 5000 total.
    Strategy: minority gets priority, Trung lập capped ~2000, Trash fills rest.
    """
    random.seed(SEED)

    # Normalize typo
    for r in all_rows:
        if r["llm_label"] in EMOTION_NORMALIZE:
            r["llm_label"] = EMOTION_NORMALIZE[r["llm_label"]]

    # Split by category
    trash = [r for r in all_rows if r["is_trash"]]
    minority = [r for r in all_rows if not r["is_trash"] and r["llm_label"] in SHOW_VALID_EMOTIONS and r["llm_label"] != "Trung lập"]
    neutral = [r for r in all_rows if not r["is_trash"] and r["llm_label"] == "Trung lập"]

    # Take ALL minority
    selected = list(minority)
    print(f"  Minority (all): {len(selected)}")

    # Cap Trung lập at 2000
    neutral_target = 2000
    neutral_sample = random.sample(neutral, min(neutral_target, len(neutral)))
    selected.extend(neutral_sample)
    print(f"  Trung lập (capped): {len(neutral_sample)}")

    # Fill remaining with Trash
    remaining = TARGET_PER_DOMAIN - len(selected)
    trash_sample = random.sample(trash, min(remaining, len(trash)))
    selected.extend(trash_sample)
    print(f"  Trash (fill): {len(trash_sample)}")

    random.shuffle(selected)
    print(f"  Total showbiz: {len(selected)}")
    return selected[:TARGET_PER_DOMAIN]


def sample_education(all_rows):
    """
    Education sampling: take ALL rare classes, balanced from common, + trash.
    Target: 5000 total.
    """
    random.seed(SEED)

    trash = [r for r in all_rows if r["is_trash"]]
    by_stance = {}
    for r in all_rows:
        if r["is_trash"]:
            continue
        lbl = r["llm_label"]
        if lbl in EDU_VALID_STANCES:
            by_stance.setdefault(lbl, []).append(r)

    # Take ALL rare: ý kiến riêng (355), tích cực (644)
    selected = []
    selected.extend(by_stance.get("ý kiến riêng", []))
    selected.extend(by_stance.get("tích cực", []))
    print(f"  ý kiến riêng (all): {len(by_stance.get('ý kiến riêng', []))}")
    print(f"  tích cực (all): {len(by_stance.get('tích cực', []))}")

    # Add trash (~800)
    trash_target = 800
    trash_sample = random.sample(trash, min(trash_target, len(trash)))
    selected.extend(trash_sample)
    print(f"  Trash: {len(trash_sample)}")

    # Fill remaining balanced between tiêu cực and trung lập
    remaining = TARGET_PER_DOMAIN - len(selected)
    per_class = remaining // 2
    tieu_cuc = by_stance.get("tiêu cực", [])
    trung_lap = by_stance.get("trung lập", [])
    tc_sample = random.sample(tieu_cuc, min(per_class, len(tieu_cuc)))
    tl_sample = random.sample(trung_lap, min(remaining - len(tc_sample), len(trung_lap)))
    selected.extend(tc_sample)
    selected.extend(tl_sample)
    print(f"  tiêu cực (sample): {len(tc_sample)}")
    print(f"  trung lập (sample): {len(tl_sample)}")

    random.shuffle(selected)
    print(f"  Total education: {len(selected)}")
    return selected[:TARGET_PER_DOMAIN]


def to_dataframe(samples, domain):
    """Convert to DataFrame with verification columns."""
    label_col = "emotion" if domain == "showbiz" else "stance"
    df = pd.DataFrame(samples)
    df = df.rename(columns={"llm_label": f"llm_{label_col}"})
    df["verified_label"] = ""
    df["notes"] = ""
    # Reorder columns
    cols = ["comment_id", "event_id", "text", f"llm_{label_col}", "is_trash", "verified_label", "notes"]
    return df[cols]


def export_domain(domain):
    print(f"\n{'='*50}")
    print(f"Processing: {domain}")
    print(f"{'='*50}")

    all_rows = load_all(domain)
    print(f"  Loaded {len(all_rows)} total comments")

    if domain == "showbiz":
        samples = sample_showbiz(all_rows)
    else:
        samples = sample_education(all_rows)

    df = to_dataframe(samples, domain)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    xlsx_path = OUTPUT_DIR / f"verify_{domain}_5k.xlsx"
    csv_path = OUTPUT_DIR / f"verify_{domain}_5k.csv"

    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  Exported: {xlsx_path}")
    print(f"  Exported: {csv_path}")

    # Print distribution summary
    label_col = "llm_emotion" if domain == "showbiz" else "llm_stance"
    print(f"\n  Distribution:")
    trash_count = df["is_trash"].sum()
    print(f"    [trash]: {trash_count}")
    non_trash = df[~df["is_trash"]]
    for lbl, cnt in non_trash[label_col].value_counts().items():
        print(f"    {lbl}: {cnt}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    args = ap.parse_args()
    domains = ["showbiz", "education"] if args.domain == "all" else [args.domain]
    for d in domains:
        export_domain(d)


if __name__ == "__main__":
    main()
