"""
Extract TF-IDF features per domain.

Input: data/gnn/graphs_{domain}.pkl
Output: data/gnn/tfidf_{domain}.npz (sparse matrix) + tfidf_vocab_{domain}.json

Mỗi domain TF-IDF riêng (vocab, idf riêng) vì topic khác nhau.
Top 300 features theo max_df + min_df default.

Usage:
    python extract_tfidf_features.py --domain education
"""

import argparse
import json
import pickle
import re
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

OUTPUT_DIR = Path("data/gnn")
N_FEATURES = 300


def normalize_text(t: str) -> str:
    """Lowercase + strip, collapse whitespace. Giữ tiếng Việt."""
    if not t:
        return ""
    t = t.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def extract_for_domain(domain: str):
    pkl = OUTPUT_DIR / f"graphs_{domain}.pkl"
    with open(pkl, "rb") as fh:
        graphs = pickle.load(fh)

    # Flatten: tất cả node thành 1 list, giữ thứ tự để map ngược
    all_texts = []
    node_ids = []
    for g in graphs:
        for nid, txt in zip(g["node_ids"], g["texts"]):
            node_ids.append(f"{g['event_id']}::{nid}")
            all_texts.append(normalize_text(txt))

    print(f"[{domain}] Fitting TF-IDF on {len(all_texts)} comments")
    vec = TfidfVectorizer(
        max_features=N_FEATURES,
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.9,
        token_pattern=r"(?u)\b\w+\b",
    )
    X = vec.fit_transform(all_texts)
    print(f"[{domain}] TF-IDF matrix shape: {X.shape}, nnz: {X.nnz}")

    out_npz = OUTPUT_DIR / f"tfidf_{domain}.npz"
    out_vocab = OUTPUT_DIR / f"tfidf_vocab_{domain}.json"
    out_ids = OUTPUT_DIR / f"tfidf_node_ids_{domain}.json"
    sp.save_npz(out_npz, X)
    # numpy int64 -> int để json serializable
    vocab_serializable = {k: int(v) for k, v in vec.vocabulary_.items()}
    with open(out_vocab, "w", encoding="utf-8") as fh:
        json.dump(vocab_serializable, fh, ensure_ascii=False)
    with open(out_ids, "w", encoding="utf-8") as fh:
        json.dump(node_ids, fh, ensure_ascii=False)
    print(f"[{domain}] Saved {out_npz}, vocab ({len(vec.vocabulary_)}), node_ids ({len(node_ids)})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        extract_for_domain(d)


if __name__ == "__main__":
    main()
