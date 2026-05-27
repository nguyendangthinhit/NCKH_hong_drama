"""
Train GNN node classifier per domain.

Pipeline:
1. Load graphs.pkl + node_features.npy + labels
2. Build PyG Data object: 1 graph lớn (concat tất cả event), edge index toàn cục
3. Stratified split node-level 70/15/15
4. Train với class weight (showbiz cực kỳ imbalance)
5. Eval F1 macro per epoch, save best model

Output:
    data/gnn/checkpoints/gnn_{domain}.pt
    data/gnn/predictions_{domain}.json
    data/gnn/metrics_{domain}.json

Usage:
    python train_gnn_node_classification.py --domain education --epochs 100
"""

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import classification_report, f1_score, confusion_matrix
from sklearn.model_selection import train_test_split

from model_graphsage_classifier import make_model

OUTPUT_DIR = Path("data/gnn")
CKPT_DIR = OUTPUT_DIR / "checkpoints"

LABEL_MAPS = {
    "education": ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng"],
    "showbiz": ["Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập"],
}


def build_pyg_data(domain: str, device: str):
    from torch_geometric.data import Data

    with open(OUTPUT_DIR / f"graphs_{domain}.pkl", "rb") as fh:
        graphs = pickle.load(fh)
    feats = np.load(OUTPUT_DIR / f"node_features_{domain}.npy")
    label_names = LABEL_MAPS[domain]
    label_to_id = {n: i for i, n in enumerate(label_names)}

    # Concat tất cả graph thành 1 graph lớn, offset edge theo node count
    all_edges_src = []
    all_edges_dst = []
    all_labels = []
    offset = 0
    for g in graphs:
        for nid, lbl in zip(g["node_ids"], g["labels"]):
            all_labels.append(label_to_id[lbl])
        for src, dst in g["edges"]:
            all_edges_src.append(src + offset)
            all_edges_dst.append(dst + offset)
        offset += g["n_nodes"]

    # Bi-directional cho message passing tốt hơn
    edge_index = torch.tensor(
        [all_edges_src + all_edges_dst, all_edges_dst + all_edges_src],
        dtype=torch.long,
    )
    x = torch.tensor(feats, dtype=torch.float32)
    y = torch.tensor(all_labels, dtype=torch.long)
    data = Data(x=x, edge_index=edge_index, y=y)
    print(f"[{domain}] PyG Data: {data}")
    return data.to(device), label_names


def make_split(y: torch.Tensor, seed: int = 42):
    """Stratified 70/15/15 split, trả về 3 mask boolean."""
    n = y.shape[0]
    idx = np.arange(n)
    y_np = y.cpu().numpy()
    train_idx, temp_idx = train_test_split(
        idx, test_size=0.30, stratify=y_np, random_state=seed,
    )
    val_idx, test_idx = train_test_split(
        temp_idx, test_size=0.50, stratify=y_np[temp_idx], random_state=seed,
    )
    train_mask = torch.zeros(n, dtype=torch.bool)
    val_mask = torch.zeros(n, dtype=torch.bool)
    test_mask = torch.zeros(n, dtype=torch.bool)
    train_mask[train_idx] = True
    val_mask[val_idx] = True
    test_mask[test_idx] = True
    return train_mask, val_mask, test_mask


def class_weights(y: torch.Tensor, n_classes: int, device: str, mode: str = "inverse"):
    """Class weights cho cross entropy.

    mode='inverse'    : count.sum() / (n_classes * count) — chuẩn sklearn
    mode='log_inverse': log(count.sum() / count) — êm hơn cho extreme imbalance
    mode='sqrt_inverse': sqrt(count.sum() / count) — trung gian
    """
    counts = torch.bincount(y, minlength=n_classes).float().clamp(min=1)
    total = counts.sum()
    if mode == "log_inverse":
        w = torch.log(total / counts)
    elif mode == "sqrt_inverse":
        w = torch.sqrt(total / (n_classes * counts))
    else:
        w = total / (n_classes * counts)
    return w.to(device)


def focal_loss(logits, target, alpha, gamma: float = 2.0):
    """Focal loss với alpha = class weight.

    Reference: Lin et al. (2017) Focal Loss for Dense Object Detection. ICCV.
    Áp dụng cho extreme imbalance — Showbiz Trung lập 94%.
    """
    log_prob = F.log_softmax(logits, dim=-1)
    prob = log_prob.exp()
    target_log_prob = log_prob.gather(1, target.unsqueeze(1)).squeeze(1)
    target_prob = prob.gather(1, target.unsqueeze(1)).squeeze(1)
    target_alpha = alpha[target]
    loss = -target_alpha * (1 - target_prob) ** gamma * target_log_prob
    return loss.mean()


