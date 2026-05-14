#!/usr/bin/env python3
import os
import json
import argparse
import random
import sys

DEFAULT_SHOW = os.path.join('data', 'showbiz_comments_new.json')
DEFAULT_EDU = os.path.join('data', 'education_comments_new.json')
OUT_SHOW = os.path.join('data', 'data_test_show.json')
OUT_EDU = os.path.join('data', 'data_test_edu.json')

def load_json_array(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        # If it's a dict with 'comments' key, return that
        if isinstance(data, dict) and 'comments' in data and isinstance(data['comments'], list):
            return data['comments']
        # Otherwise, try to interpret as list-like
        return []

def extract_fields(item):
    text = item.get('text', '') if isinstance(item, dict) else ''
    # Prefer 'emotion', fallback to 'stance'
    emotion = item.get('emotion') if isinstance(item, dict) else None
    if emotion is None:
        emotion = item.get('stance') if isinstance(item, dict) else ''
    if emotion is None:
        emotion = ''
    return {'text': text, 'emotion': emotion}

def sample_and_write(src_path, out_path, n, seed=None):
    if not os.path.exists(src_path):
        print(f"Source not found: {src_path}")
        return 0
    arr = load_json_array(src_path)
    if not arr:
        print(f"No comments loaded from {src_path}")
        return 0
    if seed is not None:
        random.seed(seed)
    k = min(n, len(arr))
    sampled = random.sample(arr, k)
    result = [extract_fields(item) for item in sampled]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return k

def main():
    parser = argparse.ArgumentParser(description='Sample comments from _new files')
    parser.add_argument('--show-src', default=DEFAULT_SHOW)
    parser.add_argument('--edu-src', default=DEFAULT_EDU)
    parser.add_argument('--out-show', default=OUT_SHOW)
    parser.add_argument('--out-edu', default=OUT_EDU)
    parser.add_argument('-n', type=int, default=300, help='Number of samples per file')
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args()

    k1 = sample_and_write(args.show_src, args.out_show, args.n, args.seed)
    print(f"Wrote {k1} samples to {args.out_show}")
    k2 = sample_and_write(args.edu_src, args.out_edu, args.n, args.seed)
    print(f"Wrote {k2} samples to {args.out_edu}")

if __name__ == '__main__':
    main()
