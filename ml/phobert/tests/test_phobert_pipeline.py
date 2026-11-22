"""Kiểm tra đọc dữ liệu/chia tập/nhãn của pipeline PhoBERT bằng DataFrame tổng hợp (không tải model).

Chạy: py -3.14 -m pytest ml/phobert/tests -q   (từ thư mục gốc repo)
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phobert_config import TrainConfig  # noqa: E402
from phobert_dataset import CommentDataset, make_collate  # noqa: E402
from phobert_data import (normalize_label,  # noqa: E402
                          prepare_dataframe, read_table, split_data)
from phobert_event_context import (build_event_contexts, event_context_text,  # noqa: E402
                                   load_event_contexts, row_contexts)
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


def test_merged_label_column_wins_and_falls_back_to_old_rules():
    df = pd.DataFrame([
        {"text": "a", "label": "ý kiến riêng", "llm_stance": "tiêu cực", "is_trash": "False", "verified_label": None},
        {"text": "b", "label": None, "llm_stance": "tiêu cực", "is_trash": "False", "verified_label": None},
        {"text": "c", "label": "lạ", "llm_stance": None, "is_trash": "True", "verified_label": None},
        {"text": "d", "label": "rác", "llm_stance": "tích cực", "is_trash": "True", "verified_label": None},
    ])
    out, *_, dropped = prepare_dataframe(df, TrainConfig(domain="education"))
    assert out["final_label"].tolist() == ["ý kiến riêng", "tiêu cực", "is_trash", "is_trash"]
    assert dropped["label_không_hợp_lệ_dùng_quy_tắc_cũ"] == 1
    strict, *_ = prepare_dataframe(df, TrainConfig(domain="education", label_source="verified"))
    assert len(strict) == 0                                   # chế độ verified bỏ qua cột label


def test_synthetic_rows_only_in_train_and_can_be_excluded():
    real = make_df()
    syn = pd.DataFrame([{"comment_id": f"syn_{i}", "event_id": f"education_{i % 10:03d}",
                         "text": f"câu sinh {i}", "label": "ý kiến riêng", "is_synthetic": "True"}
                        for i in range(50)])
    df_all = pd.concat([real.assign(is_synthetic="False"), syn], ignore_index=True)
    for mode in ("event", "row"):
        cfg = TrainConfig(domain="education", split_mode=mode)
        df, *_ = prepare_dataframe(df_all, cfg)
        tr, va, te = split_data(df, cfg)
        ids = lambda d: set(d["comment_id"])
        assert not any(i.startswith("syn_") for i in ids(va) | ids(te))
        if mode == "row":
            assert set(syn["comment_id"]) <= ids(tr) and len(tr) + len(va) + len(te) == len(df)
        else:  # chỉ giữ câu sinh của sự kiện train: câu sinh theo sự kiện val/test là rò rỉ
            real_train_events = set(tr[~tr["_synthetic"]]["event_id"])
            kept = syn[syn["event_id"].isin(real_train_events)]
            assert set(tr[tr["_synthetic"]]["comment_id"]) == set(kept["comment_id"])
            assert 0 < len(kept) < len(syn)
        tr2, va2, te2 = split_data(df, cfg, eval_ids=set(real["comment_id"].iloc[:30]))
        assert not any(i.startswith("syn_") for i in ids(va2) | ids(te2))
    no_syn, *_, dropped = prepare_dataframe(df_all, TrainConfig(domain="education", use_synthetic=False))
    assert len(no_syn) == len(real) and dropped["dòng_sinh_bỏ_theo_cấu_hình"] == 50


def test_synthetic_filter_matches_mixed_id_types_and_frozen_eval_events():
    real = pd.DataFrame([{"comment_id": f"r{e}_{i}", "event_id": e, "text": f"t{e} {i}",
                          "label": EDU[i % 4], "is_synthetic": "False"} for e in range(10) for i in range(20)])
    syn = pd.DataFrame([{"comment_id": f"syn_{e}", "event_id": str(e), "text": f"sinh {e}",
                         "label": "ý kiến riêng", "is_synthetic": "True"} for e in range(10)])
    cfg = TrainConfig(domain="education")
    df, *_ = prepare_dataframe(pd.concat([real, syn], ignore_index=True), cfg)
    tr, va, te = split_data(df, cfg)                      # id thật int, id dòng sinh str
    train_events = {str(e) for e in tr[~tr["_synthetic"]]["event_id"]}
    assert {str(e) for e in tr[tr["_synthetic"]]["event_id"]} == train_events
    frozen = set(real[real["event_id"] == 0]["comment_id"].iloc[:5])   # sự kiện 0 nằm ở cả train lẫn test
    tr2, _, te2 = split_data(df, cfg, eval_ids=frozen)
    assert "syn_0" not in set(tr2["comment_id"])


def test_event_context_text_handles_nested_and_broken_json_and_cuts_on_word():
    nested = {"id_content": "e1", "content": json.dumps({"ten_su_kien": "Đề thi khó", "content": "Thí sinh than."})}
    assert event_context_text(nested) == "Đề thi khó. Thí sinh than."
    broken = {"ten_su_kien": "Vụ A", "content": '{ "content": "Ông nói "không biết" rồi đi", "actor_related": []}'}
    assert event_context_text(broken) == 'Vụ A. Ông nói "không biết" rồi đi'
    long = {"ten_su_kien": "Tên", "content": "một hai ba bốn năm sáu"}
    assert event_context_text(long, max_chars=14) == "Tên. một hai"   # không cắt giữa từ
    assert event_context_text({"ten_su_kien": "", "content": ""}) == ""


def test_build_and_load_event_contexts(tmp_path):
    (tmp_path / "education_001.json").write_text(
        json.dumps({"id_content": "education_001", "ten_su_kien": "Vụ 1", "content": "Nội dung."}), encoding="utf-8")
    (tmp_path / "education_002.json").write_text(json.dumps({"ten_su_kien": "", "content": ""}), encoding="utf-8")
    ctx = build_event_contexts(str(tmp_path))
    assert ctx == {"education_001": "Vụ 1. Nội dung."}                 # sự kiện rỗng bị bỏ
    out = tmp_path / "ctx.json"
    out.write_text(json.dumps(ctx, ensure_ascii=False), encoding="utf-8")
    assert load_event_contexts(str(out)) == ctx
    out.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_event_contexts(str(out))


def test_row_contexts_segments_each_event_once_and_counts_missing():
    calls = []
    seg = lambda s: calls.append(s) or s.upper()
    ctx, missing = row_contexts(["a", "b", "a", "x", 1], {"a": "ngữ cảnh a", "b": "b", "1": "số"}, seg)
    assert ctx == ["NGỮ CẢNH A", "B", "NGỮ CẢNH A", "", "SỐ"] and missing == 1
    assert sorted(calls) == ["b", "ngữ cảnh a", "số"]                   # mỗi sự kiện tách từ 1 lần


def test_dataset_uses_sentence_pair_when_contexts_given():
    seen = {}

    def tok(first, second=None, **kw):
        seen.update(first=first, second=second, **kw)
        return {"input_ids": [[1, 2]] * len(first)}

    CommentDataset(["bình luận"], [0], tok, 64)
    assert seen["second"] is None and seen["truncation"] is True
    CommentDataset(["bình luận"], [0], tok, 64, contexts=["sự kiện"])
    assert seen["first"] == ["sự kiện"] and seen["second"] == ["bình luận"]
    assert seen["truncation"] == "longest_first" and seen["max_length"] == 64
