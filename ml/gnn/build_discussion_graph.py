"""
Build discussion graph từ analyzed JSON files.

Mỗi event = 1 graph riêng:
- Node = comment (chỉ giữ comment NON-TRASH có label hợp lệ)
- Edge = reply_to_id (directed: child -> parent)

Output:
- graphs.pkl: list[dict] mỗi dict = 1 graph (node_ids, edges, texts, labels, structural)
- nodes_meta.parquet: bảng metadata phẳng để debug

Usage:
    python build_discussion_graph.py --domain education
    python build_discussion_graph.py --domain showbiz
"""

import argparse
import json
import pickle
from pathlib import Path

import pandas as pd

# Constants -----------------------------------------------------------------

EDU_LABEL_FIELD = "stance"
EDU_VALID_LABELS = {"tích cực", "tiêu cực", "trung lập", "ý kiến riêng"}

SHOW_LABEL_FIELD = "emotion"
SHOW_VALID_LABELS = {"Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập"}

DOMAIN_CONFIG = {
    "education": {
        "input_dir": "data/processed/process_education/analyzed_dataa/full",
        "label_field": EDU_LABEL_FIELD,
        "valid_labels": EDU_VALID_LABELS,
    },
    "showbiz": {
        "input_dir": "data/processed/process_showbiz/analyzed_data/full",
        "label_field": SHOW_LABEL_FIELD,
        "valid_labels": SHOW_VALID_LABELS,
    },
}

OUTPUT_DIR = Path("data/gnn")


# Helpers -------------------------------------------------------------------

def flatten_comments(event_json):
    """Flatten cây comment + reply thành list phẳng với parent pointer."""
    flat = []
    for c in event_json.get("comments", []):
        flat.append({
            "comment_id": c["comment_id"],
            "parent_id": None,
            "text": c.get("text", ""),
            "likes": c.get("likes", 0),
            "is_trash": c.get("is_trash", False),
            "label": c.get("stance") or c.get("emotion"),
            "depth": 0,
        })
        for r in c.get("replies", []):
            flat.append({
                "comment_id": r["comment_id"],
                "parent_id": r.get("reply_to_id"),
                "text": r.get("text", ""),
                "likes": r.get("likes", 0),
                "is_trash": r.get("is_trash", False),
                "label": r.get("stance") or r.get("emotion"),
                "depth": 1,
            })
    return flat


def build_graph_for_event(event_json, valid_labels, label_field):
    """1 event -> 1 graph dict.

    Filter: bỏ comment is_trash=True hoặc label không nằm trong valid_labels.
    Edge: chỉ giữ edge mà cả 2 đầu đều trong tập node hợp lệ.
    Structural: depth, in_degree (số reply nhận được), sibling_count.
    """
    event_id = event_json["id_content"]
    flat = flatten_comments(event_json)

    # Filter node hợp lệ
    valid = [c for c in flat if (not c["is_trash"]) and (c["label"] in valid_labels)]
    valid_ids = {c["comment_id"] for c in valid}

    # ID -> index trong graph
    node_index = {c["comment_id"]: i for i, c in enumerate(valid)}

    # Edge: child -> parent (chỉ khi cả 2 đầu hợp lệ)
    edges = []
    for c in valid:
        if c["parent_id"] and c["parent_id"] in valid_ids:
            edges.append((node_index[c["comment_id"]], node_index[c["parent_id"]]))

    # Structural features
    in_degree = [0] * len(valid)
    for src, dst in edges:
        in_degree[dst] += 1

    # Sibling count: số node có cùng parent
    parent_counts = {}
    for c in valid:
        pid = c["parent_id"] if c["parent_id"] in valid_ids else "ROOT"
        parent_counts[pid] = parent_counts.get(pid, 0) + 1
    sibling_count = []
    for c in valid:
        pid = c["parent_id"] if c["parent_id"] in valid_ids else "ROOT"
        sibling_count.append(parent_counts[pid] - 1)

    return {
        "event_id": event_id,
        "node_ids": [c["comment_id"] for c in valid],
        "texts": [c["text"] for c in valid],
        "labels": [c["label"] for c in valid],
        "edges": edges,  # list[(src, dst)] index-based
        "structural": {
            "depth": [c["depth"] for c in valid],
            "in_degree": in_degree,
            "sibling_count": sibling_count,
        },
        "n_nodes": len(valid),
        "n_edges": len(edges),
    }


def build_all(domain):
    cfg = DOMAIN_CONFIG[domain]
    input_dir = Path(cfg["input_dir"])
    valid_labels = cfg["valid_labels"]
    label_field = cfg["label_field"]

    files = sorted(input_dir.glob("*.json"))
    print(f"[{domain}] Found {len(files)} event files")

    graphs = []
    flat_meta = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            event = json.load(fh)
        g = build_graph_for_event(event, valid_labels, label_field)
        if g["n_nodes"] == 0:
            continue
        graphs.append(g)
        for i, nid in enumerate(g["node_ids"]):
            flat_meta.append({
                "event_id": g["event_id"],
                "comment_id": nid,
                "text": g["texts"][i][:200],
                "label": g["labels"][i],
                "depth": g["structural"]["depth"][i],
                "in_degree": g["structural"]["in_degree"][i],
                "sibling_count": g["structural"]["sibling_count"][i],
            })

    total_nodes = sum(g["n_nodes"] for g in graphs)
    total_edges = sum(g["n_edges"] for g in graphs)
    print(f"[{domain}] Total: {len(graphs)} graphs, {total_nodes} nodes, {total_edges} edges")

    label_dist = pd.DataFrame(flat_meta)["label"].value_counts().to_dict()
    print(f"[{domain}] Label distribution: {label_dist}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pkl = OUTPUT_DIR / f"graphs_{domain}.pkl"
    out_meta = OUTPUT_DIR / f"nodes_meta_{domain}.parquet"
    with open(out_pkl, "wb") as fh:
        pickle.dump(graphs, fh)
    pd.DataFrame(flat_meta).to_parquet(out_meta, index=False)
    print(f"[{domain}] Saved {out_pkl} + {out_meta}")
    return graphs, label_dist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        build_all(d)


if __name__ == "__main__":
    main()
