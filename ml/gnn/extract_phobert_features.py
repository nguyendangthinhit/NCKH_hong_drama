"""
Extract PhoBERT [CLS] embedding 768d cho mỗi comment.

Hỗ trợ 2 chế độ:
- Pretrained (frozen): dùng vinai/phobert-base-v2 gốc
- Fine-tuned: load checkpoint từ ml/phobert/ (sau khi train xong Phase 02)

Fine-tuned model cho embeddings tốt hơn vì đã học domain-specific features.

Input:  data/gnn/graphs_{domain}.pkl
Output: data/gnn/phobert_{domain}.npy (float32, shape [N, 768])
        data/gnn/phobert_node_ids_{domain}.json (thứ tự node)

Usage:
    # Dùng pretrained (chưa có fine-tuned model)
    python extract_phobert_features.py --domain education --batch-size 32

    # Dùng fine-tuned model (sau khi train xong)
    python extract_phobert_features.py --domain showbiz --checkpoint ml/phobert/checkpoints/showbiz/best_model.pt
"""

import argparse
import json
import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer

OUTPUT_DIR = Path("data/gnn")
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 256


class PhoBERTFeatureExtractor(nn.Module):
    """Wrapper to load fine-tuned PhoBERT and extract [CLS] embeddings."""

    def __init__(self, model_name=MODEL_NAME):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        return outputs.last_hidden_state[:, 0, :]


def load_model(checkpoint_path: str = None, device: str = "cpu"):
    """Load PhoBERT model — fine-tuned checkpoint hoặc pretrained.

    Fine-tuned checkpoint (best_model.pt) chứa state_dict của PhoBERTClassifier
    gồm: bert.* + dropout.* + classifier.*
    Ta chỉ cần load bert.* weights vào feature extractor.
    """
    model = PhoBERTFeatureExtractor(MODEL_NAME)

    if checkpoint_path:
        ckpt_path = Path(checkpoint_path)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

        print(f"  Loading fine-tuned weights from: {ckpt_path}")
        checkpoint = torch.load(ckpt_path, map_location=device)
        state_dict = checkpoint["model_state_dict"]

        # Filter chỉ lấy bert.* weights, bỏ classifier + dropout
        bert_state = {
            k.replace("bert.", "", 1): v
            for k, v in state_dict.items()
            if k.startswith("bert.")
        }
        model.bert.load_state_dict(bert_state)
        print(f"  Loaded {len(bert_state)} weight tensors from fine-tuned model")
    else:
        print("  Using pretrained PhoBERT (no fine-tuning)")

    return model.to(device)


def extract_for_domain(domain: str, batch_size: int = 32,
                       device: str = None, checkpoint: str = None):
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
    model = load_model(checkpoint, device)
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
            cls = model(enc["input_ids"], enc["attention_mask"]).cpu().numpy()
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
    ap.add_argument("--checkpoint", default=None,
                    help="Path to fine-tuned best_model.pt (e.g. ml/phobert/checkpoints/showbiz/best_model.pt)")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        extract_for_domain(d, args.batch_size, args.device, args.checkpoint)


if __name__ == "__main__":
    main()
