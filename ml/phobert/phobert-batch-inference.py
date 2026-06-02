"""
Batch inference: classify all comments using trained PhoBERT model.

Usage (on Colab after training):
    !python phobert_batch_inference.py \
        --domain showbiz \
        --model_dir /content/phobert_checkpoints/showbiz \
        --input_csv /content/all_showbiz_comments.csv \
        --output_path /content/predictions_showbiz.csv
"""

import argparse
import json
import os

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
import torch.nn as nn


class PhoBERTClassifier(nn.Module):
    def __init__(self, num_labels, model_name="vinai/phobert-base-v2", dropout=0.1):
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(768, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        return self.classifier(cls_output)


class InferenceDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length=256):
        self.texts = texts
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
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", choices=["showbiz", "education"], required=True)
    parser.add_argument("--model_dir", type=str, required=True)
    parser.add_argument("--input_csv", type=str, required=True)
    parser.add_argument("--output_path", type=str, required=True)
    parser.add_argument("--batch_size", type=int, default=32)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # Load config
    config_path = os.path.join(args.model_dir, "config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    id2label = {int(k): v for k, v in config["id2label"].items()}
    num_labels = config["num_labels"]
    model_name = config["model_name"]
    max_length = config["max_length"]

    # Load model
    print("Loading model...")
    model = PhoBERTClassifier(num_labels=num_labels, model_name=model_name)
    checkpoint = torch.load(
        os.path.join(args.model_dir, "best_model.pt"), map_location=device
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Load input data
    print(f"Loading data from {args.input_csv}")
    df = pd.read_csv(args.input_csv, encoding="utf-8-sig")
    texts = df["text"].fillna("").tolist()

    # Inference
    dataset = InferenceDataset(texts, tokenizer, max_length)
    dataloader = DataLoader(dataset, batch_size=args.batch_size)

    all_preds = []
    all_confidences = []

    print(f"Running inference on {len(texts)} comments...")
    with torch.no_grad():
        for i, batch in enumerate(dataloader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)

            logits = model(input_ids, attention_mask)
            probs = torch.softmax(logits, dim=1)
            preds = torch.argmax(probs, dim=1)
            confidences = torch.max(probs, dim=1).values

            all_preds.extend(preds.cpu().numpy())
            all_confidences.extend(confidences.cpu().numpy())

            if (i + 1) % 50 == 0:
                print(f"  Processed {(i+1) * args.batch_size}/{len(texts)}")

    # Map predictions to labels
    df["predicted_label"] = [id2label[p] for p in all_preds]
    df["confidence"] = all_confidences

    # Save
    df.to_csv(args.output_path, index=False, encoding="utf-8-sig")
    print(f"\nSaved predictions to {args.output_path}")

    # Summary
    print(f"\nPrediction distribution:")
    for label, count in df["predicted_label"].value_counts().items():
        print(f"  {label}: {count} ({count/len(df)*100:.1f}%)")


if __name__ == "__main__":
    main()
