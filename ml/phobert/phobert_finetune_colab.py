"""
PhoBERT Fine-tuning for Vietnamese Comment Classification
=========================================================
Chạy trên Google Colab (T4/P100 GPU).

Workflow:
1. Upload verified CSV lên Colab (verify_showbiz_5k.csv / verify_education_5k.csv)
2. Chạy notebook này
3. Download checkpoint về local

Usage:
    # Train showbiz model
    !python phobert_finetune_colab.py --domain showbiz --data_path /content/verify_showbiz_5k.csv

    # Train education model
    !python phobert_finetune_colab.py --domain education --data_path /content/verify_education_5k.csv
"""

import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.utils.class_weight import compute_class_weight
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup

# ============================================================
# CONFIG
# ============================================================

SHOWBIZ_LABELS = ["Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập", "is_trash"]
EDUCATION_LABELS = ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng", "is_trash"]

MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 256
SEED = 42


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ============================================================
# DATASET
# ============================================================

class CommentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=MAX_LENGTH):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ============================================================
# MODEL
# ============================================================

class PhoBERTClassifier(nn.Module):
    def __init__(self, num_labels, dropout=0.1):
        super().__init__()
        self.bert = AutoModel.from_pretrained(MODEL_NAME)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(768, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        logits = self.classifier(cls_output)
        return logits


# ============================================================
# DATA LOADING
# ============================================================

def load_and_prepare_data(data_path, domain):
    """Load CSV and prepare labels."""
    df = pd.read_csv(data_path, encoding="utf-8-sig")

    if domain == "showbiz":
        label_col = "llm_emotion"
        valid_labels = SHOWBIZ_LABELS
    else:
        label_col = "llm_stance"
        valid_labels = EDUCATION_LABELS

    # Use verified_label if available, otherwise fall back to llm label
    if "verified_label" in df.columns:
        df["final_label"] = df["verified_label"].where(
            df["verified_label"].notna() & (df["verified_label"] != ""),
            other=df[label_col]
        )
    else:
        df["final_label"] = df[label_col]

    # Handle is_trash: if is_trash == True, override label
    df.loc[df["is_trash"] == True, "final_label"] = "is_trash"

    # Filter to valid labels only
    df = df[df["final_label"].isin(valid_labels)].reset_index(drop=True)

    # Create label mapping
    label2id = {label: idx for idx, label in enumerate(valid_labels)}
    id2label = {idx: label for label, idx in label2id.items()}

    df["label_id"] = df["final_label"].map(label2id)

    # Drop rows with NaN text
    df = df.dropna(subset=["text", "label_id"]).reset_index(drop=True)
    df["label_id"] = df["label_id"].astype(int)

    print(f"\nDataset size: {len(df)}")
    print(f"Label distribution:")
    for label, count in df["final_label"].value_counts().items():
        print(f"  {label}: {count}")

    return df, label2id, id2label


def split_data(df, test_size=0.15, val_size=0.15):
    """Stratified split into train/val/test."""
    train_df, test_df = train_test_split(
        df, test_size=test_size, stratify=df["label_id"], random_state=SEED
    )
    val_ratio = val_size / (1 - test_size)
    train_df, val_df = train_test_split(
        train_df, test_size=val_ratio, stratify=train_df["label_id"], random_state=SEED
    )

    print(f"\nSplit sizes: train={len(train_df)}, val={len(val_df)}, test={len(test_df)}")
    return train_df, val_df, test_df


# ============================================================
# TRAINING
# ============================================================

def train_epoch(model, dataloader, optimizer, scheduler, criterion, device):
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
        loss = criterion(logits, labels)
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()
        preds = torch.argmax(logits, dim=1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

    avg_loss = total_loss / len(dataloader)
    accuracy = correct / total
    return avg_loss, accuracy


def evaluate(model, dataloader, criterion, device):
    model.eval()
    total_loss = 0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            logits = model(input_ids, attention_mask)
            loss = criterion(logits, labels)

            total_loss += loss.item()
            preds = torch.argmax(logits, dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader)
    f1 = f1_score(all_labels, all_preds, average="macro")
    return avg_loss, f1, all_preds, all_labels


def train(
    model, train_loader, val_loader, optimizer, scheduler, criterion,
    device, epochs, patience, save_dir
):
    best_f1 = 0
    patience_counter = 0

    for epoch in range(epochs):
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, criterion, device
        )
        val_loss, val_f1, _, _ = evaluate(model, val_loader, criterion, device)

        print(
            f"Epoch {epoch+1}/{epochs} | "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
            f"Val Loss: {val_loss:.4f}, F1: {val_f1:.4f}"
        )

        if val_f1 > best_f1:
            best_f1 = val_f1
            patience_counter = 0
            save_path = os.path.join(save_dir, "best_model.pt")
            torch.save({
                "model_state_dict": model.state_dict(),
                "epoch": epoch,
                "best_f1": best_f1,
            }, save_path)
            print(f"  -> Saved best model (F1={best_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break

    return best_f1


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["showbiz", "education"], required=True)
    parser.add_argument("--data_path", type=str, required=True)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--patience", type=int, default=3)
    parser.add_argument("--output_dir", type=str, default="/content/phobert_checkpoints")
    args = parser.parse_args()

    set_seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load data
    df, label2id, id2label = load_and_prepare_data(args.data_path, args.domain)
    train_df, val_df, test_df = split_data(df)

    # Tokenizer
    print(f"\nLoading tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    # Datasets
    train_dataset = CommentDataset(
        train_df["text"].tolist(), train_df["label_id"].tolist(), tokenizer
    )
    val_dataset = CommentDataset(
        val_df["text"].tolist(), val_df["label_id"].tolist(), tokenizer
    )
    test_dataset = CommentDataset(
        test_df["text"].tolist(), test_df["label_id"].tolist(), tokenizer
    )

    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size)

    # Class weights for imbalanced data
    class_weights = compute_class_weight(
        "balanced", classes=np.unique(train_df["label_id"]), y=train_df["label_id"].values
    )
    class_weights_tensor = torch.tensor(class_weights, dtype=torch.float).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights_tensor)

    # Model
    num_labels = len(label2id)
    print(f"\nInitializing PhoBERT classifier ({num_labels} labels)")
    model = PhoBERTClassifier(num_labels=num_labels).to(device)

    # Optimizer + Scheduler
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(0.1 * total_steps)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    # Output directory
    save_dir = os.path.join(args.output_dir, args.domain)
    os.makedirs(save_dir, exist_ok=True)

    # Save config
    config = {
        "domain": args.domain,
        "model_name": MODEL_NAME,
        "max_length": MAX_LENGTH,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "patience": args.patience,
        "num_labels": num_labels,
        "label2id": label2id,
        "id2label": id2label,
        "seed": SEED,
    }
    with open(os.path.join(save_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Train
    print(f"\n{'='*60}")
    print(f"Training {args.domain} model")
    print(f"{'='*60}")
    best_f1 = train(
        model, train_loader, val_loader, optimizer, scheduler, criterion,
        device, args.epochs, args.patience, save_dir
    )

    # Load best model and evaluate on test set
    print(f"\n{'='*60}")
    print(f"Evaluating on test set")
    print(f"{'='*60}")
    checkpoint = torch.load(os.path.join(save_dir, "best_model.pt"))
    model.load_state_dict(checkpoint["model_state_dict"])

    test_loss, test_f1, test_preds, test_labels = evaluate(
        model, test_loader, criterion, device
    )

    print(f"\nTest F1 (macro): {test_f1:.4f}")
    print(f"\nClassification Report:")
    target_names = [id2label[i] for i in range(num_labels)]
    print(classification_report(test_labels, test_preds, target_names=target_names))

    print(f"\nConfusion Matrix:")
    cm = confusion_matrix(test_labels, test_preds)
    print(pd.DataFrame(cm, index=target_names, columns=target_names))

    # Save test results
    results = {
        "test_f1_macro": float(test_f1),
        "test_loss": float(test_loss),
        "best_val_f1": float(best_f1),
        "classification_report": classification_report(
            test_labels, test_preds, target_names=target_names, output_dict=True
        ),
        "confusion_matrix": cm.tolist(),
    }
    with open(os.path.join(save_dir, "test_results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nAll outputs saved to: {save_dir}")
    print(f"  - best_model.pt")
    print(f"  - config.json")
    print(f"  - test_results.json")


if __name__ == "__main__":
    main()
