"""Đọc dữ liệu gán nhãn (xlsx/csv), chuẩn hoá nhãn, chia train/val/test, Dataset.

Quy tắc nhãn cuối của một dòng:
  1. có verified_label  -> dùng nó (kể cả khi is_trash=True: người gán đã sửa lại)
  2. không có, is_trash -> "is_trash"          (chỉ khi label_source=verified_or_llm)
  3. không có           -> nhãn LLM            (chỉ khi label_source=verified_or_llm)
Nhãn không thuộc danh sách của lĩnh vực bị loại và được thống kê ra log.
"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from phobert_config import (DOMAIN_LABELS, LABEL_ALIASES, LLM_LABEL_COL,
                            TRASH_LABEL, TrainConfig)


def read_table(path: str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(p, dtype=object)
    else:
        df = pd.read_csv(p, encoding="utf-8-sig", dtype=object)
    return df.dropna(how="all").reset_index(drop=True)  # xlsx hay có dòng trống ở cuối


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() in ("", "nan", "None")


def normalize_label(v, valid: list):
    """Trả nhãn chuẩn hoặc None. Khớp không phân biệt hoa thường/khoảng trắng + bảng alias."""
    if _blank(v):
        return None
    key = " ".join(str(v).split()).lower()
    by_lower = {l.lower(): l for l in valid}
    if key in by_lower:
        return by_lower[key]
    alias = LABEL_ALIASES.get(key)
    return alias if alias in valid else None


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "1.0", "yes", "x")


def prepare_dataframe(df: pd.DataFrame, cfg: TrainConfig):
    """Thêm cột final_label/label_id; trả (df_hợp_lệ, label2id, id2label, thống kê loại bỏ)."""
    c, valid = cfg.columns, DOMAIN_LABELS[cfg.domain]
    llm_col = c.llm_label or LLM_LABEL_COL[cfg.domain]
    for col in (c.text,):
        if col not in df.columns:
            raise KeyError(f"Thiếu cột '{col}'. Cột hiện có: {list(df.columns)}")
    verified = df[c.verified_label] if c.verified_label in df.columns else pd.Series([None] * len(df))
    trash = df[c.is_trash].map(_truthy) if c.is_trash in df.columns else pd.Series([False] * len(df))
    llm = df[llm_col] if llm_col in df.columns else pd.Series([None] * len(df))

    final, dropped = [], Counter()
    for v, t, l in zip(verified, trash, llm):
        lab = normalize_label(v, valid)
        if lab is None and not _blank(v):
            dropped["verified_label_không_hợp_lệ"] += 1
        elif lab is None and cfg.label_source == "verified_or_llm":
            lab = TRASH_LABEL if t else normalize_label(l, valid)
        elif lab is None:
            dropped["chưa_có_verified_label"] += 1
        final.append(lab)
    out = df.copy()
    out["final_label"] = final
    has_text = out[c.text].map(lambda s: not _blank(s))
    dropped["thiếu_text"] = int((out["final_label"].notna() & ~has_text).sum())
    out = out[out["final_label"].notna() & has_text].reset_index(drop=True)
    label2id = {l: i for i, l in enumerate(valid)}
    out["label_id"] = out["final_label"].map(label2id).astype(int)
    return out, label2id, {i: l for l, i in label2id.items()}, dict(dropped)


def _greedy_assign(events, counts, targets):
    got, assign = {"test": 0, "val": 0}, {}
    for ev in events:
        for name in ("test", "val"):
            if got[name] < targets[name]:
                assign[ev] = name
                got[name] += counts[ev]
                break
        else:
            assign[ev] = "train"
    return assign


def _split_cost(assign, by_ev, overall, targets, n):
    """Lệch cỡ tập + lệch phân bố nhãn so với toàn bộ + phạt tập ít sự kiện / thiếu lớp."""
    cost = 0.0
    for name, target in targets.items():
        if target == 0:
            continue
        members = [e for e, a in assign.items() if a == name]
        cnt = by_ev.loc[members].sum().to_numpy() if members else np.zeros(len(overall))
        size = cnt.sum()
        cost += abs(size - target) / n
        cost += 0.5 * np.abs(cnt / max(size, 1) - overall).sum()
        cost += 1.0 * (len(members) < 3) + 0.3 * int(((cnt == 0) & (overall > 0)).sum())
    return cost


def _event_split(df, event_col, seed, val_size, test_size, tries=300):
    """Chia nguyên sự kiện (không rò rỉ). Thử `tries` hoán vị sự kiện có seed, chọn cách chia
    có phân bố nhãn gần toàn bộ nhất: chia ngẫu nhiên một lần hay làm val/test chỉ có 1 sự kiện."""
    rng = np.random.RandomState(seed)
    counts = df.groupby(event_col).size()
    by_ev = pd.crosstab(df[event_col], df["label_id"])
    overall = by_ev.sum().to_numpy() / len(df)
    targets = {"test": test_size * len(df), "val": val_size * len(df)}
    best, best_cost = None, np.inf
    for _ in range(tries):
        events = counts.index.to_numpy().copy()
        rng.shuffle(events)
        assign = _greedy_assign(events, counts, targets)
        cost = _split_cost(assign, by_ev, overall, targets, len(df))
        if cost < best_cost:
            best, best_cost = assign, cost
    part = df[event_col].map(best)
    return df[part == "train"], df[part == "val"], df[part == "test"]


def split_data(df: pd.DataFrame, cfg: TrainConfig, val_size=0.15, test_size=0.15, eval_ids=None):
    """Trả (train, val, test). eval_ids: tập comment_id đóng băng -> làm test, loại khỏi train/val."""
    from sklearn.model_selection import train_test_split

    c = cfg.columns
    frozen = None
    if eval_ids is not None:
        mask = df[c.comment_id].isin(eval_ids)
        frozen, df = df[mask], df[~mask]
        test_size = 0.0
    if cfg.split_mode == "event" and c.event_id in df.columns:
        if frozen is not None:
            tr, va, _ = _event_split(df, c.event_id, cfg.seed, val_size, 0.0)
            return tr, va, frozen
        return _event_split(df, c.event_id, cfg.seed, val_size, test_size)
    strat = df["label_id"] if df["label_id"].value_counts().min() >= 3 else None
    if frozen is not None:
        tr, va = train_test_split(df, test_size=val_size, stratify=strat, random_state=cfg.seed)
        return tr, va, frozen
    tr, te = train_test_split(df, test_size=test_size, stratify=strat, random_state=cfg.seed)
    strat2 = tr["label_id"] if tr["label_id"].value_counts().min() >= 3 else None
    tr, va = train_test_split(tr, test_size=val_size / (1 - test_size), stratify=strat2,
                              random_state=cfg.seed)
    return tr, va, te


def write_split_manifest(path, cfg, train, val, test):
    ids = lambda d: d[cfg.columns.comment_id].astype(str).tolist() \
        if cfg.columns.comment_id in d.columns else d.index.astype(str).tolist()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"train": ids(train), "val": ids(val), "test": ids(test)}, fh, ensure_ascii=False)


class CommentDataset(Dataset):
    """Tokenize trước (đã word-segment), pad động theo batch qua collate_fn."""

    def __init__(self, texts, labels, tokenizer, max_length):
        self.enc = tokenizer(list(texts), max_length=max_length, truncation=True)
        self.labels = list(labels)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        return {"input_ids": self.enc["input_ids"][i], "label": self.labels[i]}


def make_collate(pad_id: int):
    def collate(batch):
        width = max(len(b["input_ids"]) for b in batch)
        ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
        mask = torch.zeros((len(batch), width), dtype=torch.long)
        for i, b in enumerate(batch):
            n = len(b["input_ids"])
            ids[i, :n] = torch.tensor(b["input_ids"])
            mask[i, :n] = 1
        return {"input_ids": ids, "attention_mask": mask,
                "label": torch.tensor([b["label"] for b in batch], dtype=torch.long)}
    return collate
