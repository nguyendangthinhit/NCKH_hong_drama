"""Vòng huấn luyện/đánh giá PhoBERT: AMP trên GPU, early stopping theo val F1-macro."""

import os

import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix, f1_score


def class_weight_tensor(labels, n_classes: int, device):
    """Trọng số 'balanced' theo lớp có mặt trong train; lớp vắng mặt nhận trọng số 1 (không ảnh hưởng)."""
    counts = np.bincount(labels, minlength=n_classes).astype(float)
    present = counts > 0
    w = np.ones(n_classes)
    w[present] = counts.sum() / (present.sum() * counts[present])
    return torch.tensor(w, dtype=torch.float, device=device)


def evaluate(model, loader, criterion, device):
    model.eval()
    loss_sum, preds, gold = 0.0, [], []
    with torch.no_grad():
        for b in loader:
            logits = model(b["input_ids"].to(device), b["attention_mask"].to(device))
            y = b["label"].to(device)
            loss_sum += criterion(logits, y).item()
            preds += logits.argmax(1).cpu().tolist()
            gold += y.cpu().tolist()
    f1 = f1_score(gold, preds, average="macro", zero_division=0)
    return loss_sum / max(len(loader), 1), f1, preds, gold


def fit(model, train_loader, val_loader, optimizer, scheduler, criterion, device,
        epochs, patience, save_dir):
    """Trả (best_val_f1, số epoch đã chạy). Luôn lưu best_model.pt ở epoch cải thiện đầu tiên."""
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    best, bad, ran = -1.0, 0, 0
    for epoch in range(epochs):
        model.train()
        tot, correct, n = 0.0, 0, 0
        for b in train_loader:
            ids, mask = b["input_ids"].to(device), b["attention_mask"].to(device)
            y = b["label"].to(device)
            optimizer.zero_grad()
            with torch.autocast(device_type=device.type, enabled=use_amp):
                logits = model(ids, mask)
                loss = criterion(logits.float(), y)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            tot += loss.item()
            correct += (logits.argmax(1) == y).sum().item()
            n += y.size(0)
        val_loss, val_f1, _, _ = evaluate(model, val_loader, criterion, device)
        ran = epoch + 1
        print(f"Epoch {ran}/{epochs} | train loss {tot / max(len(train_loader), 1):.4f} "
              f"acc {correct / max(n, 1):.4f} | val loss {val_loss:.4f} F1 {val_f1:.4f}")
        if val_f1 > best:
            best, bad = val_f1, 0
            torch.save({"model_state_dict": model.state_dict(), "epoch": epoch, "best_f1": float(best)},
                       os.path.join(save_dir, "best_model.pt"))
            print(f"  -> lưu best (val F1={best:.4f})")
        else:
            bad += 1
            if bad >= patience:
                print(f"  early stopping ở epoch {ran}")
                break
    return best, ran


def test_report(model, loader, criterion, device, id2label):
    loss, f1, preds, gold = evaluate(model, loader, criterion, device)
    ids = sorted(id2label)
    names = [id2label[i] for i in ids]
    return {
        "test_f1_macro": float(f1), "test_loss": float(loss), "n_test": len(gold),
        "classification_report": classification_report(
            gold, preds, labels=ids, target_names=names, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(gold, preds, labels=ids).tolist(),
        "label_order": names,
    }
