"""Kiểm tra đọc dữ liệu/chia tập/nhãn của pipeline PhoBERT bằng DataFrame tổng hợp (không tải model).

Chạy: py -3.14 -m pytest ml/phobert/tests -q   (từ thư mục gốc repo)
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phobert_config import TrainConfig  # noqa: E402
from phobert_data import (make_collate, normalize_label, prepare_dataframe,  # noqa: E402
                          read_table, split_data)
from phobert_train import class_weight_tensor  # noqa: E402

EDU = ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng"]


def make_df(n_events=10, per_event=20):
    rows = []
    for e in range(n_events):
        for i in range(per_event):
            rows.append({"comment_id": f"e{e}_{i}", "event_id": f"education_{e:03d}",
                         "text": f"nội dung {e} {i}", "llm_stance": EDU[i % 4],
                         "is_trash": "False", "verified_label": EDU[(i + 1) % 4]})
    return pd.DataFrame(rows)


def test_normalize_label_handles_case_typo_alias():
    from phobert_config import DOMAIN_LABELS
    sh = DOMAIN_LABELS["showbiz"]
    assert normalize_label(" ứng hộ ", sh) == "Ủng hộ"        # lỗi chính tả đã gặp trong dữ liệu
    assert normalize_label("PHẪN NỘ", sh) == "Phẫn nộ"
    assert normalize_label("rác", sh) == "is_trash"
    assert normalize_label("nhãn lạ", sh) is None and normalize_label(float("nan"), sh) is None


def test_label_rules_verified_overrides_trash_and_llm_fallback():
    df = pd.DataFrame([
        {"text": "a", "llm_stance": "rác", "is_trash": "True", "verified_label": "tích cực"},
        {"text": "b", "llm_stance": "tiêu cực", "is_trash": "False", "verified_label": None},
        {"text": "c", "llm_stance": None, "is_trash": "True", "verified_label": None},
        {"text": "d", "llm_stance": "x", "is_trash": "False", "verified_label": "sai nhãn"},
    ])
    strict, *_ , dropped = prepare_dataframe(df, TrainConfig(domain="education", label_source="verified"))
    assert strict["final_label"].tolist() == ["tích cực"]          # chỉ dòng có verified hợp lệ
    assert dropped["verified_label_không_hợp_lệ"] == 1 and dropped["chưa_có_verified_label"] == 2
    assert TrainConfig().label_source == "verified_or_llm"          # mặc định: dùng nhãn cuối đã gộp
    loose, *_ = prepare_dataframe(df, TrainConfig(domain="education"))
    assert loose["final_label"].tolist() == ["tích cực", "tiêu cực", "is_trash"]


def test_event_split_disjoint_and_frozen_eval():
    cfg = TrainConfig(domain="education")
    df, *_ = prepare_dataframe(make_df(), cfg)
    tr, va, te = split_data(df, cfg)
    ev = lambda d: set(d["event_id"])
    assert not (ev(tr) & ev(va)) and not (ev(tr) & ev(te)) and not (ev(va) & ev(te))
    assert len(tr) + len(va) + len(te) == len(df) and len(va) > 0 and len(te) > 0
    frozen = set(df["comment_id"].iloc[:30])
    tr2, va2, te2 = split_data(df, cfg, eval_ids=frozen)
    assert set(te2["comment_id"]) == frozen
    assert not (frozen & set(tr2["comment_id"])) and not (frozen & set(va2["comment_id"]))


def test_event_split_balances_labels_and_is_deterministic():
    rows = []
    for e, size in enumerate([300, 120, 90, 80, 70, 60, 50, 40, 30, 20]):   # sự kiện lệch cỡ như dữ liệu thật
        for i in range(size):
            rows.append({"comment_id": f"e{e}_{i}", "event_id": f"education_{e:03d}", "text": f"t{e}_{i}",
                         "llm_stance": EDU[(i + e) % 4], "is_trash": "False", "verified_label": None})
    cfg = TrainConfig(domain="education")
    df, *_ = prepare_dataframe(pd.DataFrame(rows), cfg)
    a, b = split_data(df, cfg), split_data(df, cfg)
    assert [d["comment_id"].tolist() for d in a] == [d["comment_id"].tolist() for d in b]
    for part in a[1:]:                       # val/test: >=3 sự kiện và đủ 4 lớp
        assert part["event_id"].nunique() >= 3 and part["label_id"].nunique() == 4


def test_row_split_stratified_and_deterministic():
    cfg = TrainConfig(domain="education", split_mode="row")
    df, *_ = prepare_dataframe(make_df(), cfg)
    a = split_data(df, cfg)
    b = split_data(df, cfg)
    assert [d["comment_id"].tolist() for d in a] == [d["comment_id"].tolist() for d in b]
    assert sorted(len(d) for d in a) == sorted([len(a[0]), len(a[1]), len(a[2])])


def test_missing_text_column_raises_clear_error():
    with pytest.raises(KeyError, match="Thiếu cột"):
        prepare_dataframe(pd.DataFrame({"x": [1]}), TrainConfig(domain="education"))


def test_class_weights_ignore_absent_class_and_collate_pads():
    import numpy as np
    w = class_weight_tensor(np.array([0, 0, 0, 1]), 3, "cpu")
    assert w[0] < w[1] and w[2] == 1.0
    batch = make_collate(1)([{"input_ids": [5, 6, 7], "label": 0}, {"input_ids": [8], "label": 1}])
    assert batch["input_ids"].tolist() == [[5, 6, 7], [8, 1, 1]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [1, 0, 0]]


def test_read_table_drops_blank_rows(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("text,verified_label\na,tích cực\n,\n", encoding="utf-8-sig")
    assert len(read_table(str(p))) == 1
