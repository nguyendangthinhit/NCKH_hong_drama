#!/usr/bin/env python3
"""
count_comments.py
------------------
Đếm tổng số comment (top-level + replies) cho từng `id_content`
trong các file JSON của thư mục input và lưu kết quả ra JSON.

Usage:
    python count_comments.py <input_dir_or_file> -o <output.json>

Example:
    python count_comments.py input_clean_data -o total_comments.json
"""

import os
import sys
import json
import argparse


def count_in_entry(entry):
    comments = entry.get("comments", [])
    total = 0
    for c in comments:
        total += 1
        # replies may be absent or a list
        total += len(c.get("replies", []))
    return total


def process_file(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries = raw if isinstance(raw, list) else [raw]
    counts = {}
    for entry in entries:
        idc = entry.get("id_content") or os.path.splitext(os.path.basename(path))[0]
        counts[idc] = counts.get(idc, 0) + count_in_entry(entry)
    return counts


def main():
    parser = argparse.ArgumentParser(description="Count comments per id_content and save JSON")
    parser.add_argument("input", help="Input file or directory containing .json files")
    parser.add_argument("-o", "--output", default="total_comments.json",
                        help="Output JSON file (default: total_comments.json)")
    args = parser.parse_args()

    if os.path.isfile(args.input):
        files = [args.input]
    elif os.path.isdir(args.input):
        files = [os.path.join(args.input, f) for f in sorted(os.listdir(args.input)) if f.endswith('.json')]
    else:
        print("Input path not found:", args.input, file=sys.stderr)
        sys.exit(2)

    totals = {}
    for p in files:
        try:
            counts = process_file(p)
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v
        except Exception as e:
            print(f"Warning: skipped {p}: {e}", file=sys.stderr)

    with open(args.output, "w", encoding="utf-8") as out:
        json.dump(totals, out, ensure_ascii=False, indent=2)

    print(f"Wrote totals for {len(totals)} id_content -> {args.output}")


if __name__ == '__main__':
    main()
