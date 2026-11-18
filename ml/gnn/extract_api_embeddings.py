"""
Tạo embedding văn bản cho mỗi nút GNN qua API (thay PhoBERT local).

Đầu ra cùng định dạng extract_phobert_features.py để concat_node_features.py
dùng chung:
    data/gnn/apiemb_{domain}.npy            [N, dim] float32
    data/gnn/apiemb_node_ids_{domain}.json  "event_id::comment_id" theo thứ tự graphs.pkl

Usage:
    python extract_api_embeddings.py --domain education
    python extract_api_embeddings.py --domain showbiz --model gemini-embedding-001 --dim 768
    python extract_api_embeddings.py --domain education --limit 200   # chạy thử
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np

from embedding_api_client import (EmbeddingCache, EmbeddingClient,
                                  EmbeddingConfig, load_api_keys)

OUTPUT_DIR = Path("data/gnn")
CACHE_PATH = OUTPUT_DIR / "embedding_cache.sqlite"


def collect_nodes(domain: str):
    with open(OUTPUT_DIR / f"graphs_{domain}.pkl", "rb") as fh:
        graphs = pickle.load(fh)
    ids, texts = [], []
    for g in graphs:
        for nid, text in zip(g["node_ids"], g["texts"]):
            ids.append(f"{g['event_id']}::{nid}")
            texts.append(text)
    return ids, texts


def extract(domain: str, cfg: EmbeddingConfig, limit: int = 0, out_dir: Path = OUTPUT_DIR):
    ids, texts = collect_nodes(domain)
    if limit:
        ids, texts = ids[:limit], texts[:limit]
    print(f"[{domain}] {len(ids)} nút, model={cfg.model}, dim={cfg.dim}")
    client = EmbeddingClient(cfg, load_api_keys(), EmbeddingCache(CACHE_PATH))
    emb = client.embed(texts)
    assert emb.shape == (len(ids), cfg.dim), emb.shape
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / f"apiemb_{domain}.npy", emb)
    with open(out_dir / f"apiemb_node_ids_{domain}.json", "w", encoding="utf-8") as fh:
        json.dump(ids, fh, ensure_ascii=False)
    print(f"[{domain}] đã lưu {emb.shape}, số lần gọi API: {client.api_calls}")
    return emb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    ap.add_argument("--model", default=EmbeddingConfig.model)
    ap.add_argument("--dim", type=int, default=EmbeddingConfig.dim)
    ap.add_argument("--min-interval", type=float, default=0.0, help="giây nghỉ giữa request")
    ap.add_argument("--limit", type=int, default=0, help="chỉ lấy N nút đầu (chạy thử)")
    args = ap.parse_args()
    cfg = EmbeddingConfig(model=args.model, dim=args.dim, min_interval_s=args.min_interval)
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        extract(d, cfg, args.limit)


if __name__ == "__main__":
    main()
