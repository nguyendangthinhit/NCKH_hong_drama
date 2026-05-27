# NCKH Hồng Drama — Drama Intelligence System

Hệ thống thu thập, tiền xử lý, phân tích và phục vụ dữ liệu dư luận mạng xã hội (Showbiz + Education) phục vụ NCKH cấp trường.

Pipeline: **Ingestion → Preprocessing → Analysis → ML → Serving**, với song song phần **Sampling/Labeling** cho fine-tune và **Benchmark** so sánh Single-thread vs PySpark.

---

## Cấu trúc thư mục

```
NCKH_hong_drama/
├── ingestion/              # Cào dữ liệu
│   ├── cao_fb/             # Facebook scraper (Playwright + Gemini summarizer)
│   └── n8n/                # Workflow tự động hoá (n8n exports)
│
├── preprocessing/          # Tiền xử lý cây bình luận → comment phẳng + lọc rác
│   ├── single/             # Bản single-thread Python
│   │   ├── tienxuly_vietlaiorder.py
│   │   ├── process_education/  (script + debug)
│   │   └── process_showbiz/
│   └── spark/              # Bản PySpark (Big Data contribution)
│       ├── pyspark_preprocessing.py
│       ├── spark_session_factory.py
│       ├── is_trash_rule.py
│       ├── text_tokenizer.py
│       └── verify_preprocessing.py
│
├── analysis/               # Phân tích (keyword PMI, insight, gộp data)
│   ├── single/
│   │   ├── Analyze keywords.py
│   │   ├── analyze_insights.py
│   │   ├── analyze_comments.py
│   │   ├── analyze_education_async.py
│   │   ├── merge_final_data.py
│   │   └── analyze_keywords_explanation.md
│   └── spark/
│       ├── pyspark_pmi_keywords.py
│       └── verify_pmi_keywords.py
│
├── benchmark/              # So sánh single-thread vs Spark
│   ├── benchmark_apples_to_apples.py
│   ├── benchmark_pmi.py
│   ├── benchmark_*.json    (kết quả)
│   ├── keyword_analysis_spark*.json
│   ├── _apples_tmp/, _baseline_tmp/
│
├── sampling_labeling/      # Lấy mẫu + gán nhãn cho PhoBERT
│   ├── sample_comments.py
│   ├── count_comments.py, count_nontrash_comments.py
│   ├── map_id_content.py
│   ├── aggregate_comments_v2.py
│   ├── data_sampling_process.md
│   └── data_labels/        # Pool LLM-labeled + verified batches
│
├── ml/                     # Mô hình ML
│   └── gnn/                # GraphSAGE thread analysis
│
├── serving/                # Lớp phục vụ
│   ├── api/                # API key store (gitignored)
│   ├── code_web/           # Web UI (Vite)
│   └── dashboard/          # Dashboard React
│
├── data/                   # Toàn bộ dữ liệu
│   ├── raw/                # JSON gốc (data_Sukien, education, showbiz, ...)
│   ├── processed/          # Sau tiền xử lý + analyze
│   │   ├── process_education/    (cleaned_data_input, input_clean_data, analyzed_dataa)
│   │   ├── process_showbiz/      (input_clean_data, analyzed_data)
│   │   └── outputnew/
│   ├── spark-output/clean/ # Parquet từ PySpark
│   ├── analysis-output/    # insights.json, keyword_analysis_v4.*
│   ├── test-sets/          # data_test_edu / show / show_da_check
│   ├── archive/            # luu_tru, workspace, education_fb.json
│   ├── gnn/                # graphs.pkl, tfidf.npz, metrics.json
│   └── gnn-result/         # output từ Colab training
│
├── docs/                   # Tài liệu
│   ├── reports/            # docx báo cáo (gitignored)
│   └── prompts/            # LLM prompts
│
├── plans/                  # Kế hoạch & reports phase (gitignored)
├── _colab/                 # Snapshot upload Colab (gitignored)
├── _tmp/                   # Junk / file tạm (gitignored)
├── creadentials/           # Service account JSON (gitignored)
├── README.md
└── CLAUDE.md
```

---

## Quy trình làm việc

### 1. Ingestion
Cào FB → JSON theo schema event/comment/reply. Xem `ingestion/cao_fb/README.md`.

### 2. Preprocessing
- **Single**: `python preprocessing/single/tienxuly_vietlaiorder.py`
- **Spark**:
  ```
  python preprocessing/spark/pyspark_preprocessing.py \
    --inputs data/processed/process_education/cleaned_data_input \
             data/processed/process_showbiz/input_clean_data \
    --output data/spark-output/clean
  ```

### 3. Analysis
- **Keyword PMI single**: `python "analysis/single/Analyze keywords.py"`
- **Keyword PMI Spark**:
  ```
  python analysis/spark/pyspark_pmi_keywords.py \
    --parquet data/spark-output/clean \
    --output data/analysis-output/keyword_analysis_spark.json
  ```
- **Insight tổng hợp**: `python analysis/single/analyze_insights.py --input data/processed/outputnew --output data/analysis-output/insights.json`

### 4. Benchmark
```
python benchmark/benchmark_pmi.py
python benchmark/benchmark_apples_to_apples.py
```

### 5. Sampling & Labeling
Mục tiêu: 4000 mẫu (2k Showbiz + 2k Education) verified cho PhoBERT.
Xem `sampling_labeling/data_sampling_process.md` + `sampling_labeling/data_labels/labeling-guide.md`.

### 6. ML
- **GNN**: `ml/gnn/` — build graph, extract feature, train GraphSAGE.
- **PhoBERT** (sắp tới): fine-tune showbiz + education classifier.

### 7. Serving
- Dashboard: `cd serving/dashboard && npm run dev`
- Code Web: `cd serving/code_web && npm run dev`

---

## Kế hoạch hiện tại

Plan ML Pipeline (deadline 2026-06-25) — xem `plans/260525-0019-ml-pipeline-improvements/plan.md`:

| Phase | Mô tả | Trạng thái |
|---|---|---|
| 01 | PySpark Preprocessing + PMI | ✅ Done |
| 02 | PhoBERT Fine-tune | ⏳ Pending |
| 03 | GNN Thread Analysis | 🟡 Đã có data + code |
| 04 | Báo cáo + Bảng so sánh | ⏳ Pending |
| 05 | Streaming + Auto Pipeline | future |

---

## Yêu cầu môi trường

- Python 3.11
- Java 11 + Hadoop winutils (cho Spark trên Windows)
- Node 18+ (cho dashboard / code_web)
- GPU 8GB+ VRAM (cho PhoBERT-base)

Cài đặt Spark deps:
```
pip install pyspark==3.5 underthesea pandas pyarrow
```

---

## Bảo mật

- `.env`, `creadentials/`, `serving/api/`, `ingestion/n8n/` đã đưa vào `.gitignore`.
- Plans + docs báo cáo (`*.docx`) cũng gitignored.
- Toàn bộ data (raw/processed/parquet/gnn) **được phép** push (không nhạy cảm).
