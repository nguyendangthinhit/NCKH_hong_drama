#!/usr/bin/env python3
import os
import json
import argparse
import sys

def value_is_true(v):
    if v is True:
        return True
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    if isinstance(v, (int, float)):
        return v == 1
    return False

def count_in_obj(obj):
    total = 0
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                if not value_is_true(item.get('is_trash', False)):
                    total += 1
    elif isinstance(obj, dict):
        if 'comments' in obj and isinstance(obj['comments'], list):
            for item in obj['comments']:
                if isinstance(item, dict) and not value_is_true(item.get('is_trash', False)):
                    total += 1
        else:
            if not value_is_true(obj.get('is_trash', False)):
                total = 1
    return total

def process_file(path):
    count = 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
            text_strip = text.strip()
            if not text_strip:
                return 0
            try:
                data = json.loads(text_strip)
                return count_in_obj(data)
            except json.JSONDecodeError:
                f.seek(0)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, list):
                        for it in item:
                            if isinstance(it, dict) and not value_is_true(it.get('is_trash', False)):
                                count += 1
                    elif isinstance(item, dict):
                        if not value_is_true(item.get('is_trash', False)):
                            count += 1
                return count
    except Exception as e:
        print(f"Error reading {path}: {e}", file=sys.stderr)
    return count

def main():
    parser = argparse.ArgumentParser(description='Count comments where is_trash is not true')
    parser.add_argument('root', nargs='?', default=os.path.join('data', 'process_education', 'analyzed_dataa', 'full'))
    parser.add_argument('--ext', default='', help='Only process files with this extension (e.g. .json). Empty = auto')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    root = args.root
    total = 0
    if not os.path.exists(root):
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(2)

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if args.ext:
                if not fn.lower().endswith(args.ext.lower()):
                    continue
            else:
                if not (fn.lower().endswith('.json') or fn.lower().endswith('.jsonl') or fn.lower().endswith('.ndjson')):
                    continue
            path = os.path.join(dirpath, fn)
            c = process_file(path)
            total += c
            if args.verbose:
                print(f"{path}: {c}")

    print(f"Total non-trash comments: {total}")

if __name__ == '__main__':
    main()
