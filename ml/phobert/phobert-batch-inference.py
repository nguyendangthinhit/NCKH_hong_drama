"""
Batch inference: gán nhãn toàn bộ bình luận bằng PhoBERT đã fine-tune.

Dùng đúng cấu hình lúc train (đọc từ config.json trong model_dir): model, max_length,
segmenter, tên cột text. Nhờ vậy dự đoán nhất quán với dữ liệu đã huấn luyện.

Usage:
    !python phobert-batch-inference.py --model_dir /content/phobert_checkpoints/showbiz \
        --input_path /content/all_showbiz_comments.xlsx --output_path /content/predictions_showbiz.csv
Thêm cột predicted_label, confidence (max softmax, chưa hiệu chỉnh), và prob_<nhãn> cho từng lớp.
Model train với ngữ cảnh sự kiện (config event_context=true): input cần cột event_id; ngữ cảnh lấy
từ event_contexts.json trong model_dir, `--event_context_file` bổ sung/ghi đè (sự kiện mới).
"""

import argparse
import json
import os

import pandas as pd
import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer

from phobert_data import read_table
from phobert_dataset import CommentDataset, make_collate
from phobert_event_context import load_event_contexts, row_contexts
from phobert_model import PhoBERTClassifier
from phobert_segmenter import get_segmenter


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", required=True)
    ap.add_argument("--input_path", required=True, help="xlsx hoặc csv")
    ap.add_argument("--output_path", required=True)
    ap.add_argument("--domain", choices=["showbiz", "education"],
                    help="tuỳ chọn: nếu đặt, phải khớp domain của checkpoint")
    ap.add_argument("--batch_size", type=int, default=32)
    ap.add_argument("--event_context_file", help="JSON {event_id: ngữ cảnh} cho sự kiện mới")
    args = ap.parse_args()

    with open(os.path.join(args.model_dir, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    if args.domain and args.domain != cfg["domain"]:
        raise SystemExit(f"Checkpoint là domain '{cfg['domain']}', không khớp --domain {args.domain}")
    id2label = {int(k): v for k, v in cfg["id2label"].items()}
    text_col = cfg["columns"]["text"]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = PhoBERTClassifier(cfg["num_labels"], cfg["model_name"], cfg["dropout"],
                              smoke=cfg.get("smoke", False))
    ckpt = torch.load(os.path.join(args.model_dir, "best_model.pt"), map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device).eval()

    df = read_table(args.input_path)
    if text_col not in df.columns:
        raise SystemExit(f"Thiếu cột '{text_col}' trong {args.input_path}")
    seg = get_segmenter(cfg["segmenter"])
    tok = AutoTokenizer.from_pretrained(cfg["model_name"])
    texts = [seg("" if pd.isna(t) else t) for t in df[text_col]]
    ctx = None
    if cfg.get("event_context"):
        ev_col = cfg["columns"]["event_id"]
        if ev_col not in df.columns:
            raise SystemExit(f"Model train với ngữ cảnh sự kiện: input cần cột '{ev_col}'")
        saved = os.path.join(args.model_dir, "event_contexts.json")
        if not os.path.exists(saved) and not args.event_context_file:
            raise SystemExit(f"Thiếu {saved}: chép file ngữ cảnh lúc train vào model_dir "
                             "hoặc truyền --event_context_file")
        contexts = load_event_contexts(saved) if os.path.exists(saved) else {}
        if args.event_context_file:
            contexts |= load_event_contexts(args.event_context_file)
        ctx, missing = row_contexts(df[ev_col], contexts, seg)
        if missing:
            print(f"⚠ {missing}/{len(df)} dòng không có ngữ cảnh sự kiện (để rỗng, dự đoán kém hơn)")
    elif args.event_context_file:
        print("⚠ Model train không có ngữ cảnh sự kiện: bỏ qua --event_context_file")
    loader = DataLoader(CommentDataset(texts, [0] * len(texts), tok, cfg["max_length"], ctx),
                        batch_size=args.batch_size, collate_fn=make_collate(tok.pad_token_id))

    probs = []
    print(f"Inference {len(texts)} bình luận trên {device}...")
    with torch.no_grad():
        for b in loader:
            logits = model(b["input_ids"].to(device), b["attention_mask"].to(device))
            probs.append(torch.softmax(logits, dim=1).cpu())
    probs = torch.cat(probs)
    conf, pred = probs.max(dim=1)
    df["predicted_label"] = [id2label[int(p)] for p in pred]
    df["confidence"] = conf.numpy()
    for i, name in sorted(id2label.items()):
        df[f"prob_{name}"] = probs[:, i].numpy()
    df.to_csv(args.output_path, index=False, encoding="utf-8-sig")
    print(f"Đã lưu {args.output_path}")
    print(df["predicted_label"].value_counts().to_string())


if __name__ == "__main__":
    main()
