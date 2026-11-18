"""
Concat text-embedding (PhoBERT 768 hoặc API) + TF-IDF + structural (3) thành node features.
Chiều lấy từ dữ liệu (PhoBERT 768 + TF-IDF 300 + 3 = 1071; API dim=768 cho cùng 1071).

Đảm bảo cùng thứ tự node giữa 3 nguồn (theo node_ids list).

Input (--text-emb phobert | api):
    data/gnn/{phobert|apiemb}_{domain}.npy           [N, D]
    data/gnn/{phobert|apiemb}_node_ids_{domain}.json
    data/gnn/tfidf_{domain}.npz              [N, 300] sparse
    data/gnn/tfidf_node_ids_{domain}.json
    data/gnn/graphs_{domain}.pkl             (lấy structural)

Output:
    data/gnn/node_features_{domain}.npy      [N, 1071] float32
    data/gnn/feature_meta_{domain}.json      (vị trí slice từng nguồn)

Usage:
    python concat_node_features.py --domain education
    python concat_node_features.py --domain education --text-emb api
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import scipy.sparse as sp

OUTPUT_DIR = Path("data/gnn")


TEXT_EMB_PREFIX = {"phobert": "phobert", "api": "apiemb"}


def concat_for_domain(domain: str, text_emb: str = "phobert"):
    # Load 3 nguồn
    prefix = TEXT_EMB_PREFIX[text_emb]
    phobert = np.load(OUTPUT_DIR / f"{prefix}_{domain}.npy")
    with open(OUTPUT_DIR / f"{prefix}_node_ids_{domain}.json", encoding="utf-8") as fh:
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

    # Chuẩn hoá thang đo để khối cấu trúc (đếm số, có thể hàng trăm) không át embedding (~0.01-1):
    # embedding chuẩn hoá L2 theo hàng, cấu trúc log1p. TF-IDF đã L2 theo hàng.
    phobert = phobert / np.linalg.norm(phobert, axis=1, keepdims=True).clip(min=1e-8)
    structural = np.log1p(structural)

    # Concat
    feats = np.concatenate([phobert, tfidf, structural], axis=1).astype(np.float32)
    d_txt, d_tfidf = phobert.shape[1], tfidf.shape[1]
    print(f"[{domain}] Concat shape: {feats.shape} ({d_txt} + {d_tfidf} + 3, text-emb={text_emb})")

    out_npy = OUTPUT_DIR / f"node_features_{domain}.npy"
    out_meta = OUTPUT_DIR / f"feature_meta_{domain}.json"
    np.save(out_npy, feats)
    with open(out_meta, "w", encoding="utf-8") as fh:
        json.dump({
            "text_emb": text_emb,
            "normalization": "text L2 theo hàng; structural log1p; tfidf giữ nguyên",
            "text": [0, d_txt],
            "tfidf": [d_txt, d_txt + d_tfidf],
            "structural": [d_txt + d_tfidf, d_txt + d_tfidf + 3],
            "n_nodes": int(feats.shape[0]),
            "dim": int(feats.shape[1]),
        }, fh, indent=2)
    print(f"[{domain}] Saved {out_npy}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    ap.add_argument("--text-emb", choices=list(TEXT_EMB_PREFIX), default="phobert")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        concat_for_domain(d, args.text_emb)


if __name__ == "__main__":
    main()
