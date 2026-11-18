"""
Export clean JSONL to other formats (CSV, JSON array, Parquet).

Why a separate utility:
  - Comments JSONL is the canonical format (line-per-record for streaming).
  - Analytics teams often want CSV (Excel/Sheets) or Parquet (pandas/dbt).
  - Some images/nested fields need flattening for tabular export.

Usage:
  python3 scripts/_export.py <input.jsonl> <format> [output_path]

  format ∈ {csv, json, parquet}

Examples:
  python3 scripts/_export.py data/posts/<slug>/clean.jsonl csv
  python3 scripts/_export.py data/posts/<slug>/clean.jsonl parquet
  python3 scripts/_export.py data/posts/<slug>/clean.jsonl json out.json

Output paths (default if not provided):
  csv: <input_stem>.csv
  parquet: <input_stem>.parquet
  json: <input_stem>.json

Schema (flat):
  record_id          — stable hash of (post_id|author|text[:80])
  post_url           — original post URL
  type               — "comment" | "reply"
  author             — author name
  author_id          — (may be null)
  profile_url        — author profile URL (may have query params stripped)
  text               — comment text (truncated to 5000)
  timestamp_raw      — "12 hours ago" / ISO / etc.
  time_iso           — ISO parse attempt (null if raw is relative)
  reactions_total    — (may be null)
  n_images           — count of images
  image_urls         — pipe-separated list
  parent_comment_id  — for replies (may be null)
  scraped_at         — ISO timestamp
  source_file        — path of the JSONL file
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# -----------------------------------------------------------------------
# Field flatteners
# -----------------------------------------------------------------------

def _safe_str(v) -> str:
    if v is None:
        return ""
    return str(v)


def _flatten(record: dict, source_file: str) -> dict:
    """Flatten a comment/reply record into a tabular row."""
    images = record.get("images") or []
    image_urls = "|".join(
        (img.get("src") if isinstance(img, dict) else img) or "" for img in images
    )
    text = record.get("text") or ""
    author = record.get("author") or ""
    post_url = record.get("post_url") or ""
    profile_url = record.get("profile_url") or ""
    if profile_url and "?" in profile_url:
        # Keep profile path but strip tracking params
        profile_url = profile_url.split("?")[0]

    timestamp_raw = record.get("timestamp_raw") or record.get("time") or ""
    time_iso = _parse_iso_or_relative(timestamp_raw)

    # Stable record ID (cross-run dedup key)
    key_material = f"{post_url}|{author}|{text[:80]}"
    record_id = hashlib.sha256(key_material.encode("utf-8")).hexdigest()[:16]

    return {
        "record_id": record_id,
        "post_url": post_url,
        "type": record.get("type") or "comment",
        "author": author,
        "author_id": record.get("author_id") or "",
        "profile_url": profile_url,
        "text": text,
        "timestamp_raw": timestamp_raw,
        "time_iso": time_iso or "",
        "reactions_total": record.get("reactions_total") or "",
        "n_images": len(images),
        "image_urls": image_urls,
        "parent_comment_id": record.get("parent_comment_id") or "",
        "scraped_at": record.get("scraped_at") or "",
        "source_file": source_file,
    }


_RELATIVE_PATTERN = re.compile(
    r"(\d+|a|an)\s+(second|minute|hour|day|week|month|year)s?\s+ago|"
    r"just\s+now|yesterday",
    re.IGNORECASE,
)


def _parse_iso_or_relative(raw: str) -> str | None:
    """Best-effort ISO conversion. Returns None if can't parse."""
    if not raw:
        return None
    raw = raw.strip()
    # Try ISO first
    try:
        # Handle common variants
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw).isoformat()
    except Exception:
        pass
    # Relative → return as-is (no synthetic date to avoid misleading data)
    return None


# -----------------------------------------------------------------------
# Format writers
# -----------------------------------------------------------------------

CSV_COLUMNS = [
    "record_id", "post_url", "type", "author", "author_id", "profile_url",
    "text", "timestamp_raw", "time_iso", "reactions_total", "n_images",
    "image_urls", "parent_comment_id", "scraped_at", "source_file",
]


def write_csv(input_path: Path, output_path: Path) -> int:
    """Write JSONL → CSV. Returns row count."""
    n = 0
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for line in input_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            writer.writerow(_flatten(rec, str(input_path)))
            n += 1
    return n


def write_json(input_path: Path, output_path: Path) -> int:
    """Write JSONL → JSON array (flattened). Returns row count."""
    rows = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        rows.append(_flatten(rec, str(input_path)))
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return len(rows)


def write_parquet(input_path: Path, output_path: Path) -> int:
    """Write JSONL → Parquet (requires pyarrow). Returns row count."""
    try:
        import pyarrow as pa  # noqa: F401
        import pyarrow.parquet as pq  # noqa: F401
    except ImportError:
        print("ERROR: pyarrow not installed. Run: pip install pyarrow",
              file=sys.stderr)
        sys.exit(1)
    rows = []
    for line in input_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        rows.append(_flatten(rec, str(input_path)))
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, str(output_path))
    return len(rows)


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export clean JSONL to CSV/JSON/Parquet for analytics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", help="Input JSONL file (e.g. clean.jsonl)")
    parser.add_argument("format", choices=["csv", "json", "parquet"],
                        help="Output format")
    parser.add_argument("output", nargs="?", default=None,
                        help="Output path (default: <input_stem>.<ext>)")
    args = parser.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        parser.error(f"Input file not found: {inp}")

    # Default output path
    if args.output:
        out = Path(args.output)
    else:
        ext = {"csv": "csv", "json": "json", "parquet": "parquet"}[args.format]
        out = inp.with_suffix(f".{ext}")

    # Dispatch
    writers = {
        "csv": write_csv,
        "json": write_json,
        "parquet": write_parquet,
    }
    n = writers[args.format](inp, out)
    print(f"✓ Exported {n} records: {inp} → {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()