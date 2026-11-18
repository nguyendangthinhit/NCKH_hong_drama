"""Kiểm tra khung GNN bằng dữ liệu tổng hợp (chỉ kiểm code, không phải kết quả mô hình).

Chạy: py -3.14 -m pytest ml/gnn/tests -q   (từ thư mục gốc repo)
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

GNN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GNN_DIR))
sys.path.insert(0, str(GNN_DIR / "graph_db"))

import concat_node_features as cnf  # noqa: E402
import embedding_api_client as eac  # noqa: E402
import load_graph_to_neo4j as l2n  # noqa: E402
import train_gnn_node_classification as trn  # noqa: E402
from model_graphsage_classifier import MeanSAGEConv, MLPClassifier, make_model  # noqa: E402

LABELS = ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng"]


def fake_graphs(n_events=10, per_event=12, seed=0):
    rng = np.random.RandomState(seed)
    graphs = []
    for e in range(n_events):
        labels = [LABELS[i % 4] for i in range(per_event)]
        graphs.append({
            "event_id": f"education_{e:03d}",
            "node_ids": [f"c{i}" for i in range(per_event)],
            "texts": [f"bình luận {e}-{i}" for i in range(per_event)],
            "labels": labels,
            "edges": [(i, i - 1) for i in range(1, per_event, 3)],
            "structural": {"depth": [0] * per_event, "in_degree": [0] * per_event,
                           "sibling_count": [0] * per_event},
            "n_nodes": per_event,
            "n_edges": len(range(1, per_event, 3)),
        })
    return graphs


def test_mean_sage_conv_matches_manual_mean():
    x = torch.tensor([[1., 0.], [0., 2.], [4., 4.]])
    edge_index = torch.tensor([[0, 1], [2, 2]])  # 0->2, 1->2
    conv = MeanSAGEConv(2, 3)
    out = conv(x, edge_index)
    agg2 = (x[0] + x[1]) / 2
    expect2 = conv.lin_l(agg2) + conv.lin_r(x[2])
    assert torch.allclose(out[2], expect2, atol=1e-6)
    assert torch.allclose(out[0], conv.lin_r(x[0]) + conv.lin_l.bias, atol=1e-6)  # không có hàng xóm


def test_model_in_dim_follows_features_and_state_keys():
    m = make_model("showbiz", in_dim=77)
    out = m(torch.zeros(5, 77), torch.tensor([[0], [1]]))
    assert out.shape == (5, 5)
    assert "conv1.lin_l.weight" in m.state_dict() and "conv1.lin_r.weight" in m.state_dict()


def test_event_split_has_no_event_leakage():
    ids = np.array([f"e{i // 7}" for i in range(140)])
    tr, va, te = trn.make_event_split(ids, seed=1)
    ev = lambda m: set(ids[m.numpy()])
    assert not (ev(tr) & ev(va)) and not (ev(tr) & ev(te)) and not (ev(va) & ev(te))
    assert (tr | va | te).all() and not (tr & va).any()


def test_embedding_cache_avoids_second_api_call(tmp_path, monkeypatch):
    cfg = eac.EmbeddingConfig(dim=4, batch_size=2)
    client = eac.EmbeddingClient(cfg, ["k"], eac.EmbeddingCache(tmp_path / "c.sqlite"))
    calls = []

    def fake_post(texts):
        calls.append(list(texts))
        return np.array([[len(t), 1, 2, 3] for t in texts], dtype=np.float32)

    monkeypatch.setattr(client, "_post_batch", fake_post)
    a = client.embed(["aa", "bbb", "aa"], progress=False)
    assert a.shape == (3, 4) and a[0].tolist() == a[2].tolist()
    assert sum(len(c) for c in calls) == 2  # "aa" trùng chỉ gọi 1 lần
    n = len(calls)
    b = client.embed(["bbb", "aa"], progress=False)
    assert len(calls) == n and b.shape == (2, 4)  # lần 2 hoàn toàn từ cache


def test_build_rows_with_predictions():
    graphs = fake_graphs(2, 4)
    preds = [{"pred_label_name": "tiêu cực", "confidence": 0.9, "split": "test"}] * 8
    ev, cm, rp = l2n.build_rows(graphs, "education", preds)
    assert len(ev) == 2 and len(cm) == 8 and len(rp) == 2 * len(graphs[0]["edges"])
    assert cm[0]["props"]["pred_label"] == "tiêu cực" and cm[0]["uid"] == "education_000::c0"


def test_concat_api_embedding_and_train_end_to_end(tmp_path, monkeypatch):
    graphs = fake_graphs()
    n = sum(g["n_nodes"] for g in graphs)
    ids = [f"{g['event_id']}::{x}" for g in graphs for x in g["node_ids"]]
    for mod in (cnf, trn):
        monkeypatch.setattr(mod, "OUTPUT_DIR", tmp_path)
    (tmp_path / "graphs_education.pkl").write_bytes(pickle.dumps(graphs))
    labels = np.array([LABELS.index(l) for g in graphs for l in g["labels"]])
    rng = np.random.RandomState(0)
    emb = rng.randn(n, 16).astype(np.float32)
    emb[np.arange(n), labels] += 5.0  # tách được theo nhãn để kiểm vòng train có học
    np.save(tmp_path / "apiemb_education.npy", emb)
    (tmp_path / "apiemb_node_ids_education.json").write_text(json.dumps(ids), encoding="utf-8")
    import scipy.sparse as sp
    sp.save_npz(tmp_path / "tfidf_education.npz", sp.csr_matrix(np.zeros((n, 5), np.float32)))
    (tmp_path / "tfidf_node_ids_education.json").write_text(json.dumps(ids), encoding="utf-8")

    cnf.concat_for_domain("education", "api")
    feats = np.load(tmp_path / "node_features_education.npy")
    assert feats.shape == (n, 16 + 5 + 3)
    meta = json.loads((tmp_path / "feature_meta_education.json").read_text(encoding="utf-8"))
    assert meta["text"] == [0, 16] and meta["text_emb"] == "api"

    out = tmp_path / "out"
    for split in ("node", "event"):
        m = trn.train_one("education", epochs=60, patience=60, split=split, out_dir=out)
        assert m["hyperparameters"]["in_dim"] == 24
        assert (out / "checkpoints" / "gnn_education.pt").exists()
    assert m["best_val_f1_macro"] > 0.5  # dữ liệu tổng hợp tách được: vòng train phải học


def test_mlp_ignores_edges_and_factory_selects_kind():
    m = make_model("education", in_dim=10, kind="mlp")
    assert isinstance(m, MLPClassifier)
    x = torch.randn(6, 10)
    m.eval()
    a = m(x, torch.tensor([[0, 1], [1, 2]]))
    b = m(x, torch.empty(2, 0, dtype=torch.long))
    assert a.shape == (6, 4) and torch.allclose(a, b)
    assert not isinstance(make_model("showbiz", 10), MLPClassifier)


def test_train_mlp_end_to_end_writes_model_kind(tmp_path, monkeypatch):
    graphs = fake_graphs()
    n = sum(g["n_nodes"] for g in graphs)
    monkeypatch.setattr(trn, "OUTPUT_DIR", tmp_path)
    (tmp_path / "graphs_education.pkl").write_bytes(pickle.dumps(graphs))
    labels = np.array([LABELS.index(l) for g in graphs for l in g["labels"]])
    feats = np.random.RandomState(0).randn(n, 8).astype(np.float32)
    feats[np.arange(n), labels] += 5.0
    np.save(tmp_path / "node_features_education.npy", feats)
    m = trn.train_one("education", epochs=60, patience=60, split="event",
                      out_dir=tmp_path / "mlp", model_kind="mlp")
    assert m["hyperparameters"]["model"] == "mlp"
