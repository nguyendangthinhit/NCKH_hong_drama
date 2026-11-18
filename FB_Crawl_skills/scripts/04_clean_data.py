"""
Demo facebook-data-clean skill: clean raw JSON output từ DevTools console snippet.

Input: file JSON từ scripts/03_console_snippets.js (FB comments extract)
Output:
  - data/clean_comments_<timestamp>.jsonl
  - data/quarantine_<timestamp>.jsonl
  - data/stats_<timestamp>.json

Usage:
  python3 scripts/04_clean_data.py data/fb_comments_xxx.json
"""
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path


# ============================================================
# Schema & validation
# ============================================================

REQUIRED_FIELDS = {"text"}  # minimum — author + text


def validate_record(rec: dict) -> tuple[bool, str | None]:
    for field in REQUIRED_FIELDS:
        if not rec.get(field):
            return False, f"missing_field:{field}"
    if len(rec.get("text", "")) < 2:
        return False, "text_too_short"
    return True, None


# ============================================================
# Text normalization
# ============================================================

def normalize_text(text: str) -> str:
    """Unicode NFC + strip control chars + collapse whitespace + strip ZW chars."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    text = re.sub(r"[​-‏‪-‮⁠]", "", text)  # strip ZWS, ZWNJ, ZWJ, RTL marks
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# Spam detection (heuristics)
# ============================================================

SPAM_PATTERNS = [
    r"\b(click|tap|nhấn)\s+(here|ngay|vào đây)\b",
    r"http[s]?://(?:bit\.ly|tinyurl\.com|goo\.gl)/\S+",
    r"\bDM\s+me\s+for",
    r"nhắn tin\s+cho\s+tôi",
]


def is_spam(record: dict) -> tuple[bool, list[str]]:
    text = record.get("text", "") or ""
    reasons = []

    for pat in SPAM_PATTERNS:
        if re.search(pat, text, re.I):
            reasons.append(f"pattern:{pat[:30]}")

    urls = re.findall(r"http[s]?://\S+", text)
    if len(urls) >= 3:
        reasons.append(f"link_count={len(urls)}")

    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.6:
        reasons.append("all_caps")

    return (len(reasons) > 0, reasons)


# ============================================================
# PII redaction (SĐT VN + email)
# ============================================================

PHONE_VN = re.compile(r"\b(0|\+84)(3[2-9]|5[6|8|9]|7[0|6-9]|8[1-9]|9[0-9])\d{7}\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def redact_pii(text: str) -> tuple[str, dict]:
    counts = {"phone": 0, "email": 0}

    def phone_repl(m):
        counts["phone"] += 1
        return "[REDACTED_PHONE]"

    def email_repl(m):
        counts["email"] += 1
        return "[REDACTED_EMAIL]"

    text = PHONE_VN.sub(phone_repl, text)
    text = EMAIL.sub(email_repl, text)
    return text, counts


# ============================================================
# Main pipeline
# ============================================================

def clean(input_path: Path, output_dir: Path | None = None,
          cross_dedup: bool = False) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print(f"⚠ Expected list, got {type(raw).__name__}")
        return {}

    # Auto-detect output folder: if input is in a post folder, output there
    if output_dir is None:
        # Post folders live under data/posts/<slug>/
        if input_path.parent.parent.name == "posts":
            # Input is at data/posts/<slug>/<file> → save outputs to <slug>/
            output_dir = input_path.parent
        else:
            # Fallback to data root
            from _data_paths import DATA_DIR
            output_dir = DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    clean_records = []
    quarantine = []
    seen_hashes = set()
    pii_totals = {"phone": 0, "email": 0}
    lang_counter = {}
    spam_count = 0
    schema_fail = 0
    exact_dup = 0
    cross_dup_removed = 0

    # Cross-run dedup: load text_hashes from all existing clean.jsonl files
    # (except the one we're about to write, to avoid self-matching).
    if cross_dedup:
        from _data_paths import POSTS_DIR
        for other_clean in POSTS_DIR.rglob("clean.jsonl"):
            if output_dir and other_clean.parent == output_dir:
                continue  # Skip our own target dir
            try:
                for line in other_clean.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    # Hash the CLEANED text (so normalized text matches across runs)
                    clean_t = normalize_text(rec.get("text", ""))
                    if clean_t:
                        h = hashlib.sha256(clean_t.encode("utf-8")).hexdigest()[:16]
                        seen_hashes.add(h)
            except Exception:
                pass  # Corrupt file, skip

    for rec in raw:
        # 1. Schema validation
        valid, err = validate_record(rec)
        if not valid:
            quarantine.append({"reason": err, "original": rec})
            schema_fail += 1
            continue

        # 2. Exact dedup (within this run) + cross-run dedup (if enabled)
        text = rec["text"]
        # 3. Text normalization — we'll hash the normalized text
        clean_text = normalize_text(text)
        text_hash = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()[:16]
        if text_hash in seen_hashes:
            # Was it from this run or loaded from another run's clean.jsonl?
            if cross_dedup:
                cross_dup_removed += 1
                reason = "cross_run_dup"
            else:
                exact_dup += 1
                reason = "exact_dup"
            quarantine.append({"reason": reason, "details": text_hash, "original": rec})
            continue
        seen_hashes.add(text_hash)

        # 4. Spam filter
        is_spam_rec, spam_reasons = is_spam(rec)
        if is_spam_rec:
            quarantine.append({"reason": "spam", "details": spam_reasons, "original": rec})
            spam_count += 1
            continue

        # 5. PII redaction
        clean_text, pii_counts = redact_pii(clean_text)
        for k, v in pii_counts.items():
            pii_totals[k] += v

        # 6. Build clean record
        clean_rec = {
            "author": rec.get("author"),
            "profile_url": rec.get("profile_url"),
            "text": clean_text,
            "text_hash": text_hash,
            "timestamp_original": rec.get("timestamp"),
            "reactions": rec.get("reactions"),
            "replies": rec.get("replies"),
            "scraped_at": rec.get("scraped_at"),
            "post_url": rec.get("post_url"),
            "pii_redactions": pii_counts,
            "cleaned_at": datetime.utcnow().isoformat() + "Z",
        }
        clean_records.append(clean_rec)

    # Stats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # If saving in post folder, use stable names; else use timestamp
    in_post_folder = (
        output_dir.parent.name == "posts" or
        "share_p_" in output_dir.name or
        "groups_" in output_dir.name or
        "mrgoonie_" in output_dir.name
    )
    if in_post_folder:
        # Stable names — overwrite previous
        clean_path = output_dir / "clean.jsonl"
        quarantine_path = output_dir / "quarantine.jsonl"
        stats_path = output_dir / "stats.json"
    else:
        clean_path = output_dir / f"clean_comments_{timestamp}.jsonl"
        quarantine_path = output_dir / f"quarantine_{timestamp}.jsonl"
        stats_path = output_dir / f"stats_{timestamp}.json"

    with open(clean_path, "w", encoding="utf-8") as f:
        for r in clean_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(quarantine_path, "w", encoding="utf-8") as f:
        for r in quarantine:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {
        "input_file": str(input_path),
        "total_input": len(raw),
        "schema_fail": schema_fail,
        "exact_dup_removed": exact_dup,
        "cross_dup_removed": cross_dup_removed,
        "spam_removed": spam_count,
        "total_quarantine": len(quarantine),
        "total_clean": len(clean_records),
        "pii_redactions": pii_totals,
        "cross_dedup_enabled": cross_dedup,
        "processed_at": datetime.utcnow().isoformat() + "Z",
    }

    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    # Write clean manifest (clean_manifest.json) — audit trail for this clean run
    clean_manifest = {
        "input_sha256": _sha256_file(input_path),
        "input_path": str(input_path),
        "output_paths": {
            "clean": str(clean_path),
            "quarantine": str(quarantine_path),
            "stats": str(stats_path),
        },
        "dedup_removed_count": exact_dup + cross_dup_removed,
        "quarantine_count": len(quarantine),
        "clean_count": len(clean_records),
        "cross_dedup_enabled": cross_dedup,
        "duration_seconds": None,  # Caller can compute
        "processed_at": stats["processed_at"],
    }
    cm_path = output_dir / "clean_manifest.json"
    with open(cm_path, "w", encoding="utf-8") as f:
        json.dump(clean_manifest, f, indent=2, ensure_ascii=False)

    return {
        "stats": stats,
        "clean_path": str(clean_path),
        "quarantine_path": str(quarantine_path),
        "stats_path": str(stats_path),
        "clean_manifest_path": str(cm_path),
        "sample_clean": clean_records[:3],
    }


def _sha256_file(path: Path) -> str:
    """SHA256 of file contents (for clean_manifest input hash)."""
    import hashlib as _hl
    h = _hl.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Clean FB comments JSON")
    parser.add_argument("input", help="Path to raw JSON from console snippet")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: auto-detect from input location)",
    )
    parser.add_argument(
        "--cross-dedup", action="store_true",
        help="Skip records whose text_hash already exists in any other "
             "data/posts/*/clean.jsonl (cross-run deduplication)",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir) if args.output_dir else None

    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        sys.exit(1)

    print(f"📂 Input: {input_path}")
    if args.cross_dedup:
        print("  → Cross-dedup enabled (will skip records matching other clean.jsonl files)")
    result = clean(input_path, output_dir, cross_dedup=args.cross_dedup)

    if not result:
        sys.exit(1)

    print(f"\n📊 Stats:")
    for k, v in result["stats"].items():
        print(f"  {k}: {v}")

    print(f"\n💾 Outputs:")
    print(f"  Clean           : {result['clean_path']}")
    print(f"  Quarantine      : {result['quarantine_path']}")
    print(f"  Stats           : {result['stats_path']}")
    print(f"  Clean manifest  : {result['clean_manifest_path']}")

    print(f"\n📋 Sample (first 3 clean records):")
    for r in result["sample_clean"]:
        print(f"  - {r['author']}: {r['text'][:80]}")


if __name__ == "__main__":
    main()