def train_one(domain: str, epochs: int = 300, lr: float = 1e-3,
              hidden_dim: int = 128, dropout: float = 0.3,
              patience: int = 50, seed: int = 42,
              loss_type: str = "auto", weight_mode: str = "auto",
              focal_gamma: float = 2.0):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[{domain}] Device: {device}")
    torch.manual_seed(seed)
    np.random.seed(seed)

    data, label_names = build_pyg_data(domain, device)
    n_classes = len(label_names)
    train_m, val_m, test_m = make_split(data.y, seed)

    # Auto: showbiz cực kỳ imbalance -> focal + log_inverse weight
    #       education cân hơn -> ce + sqrt_inverse
    if loss_type == "auto":
        loss_type = "focal" if domain == "showbiz" else "ce"
    if weight_mode == "auto":
        weight_mode = "log_inverse" if domain == "showbiz" else "sqrt_inverse"
    print(f"[{domain}] loss={loss_type} weight_mode={weight_mode} epochs={epochs} patience={patience}")

    model = make_model(domain, in_dim=data.x.shape[1],
                       hidden_dim=hidden_dim, dropout=dropout).to(device)
    weights = class_weights(data.y[train_m], n_classes, device, weight_mode)
    print(f"[{domain}] class weights: {weights.cpu().tolist()}")
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=5e-4)

    best_val_f1 = -1.0
    best_state = None
    bad = 0
    t0 = time.time()
    for ep in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        if loss_type == "focal":
            loss = focal_loss(out[train_m], data.y[train_m], weights, focal_gamma)
        else:
            loss = F.cross_entropy(out[train_m], data.y[train_m], weight=weights)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            pred = model(data.x, data.edge_index).argmax(dim=1)
            val_f1 = f1_score(
                data.y[val_m].cpu(), pred[val_m].cpu(),
                average="macro", zero_division=0,
            )
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            bad = 0
        else:
            bad += 1
        if ep % 10 == 0 or ep == 1:
            print(f"[{domain}] ep={ep:3d} loss={loss.item():.4f} val_f1={val_f1:.4f} best={best_val_f1:.4f}")
        if bad >= patience:
            print(f"[{domain}] Early stop at ep={ep}")
            break

    train_time = time.time() - t0
    print(f"[{domain}] Train time: {train_time:.1f}s, best val_f1={best_val_f1:.4f}")

    # Load best, eval test
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        logits = model(data.x, data.edge_index)
        pred = logits.argmax(dim=1)
        prob = F.softmax(logits, dim=1)

    y_true = data.y[test_m].cpu().numpy()
    y_pred = pred[test_m].cpu().numpy()
    test_f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)
    test_f1_weighted = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(n_classes))).tolist()
    cls_report = classification_report(
        y_true, y_pred, labels=list(range(n_classes)),
        target_names=label_names, output_dict=True, zero_division=0,
    )

    metrics = {
        "domain": domain,
        "n_classes": n_classes,
        "label_names": label_names,
        "n_train": int(train_m.sum()),
        "n_val": int(val_m.sum()),
        "n_test": int(test_m.sum()),
        "train_time_sec": round(train_time, 2),
        "best_val_f1_macro": round(best_val_f1, 4),
        "test_f1_macro": round(test_f1_macro, 4),
        "test_f1_weighted": round(test_f1_weighted, 4),
        "confusion_matrix": cm,
        "classification_report": cls_report,
        "hyperparameters": {
            "hidden_dim": hidden_dim,
            "dropout": dropout,
            "lr": lr,
            "epochs_max": epochs,
            "patience": patience,
            "seed": seed,
        },
    }

    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, CKPT_DIR / f"gnn_{domain}.pt")
    with open(OUTPUT_DIR / f"metrics_{domain}.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2)

    # Predictions toàn bộ node (cho evaluate vs LLM)
    preds_all = []
    for i in range(data.y.shape[0]):
        preds_all.append({
            "idx": i,
            "true_label_id": int(data.y[i].item()),
            "true_label_name": label_names[int(data.y[i].item())],
            "pred_label_id": int(pred[i].item()),
            "pred_label_name": label_names[int(pred[i].item())],
            "confidence": float(prob[i, pred[i]].item()),
            "split": "train" if train_m[i] else ("val" if val_m[i] else "test"),
        })
    with open(OUTPUT_DIR / f"predictions_{domain}.json", "w", encoding="utf-8") as fh:
        json.dump(preds_all, fh, ensure_ascii=False)

    print(f"[{domain}] test_f1_macro={test_f1_macro:.4f} test_f1_weighted={test_f1_weighted:.4f}")
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", choices=["education", "showbiz", "all"], default="all")
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden-dim", type=int, default=128)
    ap.add_argument("--dropout", type=float, default=0.3)
    ap.add_argument("--patience", type=int, default=50)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--loss-type", choices=["auto", "ce", "focal"], default="auto")
    ap.add_argument("--weight-mode", choices=["auto", "inverse", "log_inverse", "sqrt_inverse"], default="auto")
    ap.add_argument("--focal-gamma", type=float, default=2.0)
    args = ap.parse_args()
    domains = ["education", "showbiz"] if args.domain == "all" else [args.domain]
    for d in domains:
        train_one(d, args.epochs, args.lr, args.hidden_dim, args.dropout,
                  args.patience, args.seed, args.loss_type, args.weight_mode,
                  args.focal_gamma)


if __name__ == "__main__":
    main()
