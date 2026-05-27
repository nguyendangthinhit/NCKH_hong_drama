"""
Concat PhoBERT (768) + TF-IDF (300) + structural (3) = 1071d node features.

Đảm bảo cùng thứ tự node giữa 3 nguồn (theo node_ids list).

Input:
    data/gnn/phobert_{domain}.npy           [N, 768]
    data/gnn/phobert_node_ids_{domain}.json
    data/gnn/tfidf_{domain}.npz              [N, 300] sparse
    data/gnn/tfidf_node_ids_{domain}.json
    data/gnn/graphs_{domain}.pkl             (lấy structural)

Output:
    data/gnn/node_features_{domain}.npy      [N, 1071] float32
    data/gnn/feature_meta_{domain}.json      (vị trí slice từng nguồn)

Usage:
    python concat_node_features.py --domain education
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import scipy.sparse as sp

OUTPUT_DIR = Path("data/gnn")


def concat_for_domain(domain: str):
    # Load 3 nguồn
    phobert = np.load(OUTPUT_DIR / f"phobert_{domain}.npy")
    with open(OUTPUT_DIR / f"phobert_node_ids_{domain}.json", encoding="utf-8") as fh:
        phobert_ids = json.load(fh)

    tfidf = sp.load_npz(OUTPUT_DIR / f"tfidf_{domain}.npz").toarray().astype(np.float32)
    with open(OUTPUT_DIR / f"tfidf_node_ids_{domain}.json", encoding="utf-8") as fh:
        tfidf_ids = json.load(fh)

    with open(OUTPUT_DIR / f"graphs_{domain}.pkl", "rb") as fh:
        graphs = pickle.load(fh)

    # Build canonical order = order trong graphs.pkl
    canon_ids = []
    structural = []
    for g in graphs:
        for i, nid in enumerate(g["node_ids"]):
            canon_ids.append(f"{g['event_id']}::{nid}")
            structural.append([
                g["structural"]["depth"][i],
                g["structural"]["in_degree"][i],
                g["structural"]["sibling_count"][i],
            ])
    structural = np.array(structural, dtype=np.float32)

    # Verify cùng thứ tự
    assert phobert_ids == canon_ids, f"PhoBERT order mismatch ({domain})"
    assert tfidf_ids == canon_ids, f"TF-IDF order mismatch ({domain})"
    assert phobert.shape[0] == tfidf.shape[0] == structural.shape[0]

    # Concat
    feats = np.concatenate([phobert, tfidf, structural], axis=1).astype(np.float32)
    print(f"[{domain}] Concat shape: {feats.shape} (768 + 300 + 3 = {feats.shape[1]})")

    out_npy = OUTPUT_DIR / f"node_features_{domain}.npy"
    out_meta = OUTPUT_DIR / f"feature_meta_{domain}.json"
    np.save(out_npy, feats)
    with open(out_meta, "w", encoding="utf-8") as fh:
        json.dump({
            "phobert": [0, 768],
            "tfidf": [768, 1068],
            "structural": [1068, 1071],
            "n_nodes": int(feats.shape[0]),
            "dim": int(feats.shape[1]),
        }, fh, indent=2)
    print(f"[{domain}] Saved {out_npy}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        concat_for_domain(d)


if __name__ == "__main__":
    main()
