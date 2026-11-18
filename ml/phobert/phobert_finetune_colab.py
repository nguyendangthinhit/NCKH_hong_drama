"""
Fine-tune PhoBERT phân loại bình luận (Showbiz 6 lớp / Giáo dục 5 lớp, gồm is_trash).

Chạy trên Colab/GPU khi có dữ liệu gán lại:
    !python phobert_finetune_colab.py --domain showbiz --data_path /content/labeled_showbiz_final.csv
    !python phobert_finetune_colab.py --domain education --data_path /content/labeled_education_final.csv \
        --eval_file /content/eval_set_education.xlsx      # tập đánh giá đóng băng (tuỳ chọn)
Dữ liệu: `labeling data/labeled_{domain}_final.csv` (đã bỏ id trùng, có cột final_label để đối chiếu).

Kiểm tra nhanh pipeline không cần tải model/dữ liệu thật: thêm --smoke
(encoder nhỏ ngẫu nhiên, kết quả KHÔNG có ý nghĩa).

Đầu ra trong {output_dir}/{domain}/: best_model.pt, config.json, test_results.json,
split_manifest.json (comment_id từng tập, để tái lập và đối chiếu với GNN).
Module: phobert_config (nhãn/cột), phobert_data (đọc+chia), phobert_segmenter,
phobert_model, phobert_train (vòng train).
"""

import argparse
import dataclasses
import json
import os
import random

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from phobert_config import ColumnMap, DOMAIN_LABELS, TrainConfig
from phobert_data import (CommentDataset, make_collate, prepare_dataframe, read_table,
                          split_data, write_split_manifest)
from phobert_model import PhoBERTClassifier
from phobert_segmenter import get_segmenter
from phobert_train import class_weight_tensor, fit, test_report


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--domain", choices=list(DOMAIN_LABELS), required=True)
    p.add_argument("--data_path", required=True, help="xlsx hoặc csv đã gán nhãn")
    p.add_argument("--eval_file", help="tập đánh giá đóng băng: dùng làm test, loại khỏi train/val")
    p.add_argument("--output_dir", default="/content/phobert_checkpoints")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=2e-5)
    p.add_argument("--patience", type=int, default=3)
    p.add_argument("--max_length", type=int, default=256)
    p.add_argument("--label_source", choices=["verified", "verified_or_llm"], default="verified_or_llm")
    p.add_argument("--split_mode", choices=["event", "row"], default="event")
    p.add_argument("--segmenter", choices=["underthesea", "none"], default="underthesea")
    p.add_argument("--smoke", action="store_true", help="encoder nhỏ ngẫu nhiên, chỉ kiểm pipeline")
    for f in ("text", "event_id", "comment_id", "verified_label", "is_trash", "llm_label"):
        p.add_argument(f"--{f.replace('_', '-')}-col", dest=f"col_{f}", default=getattr(ColumnMap(), f))
    return p.parse_args()


def main():
    a = parse_args()
    cols = ColumnMap(**{f: getattr(a, f"col_{f}") for f in
                        ("text", "event_id", "comment_id", "verified_label", "is_trash", "llm_label")})
    cfg = TrainConfig(domain=a.domain, epochs=a.epochs, batch_size=a.batch_size, lr=a.lr,
                      patience=a.patience, max_length=a.max_length, label_source=a.label_source,
                      split_mode=a.split_mode, segmenter=a.segmenter, columns=cols)
    set_seed(cfg.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    df, label2id, id2label, dropped = prepare_dataframe(read_table(a.data_path), cfg)
    print(f"Dòng dùng được: {len(df)}; loại bỏ: {dropped}")
    print(df["final_label"].value_counts().to_string())
    if len(df) < 30:
        raise SystemExit("Quá ít dòng có nhãn (<30). Kiểm tra cột nhãn/--label_source.")
    eval_ids = None
    if a.eval_file:
        ev = read_table(a.eval_file)
        eval_ids = set(ev[cols.comment_id].astype(str))
        df[cols.comment_id] = df[cols.comment_id].astype(str)
    train_df, val_df, test_df = split_data(df, cfg, eval_ids=eval_ids)
    print(f"Chia ({cfg.split_mode}): train={len(train_df)} val={len(val_df)} test={len(test_df)}")
    if len(test_df) == 0 or len(val_df) == 0:
        raise SystemExit("Tập val/test rỗng: dữ liệu quá ít sự kiện, thử --split_mode row.")

    seg = get_segmenter(cfg.segmenter)
    tok = AutoTokenizer.from_pretrained(cfg.model_name)
    collate = make_collate(tok.pad_token_id)
    mk = lambda d, shuffle: DataLoader(
        CommentDataset([seg(t) for t in d[cols.text]], d["label_id"], tok, cfg.max_length),
        batch_size=cfg.batch_size, shuffle=shuffle, collate_fn=collate)
    train_loader, val_loader, test_loader = mk(train_df, True), mk(val_df, False), mk(test_df, False)

    model = PhoBERTClassifier(len(label2id), cfg.model_name, cfg.dropout, smoke=a.smoke).to(device)
    criterion = torch.nn.CrossEntropyLoss(
        weight=class_weight_tensor(train_df["label_id"].to_numpy(), len(label2id), device))
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    total = len(train_loader) * cfg.epochs
    sched = get_linear_schedule_with_warmup(opt, int(cfg.warmup_ratio * total), total)

    save_dir = os.path.join(a.output_dir, cfg.domain)
    os.makedirs(save_dir, exist_ok=True)
    write_split_manifest(os.path.join(save_dir, "split_manifest.json"), cfg, train_df, val_df, test_df)
    config = dataclasses.asdict(cfg) | {
        "num_labels": len(label2id), "label2id": label2id, "id2label": id2label,
        "smoke": a.smoke, "dropped": dropped, "frozen_eval_file": a.eval_file}
    with open(os.path.join(save_dir, "config.json"), "w", encoding="utf-8") as fh:
        json.dump(config, fh, ensure_ascii=False, indent=2)

    best, ran = fit(model, train_loader, val_loader, opt, sched, criterion, device,
                    cfg.epochs, cfg.patience, save_dir)
    model.load_state_dict(torch.load(os.path.join(save_dir, "best_model.pt"),
                                     map_location=device)["model_state_dict"])
    results = test_report(model, test_loader, criterion, device, id2label)
    results |= {"best_val_f1": float(best), "epochs_run": ran, "smoke": a.smoke}
    with open(os.path.join(save_dir, "test_results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"Test F1 macro: {results['test_f1_macro']:.4f}  -> {save_dir}")


if __name__ == "__main__":
    main()
