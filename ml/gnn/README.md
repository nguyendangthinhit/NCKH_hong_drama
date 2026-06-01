# GNN Pipeline — Hướng dẫn sử dụng

## Tổng quan

Pipeline GNN sử dụng PhoBERT fine-tuned làm feature extractor, kết hợp TF-IDF và structural features để train GraphSAGE classifier trên discussion graph.

```
[Analyzed JSON] → build_discussion_graph.py → graphs_{domain}.pkl
                                                      ↓
[PhoBERT fine-tuned] → extract_phobert_features.py → phobert_{domain}.npy (768d)
                                                      ↓
                    → extract_tfidf_features.py    → tfidf_{domain}.npz (300d)
                                                      ↓
                    → concat_node_features.py      → node_features_{domain}.npy (1071d)
                                                      ↓
                    → train_gnn_node_classification.py → gnn_{domain}.pt
```

---

## Yêu cầu

```bash
pip install torch torch-geometric transformers scikit-learn pandas numpy scipy
```

Hoặc dùng `requirements.txt`:
```bash
pip install -r ml/gnn/requirements.txt
```

---

## Bước 1: Chuẩn bị PhoBERT checkpoint

Sau khi train PhoBERT trên Colab (xem `ml/phobert/phobert-finetune-colab.ipynb`), download checkpoint và đặt vào:

```
ml/phobert/checkpoints/
├── showbiz/
│   ├── best_model.pt      ← file này
│   └── config.json
└── education/
    ├── best_model.pt      ← file này
    └── config.json
```

**Cấu trúc `best_model.pt`:**
```python
{
    "model_state_dict": {
        "bert.embeddings...": tensor,
        "bert.encoder...": tensor,
        "dropout.weight": tensor,      # bỏ qua khi extract features
        "classifier.weight": tensor,   # bỏ qua khi extract features
    },
    "epoch": int,
    "best_f1": float,
}
```

Script `extract_phobert_features.py` tự động filter chỉ lấy `bert.*` weights.

---

## Bước 2: Chạy pipeline (theo thứ tự)

Chạy từ thư mục gốc project (`D:\py\git\NCKH_hong_drama`):

### 2.1 Build discussion graph

```bash
python ml/gnn/build_discussion_graph.py --domain all
```

Output: `data/gnn/graphs_{domain}.pkl`, `data/gnn/nodes_meta_{domain}.parquet`

### 2.2 Extract PhoBERT embeddings (dùng fine-tuned model)

```bash
# Showbiz — dùng fine-tuned checkpoint
python ml/gnn/extract_phobert_features.py \
    --domain showbiz \
    --checkpoint ml/phobert/checkpoints/showbiz/best_model.pt \
    --batch-size 32

# Education — dùng fine-tuned checkpoint
python ml/gnn/extract_phobert_features.py \
    --domain education \
    --checkpoint ml/phobert/checkpoints/education/best_model.pt \
    --batch-size 32
```

**Nếu chưa có fine-tuned model** (dùng pretrained):
```bash
python ml/gnn/extract_phobert_features.py --domain all
```

Output: `data/gnn/phobert_{domain}.npy` (shape [N, 768])

### 2.3 Extract TF-IDF features

```bash
python ml/gnn/extract_tfidf_features.py --domain all
```

Output: `data/gnn/tfidf_{domain}.npz` (shape [N, 300])

### 2.4 Concat features

```bash
python ml/gnn/concat_node_features.py --domain all
```

Output: `data/gnn/node_features_{domain}.npy` (shape [N, 1071])

### 2.5 Train GNN

```bash
python ml/gnn/train_gnn_node_classification.py --domain all --epochs 300 --patience 50
```

Output:
- `data/gnn/checkpoints/gnn_{domain}.pt`
- `data/gnn/metrics_{domain}.json`
- `data/gnn/predictions_{domain}.json`

### 2.6 Evaluate GNN vs LLM

```bash
python ml/gnn/evaluate_gnn_vs_llm.py --domain all
```

Output: `data/gnn/eval_summary.md`

---

## Chạy trên Colab

Nếu chạy trên Colab, dùng notebook `ml/gnn/train_gnn_colab.ipynb` — nó gộp tất cả bước trên.

Upload các file cần thiết:
1. `ml/phobert/checkpoints/{domain}/best_model.pt` (PhoBERT fine-tuned)
2. Thư mục `data/processed/` (analyzed JSON files)

---

## Cấu trúc output (`data/gnn/`)

```
data/gnn/
├── graphs_education.pkl          # Graph structure
├── graphs_showbiz.pkl
├── nodes_meta_education.parquet  # Debug metadata
├── nodes_meta_showbiz.parquet
├── phobert_education.npy         # PhoBERT embeddings [N, 768]
├── phobert_showbiz.npy
├── phobert_node_ids_*.json       # Node ID ordering
├── tfidf_education.npz           # TF-IDF features [N, 300]
├── tfidf_showbiz.npz
├── tfidf_vocab_*.json
├── node_features_education.npy   # Final concat [N, 1071]
├── node_features_showbiz.npy
├── feature_meta_*.json           # Feature slice info
├── checkpoints/
│   ├── gnn_education.pt          # Trained GNN weights
│   └── gnn_showbiz.pt
├── metrics_*.json                # F1, confusion matrix
├── predictions_*.json            # Per-node predictions
└── eval_summary.md               # GNN vs LLM comparison
```

---

## FAQ

**Q: Fine-tuned vs pretrained PhoBERT — khác biệt gì?**

Pretrained PhoBERT cho embeddings generic (chưa biết domain). Fine-tuned PhoBERT đã học phân biệt các emotion/stance cụ thể → embeddings encode thông tin sentiment rõ hơn → GNN có input tốt hơn → F1 cao hơn.

**Q: Tại sao cần TF-IDF nếu đã có PhoBERT?**

PhoBERT capture semantic meaning, TF-IDF capture lexical signals (từ khóa cụ thể). Kết hợp cả hai cho robust hơn, đặc biệt với comments ngắn mà PhoBERT khó encode.

**Q: GNN có cần retrain khi đổi PhoBERT checkpoint?**

Có. Khi extract embeddings mới từ fine-tuned PhoBERT, phải chạy lại từ bước 2.2 trở đi (extract → concat → train GNN).

**Q: Nếu F1 GNN vẫn thấp sau khi dùng fine-tuned PhoBERT?**

- Tăng `--hidden-dim 256`
- Thử `--loss-type focal` cho showbiz (extreme imbalance)
- Tăng epochs: `--epochs 500 --patience 100`
- Kiểm tra data: có thể graph quá sparse (ít edges)
