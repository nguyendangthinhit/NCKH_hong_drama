"""
Extract PhoBERT [CLS] embedding 768d cho mỗi comment.

PhoBERT-base-v2 frozen — KHÔNG fine-tune. Dùng làm encoder text → vector.
Chạy trên Colab GPU (T4) ~10-15 phút cho 26k comments.

Input:  data/gnn/graphs_{domain}.pkl
Output: data/gnn/phobert_{domain}.npy (float32, shape [N, 768])
        data/gnn/phobert_node_ids_{domain}.json (thứ tự node)

Usage:
    python extract_phobert_features.py --domain education --batch-size 32
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

OUTPUT_DIR = Path("data/gnn")
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 256


def extract_for_domain(domain: str, batch_size: int = 32, device: str = None):
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[{domain}] Device: {device}")

    pkl = OUTPUT_DIR / f"graphs_{domain}.pkl"
    with open(pkl, "rb") as fh:
        graphs = pickle.load(fh)

    all_texts = []
    node_ids = []
    for g in graphs:
        for nid, txt in zip(g["node_ids"], g["texts"]):
            node_ids.append(f"{g['event_id']}::{nid}")
            all_texts.append(txt or "")

    print(f"[{domain}] Loading PhoBERT...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    model.eval()

    n = len(all_texts)
    embeds = np.zeros((n, 768), dtype=np.float32)
    print(f"[{domain}] Encoding {n} comments, batch_size={batch_size}")

    with torch.no_grad():
        for i in range(0, n, batch_size):
            batch = all_texts[i:i + batch_size]
            enc = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            ).to(device)
            out = model(**enc)
            # [CLS] token = position 0
            cls = out.last_hidden_state[:, 0, :].cpu().numpy()
            embeds[i:i + len(batch)] = cls
            if (i // batch_size) % 50 == 0:
                print(f"[{domain}] {i}/{n}")

    out_npy = OUTPUT_DIR / f"phobert_{domain}.npy"
    out_ids = OUTPUT_DIR / f"phobert_node_ids_{domain}.json"
    np.save(out_npy, embeds)
    with open(out_ids, "w", encoding="utf-8") as fh:
        json.dump(node_ids, fh, ensure_ascii=False)
    print(f"[{domain}] Saved {out_npy} shape={embeds.shape}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        extract_for_domain(d, args.batch_size, args.device)


if __name__ == "__main__":
    main()
