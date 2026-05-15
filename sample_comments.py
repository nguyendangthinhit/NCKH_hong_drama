#!/usr/bin/env python3
import os
import json
import argparse
import random
import sys
from collections import defaultdict

DEFAULT_SHOW = os.path.join('data', 'showbiz_comments_new.json')
# DEFAULT_EDU = os.path.join('data', 'education_comments_new.json')
OUT_SHOW = os.path.join('data', 'data_test_show.json')
# OUT_EDU = os.path.join('data', 'data_test_edu.json')

# Stratified sampling config for showbiz: emotion -> number of samples
EMOTION_SAMPLES = {
    'null':20, # rác
    'Ủng hộ': 20,      # support
    'Đồng cảm': 40,    # empathy
    'Phẫn nộ': 80,     # anger
    'Cà khịa': 80,     # sarcasm
    'Trung lập': 80    # neutral
}

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

def normalize_emotion(emotion):
    """Normalize emotion values and handle None/empty values"""
    if emotion is None or emotion == '':
        return 'null'  # Keep null as 'null' string for stratified sampling
    # Map variations to canonical form
    emotion_map = {
        'Ứng hộ': 'Ủng hộ',  # normalize both support variations
    }
    return emotion_map.get(emotion, emotion)

def extract_fields(item):
    text = item.get('text', '') if isinstance(item, dict) else ''
    # Prefer 'emotion', fallback to 'stance'
    emotion = item.get('emotion') if isinstance(item, dict) else None
    if emotion is None:
        emotion = item.get('stance') if isinstance(item, dict) else None
    # Let normalize_emotion handle None values
    emotion = normalize_emotion(emotion)
    return {'text': text, 'emotion': emotion}

def sample_stratified(src_path, out_path, emotion_samples, seed=None):
    """Sample comments using stratified sampling by emotion"""
    if not os.path.exists(src_path):
        print(f"Source not found: {src_path}")
        return 0
    
    arr = load_json_array(src_path)
    if not arr:
        print(f"No comments loaded from {src_path}")
        return 0
    
    if seed is not None:
        random.seed(seed)
    
    # Group comments by emotion
    groups = defaultdict(list)
    for item in arr:
        fields = extract_fields(item)
        emotion = fields['emotion']
        groups[emotion].append(fields)
    
    # Sample from each emotion group
    result = []
    for emotion, target_count in emotion_samples.items():
        if emotion in groups:
            available = len(groups[emotion])
            actual_count = min(target_count, available)
            sampled = random.sample(groups[emotion], actual_count)
            result.extend(sampled)
            print(f"  {emotion}: {actual_count}/{target_count} (available: {available})")
        else:
            print(f"  {emotion}: 0/{target_count} (not available)")
    
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return len(result)

def main():
    parser = argparse.ArgumentParser(description='Sample comments with stratified sampling by emotion')
    parser.add_argument('--show-src', default=DEFAULT_SHOW)
    parser.add_argument('--out-show', default=OUT_SHOW)
    parser.add_argument('--seed', type=int, default=None)
    args = parser.parse_args()

    print("Sampling showbiz comments with stratified distribution:")
    k1 = sample_stratified(args.show_src, args.out_show, EMOTION_SAMPLES, args.seed)
    print(f"✓ Wrote {k1} samples to {args.out_show}")
    
    # # EDUCATION COMMENTED OUT - only processing showbiz now
    # print("\nSampling education comments with stratified distribution:")
    # k2 = sample_stratified(args.edu_src, args.out_edu, EMOTION_SAMPLES, args.seed)
    # print(f"✓ Wrote {k2} samples to {args.out_edu}")

if __name__ == '__main__':
    main()
