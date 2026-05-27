"""
Evaluate GNN vs LLM baseline.

Logic:
- Label gốc trong dataset đến từ LLM (Gemini/Llama) — đó là "thầy".
- GNN train trên 70% labels, test trên 15% mà GNN chưa thấy.
- F1 GNN trên test = đo khả năng GNN match LLM ở dữ liệu mới.
- Bonus: benchmark thời gian + cost giữa LLM call vs GNN inference.

Output:
    data/gnn/eval_gnn_vs_llm_{domain}.json
    data/gnn/eval_summary.md  (markdown bảng so sánh chung)
"""

import argparse
import json
import time
from pathlib import Path

OUTPUT_DIR = Path("data/gnn")

# Cost giả định LLM (Gemini Flash 2.5, dữ liệu chính thức 2026):
# Input: $0.075 / 1M tokens, Output: $0.30 / 1M tokens
# Per comment ~150 input + 30 output tokens
LLM_COST_PER_COMMENT_USD = (150 * 0.075 + 30 * 0.30) / 1_000_000
LLM_LATENCY_SEC = 0.5  # avg request

# Reference rate cho ngoại suy
USD_TO_VND = 25_400


def load_metrics(domain: str):
    p = OUTPUT_DIR / f"metrics_{domain}.json"
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def benchmark_inference_time(domain: str):
    """Đo thời gian inference GNN trên toàn bộ node của domain."""
    import pickle
    import numpy as np
    import torch
    import torch.nn.functional as F
    from torch_geometric.data import Data
    from model_graphsage_classifier import make_model

    device = "cuda" if torch.cuda.is_available() else "cpu"

    with open(OUTPUT_DIR / f"graphs_{domain}.pkl", "rb") as fh:
        graphs = pickle.load(fh)
    feats = np.load(OUTPUT_DIR / f"node_features_{domain}.npy")

    src, dst = [], []
    offset = 0
    for g in graphs:
        for s, d in g["edges"]:
            src.append(s + offset)
            dst.append(d + offset)
        offset += g["n_nodes"]
    edge_index = torch.tensor([src + dst, dst + src], dtype=torch.long).to(device)
    x = torch.tensor(feats, dtype=torch.float32).to(device)

    model = make_model(domain, in_dim=x.shape[1]).to(device)
    state = torch.load(OUTPUT_DIR / "checkpoints" / f"gnn_{domain}.pt",
                       map_location=device)
    model.load_state_dict(state)
    model.eval()

    # Warmup
    with torch.no_grad():
        _ = model(x, edge_index)
    if device == "cuda":
        torch.cuda.synchronize()

    t0 = time.time()
    with torch.no_grad():
        for _ in range(5):
            _ = model(x, edge_index)
    if device == "cuda":
        torch.cuda.synchronize()
    elapsed = (time.time() - t0) / 5
    return elapsed, x.shape[0], device


def eval_for_domain(domain: str):
    metrics = load_metrics(domain)
    if metrics is None:
        print(f"[{domain}] No metrics found. Skip.")
        return None

    n_total = metrics["n_train"] + metrics["n_val"] + metrics["n_test"]
    print(f"[{domain}] Total nodes: {n_total}")

    # Benchmark thời gian
    try:
        gnn_time, n_nodes, device = benchmark_inference_time(domain)
        gnn_per_node_ms = (gnn_time / n_nodes) * 1000
    except Exception as e:
        print(f"[{domain}] Benchmark skipped: {e}")
        gnn_time = None
        gnn_per_node_ms = None
        device = "n/a"

    llm_total_sec = n_total * LLM_LATENCY_SEC
    llm_total_usd = n_total * LLM_COST_PER_COMMENT_USD
    llm_total_vnd = llm_total_usd * USD_TO_VND

    out = {
        "domain": domain,
        "n_total_comments": n_total,
        "f1_macro_gnn_on_test": metrics["test_f1_macro"],
        "f1_weighted_gnn_on_test": metrics["test_f1_weighted"],
        "gnn_inference": {
            "device": device,
            "total_sec_for_all_nodes": round(gnn_time, 4) if gnn_time else None,
            "per_node_ms": round(gnn_per_node_ms, 3) if gnn_per_node_ms else None,
        },
        "llm_inference_estimate": {
            "latency_per_call_sec": LLM_LATENCY_SEC,
            "total_sec_for_all_nodes": round(llm_total_sec, 1),
            "cost_usd_per_comment": LLM_COST_PER_COMMENT_USD,
            "total_cost_usd": round(llm_total_usd, 4),
            "total_cost_vnd": round(llm_total_vnd, 0),
        },
        "speedup_gnn_vs_llm": (
            round(llm_total_sec / gnn_time, 0) if gnn_time else None
        ),
        "interpretation": {
            "f1_high_means": "GNN học match LLM tốt — có thể replace ở scale lớn",
            "speedup_means": "GNN nhanh hơn bao lần so với gọi LLM API tuần tự",
            "cost_savings": (
                f"~{round(llm_total_vnd, 0)} VND tiết kiệm cho mỗi {n_total} comments"
            ),
        },
    }

    out_path = OUTPUT_DIR / f"eval_gnn_vs_llm_{domain}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
    print(f"[{domain}] Saved {out_path}")
    return out


def write_summary(results: dict):
    md = ["# Đánh giá GNN vs LLM — Tóm tắt", ""]
    md.append("| Domain | F1 macro GNN | F1 weighted GNN | GNN inference (s) | LLM inference (s) | Speedup |")
    md.append("|---|---|---|---|---|---|")
    for d, r in results.items():
        if r is None:
            continue
        md.append(
            f"| {d} | {r['f1_macro_gnn_on_test']} | {r['f1_weighted_gnn_on_test']} | "
            f"{r['gnn_inference']['total_sec_for_all_nodes']} | "
            f"{r['llm_inference_estimate']['total_sec_for_all_nodes']} | "
            f"{r['speedup_gnn_vs_llm']}x |"
        )
    md.append("")
    md.append(f"**Cost LLM giả định:** Gemini Flash 2.5, ~{LLM_COST_PER_COMMENT_USD*1e6:.3f} USD / 1M comment.")
    md.append(f"**Latency LLM giả định:** {LLM_LATENCY_SEC}s/call (sequential, không batch).")
    md.append("")
    md.append("Diễn giải:")
    md.append("- F1 cao → GNN match LLM tốt → có thể replace LLM ở scale.")
    md.append("- Speedup cao → ROI khi xử lý batch lớn (1M+ comments).")
    out = OUTPUT_DIR / "eval_summary.md"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))
    print(f"Saved {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    results = {}
    for d in domains:
        results[d] = eval_for_domain(d)
    if args.domain == "all":
        write_summary(results)


if __name__ == "__main__":
    main()
