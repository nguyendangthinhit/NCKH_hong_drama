# Tái lập thí nghiệm

Document loại 16/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: môi trường, đầu vào, cấu hình, notebook/script và artifact hiện có để hiểu cách tái chạy các phần của dự án. Đây không phải khẳng định đã tái lập thành công mọi thí nghiệm; không chạy lại Spark, training, benchmark, ETL hoặc gọi LLM trong lần viết tài liệu.

Thuật toán ở [loại 6](./mo-hinh-ml-va-phan-tich.md), số đo ở [loại 8](./danh-gia-va-benchmark.md), cổng kiểm tra ở [loại 13](./testing-va-nghiem-thu.md). Tài liệu không lấy cấu hình tương lai làm cấu hình đã dùng.

## 1. Môi trường được mô tả trong repo

| Thành phần | Bằng chứng/cấu hình hiện có | Giới hạn tái lập |
|---|---|---|
| Python backend | README dùng Python 3.11, venv riêng; requirements khóa FastAPI 0.115.6/Uvicorn 0.34.0/httpx 0.27.2/BeautifulSoup 4.12.3 | Manifest này không bao phủ toàn pipeline ML/Spark |
| Website | package.json và package-lock.json; React/Vite, build/lint/dev scripts | Node/npm của lần build cũ chưa được ghi trong artifact benchmark |
| Dashboard | package.json và package-lock.json; React/TypeScript/Vite | Build frontend không xác minh GitHub/n8n/Gemini live |
| Spark local | Factory đặt JDK 17, đường dẫn `.venv-ml/Scripts/python.exe`, Hadoop trên Windows | Đường dẫn mặc định phụ thuộc máy; chưa có manifest môi trường chung |
| GNN local | `ml/gnn/requirements.txt` có numpy/pandas/pyarrow/scipy/scikit-learn với cận dưới | Không phải lockfile toàn bộ môi trường train |
| GNN/PhoBERT Colab | Notebook và các script ML hiện có | Các lệnh cài phụ thuộc không khóa đủ phiên bản/runtime Colab |

Tại gốc repo chưa thấy requirements.txt, pyproject.toml hoặc uv.lock trong lần khảo sát. Không suy ra mọi venv trong máy có cùng bộ package hoặc cùng phiên bản chỉ từ việc thư mục tồn tại.

`ml/gnn/requirements.txt` hiện có thật. Các mục torch, transformers, sentencepiece và torch-geometric ở phần Colab của file này là comment, không được cài chỉ bằng active requirements đó. README và notebook còn mô tả bước bổ sung riêng; không coi hai cách cài là tương đương hoàn toàn.

## 2. Notebook và script: các nguồn hiện có

| File | Nội dung quan sát được |
|---|---|
| `ml/phobert/phobert-finetune-colab.ipynb` | Notebook PhoBERT 28 cell, 17 code cell, kernel Python 3; có cài package và logic seed/train |
| `ml/gnn/train_gnn_colab.ipynb` | Notebook GNN 19 cell, 10 code cell; dùng Drive và các bước feature/train |
| `_colab/ml/gnn/train_gnn_colab.ipynb` | Bản notebook khác vị trí cũng hiện có; cần phân biệt với file trong ml |
| `ml/phobert/phobert_finetune_colab.py` | Entry point fine-tune bằng CLI |
| `ml/gnn/*.py` | Các bước dựng graph, feature, train và đánh giá riêng |

Ba notebook đã khảo sát không có cell lưu outputs. Sự tồn tại của cell hoặc execution_count không tự chứng minh lần chạy, GPU, dataset hoặc kết quả từng được dùng. Chưa có bằng chứng notebook và script Python luôn cùng phiên bản logic; phải đối chiếu file thực sự dùng cho một kết quả.

Không thực thi cell hoặc sao chép output nhạy cảm khi khảo sát. Cấu hình Drive/đường dẫn trong notebook cần được đối chiếu với vị trí dữ liệu của môi trường chạy; chưa có manifest liên kết notebook → commit → input hash → output cho toàn dự án.

## 3. Snapshot dữ liệu và khóa nối

Các nguồn chính được các script đọc gồm JSON bình luận đã phân tích, JSON web, summary, CSV verify và Parquet sạch. Vị trí/schema chi tiết ở [loại 3](./database-va-du-lieu.md) và [loại 5](./gan-nhan-va-tap-du-lieu.md).

| Nhánh | Input mà code hiện dùng | Output cần phân biệt |
|---|---|---|
| GNN Giáo dục | `data/processed/process_education/analyzed_dataa/full/` | Graph/node theo stance hợp lệ, bỏ rác |
| GNN Showbiz | `data/processed/process_showbiz/analyzed_data/full/` | Graph/node theo emotion hợp lệ, bỏ rác; không tự sửa lỗi nhãn Ứng hộ |
| Export verify | Hai cây full trên | CSV/XLSX 5.000 mẫu/lĩnh vực, seed 42; verified_label hiện trống |
| Insight | JSON đã gộp tại outputnew qua tham số input | Summary tổng hợp, không tái đếm full |
| Benchmark apples | `data/raw/education_comments_new.json`, `showbiz_comments_new.json` | Corpus riêng với benchmark scale |

Snapshot full Showbiz, insight và các tập test có chênh lệch đã ghi ở loại 5/8. Không dùng tổng số bình luận hoặc tên file giống nhau để chứng minh hai thí nghiệm dùng cùng dữ liệu. Text/ID trùng và sự thiếu metadata nguồn cũng giới hạn việc đối chiếu mẫu giữa các phiên.

## 4. Seed, split và khả năng lặp lại

| Bước | Cấu hình trong code |
|---|---|
| Export verify 5k | `random.seed(42)`; thứ tự file input được sort |
| PhoBERT | SEED 42; seed random/NumPy/PyTorch; max_length 256 |
| PhoBERT split | Stratified theo label_id, 70/15/15, random_state 42 |
| GNN | Seed CLI mặc định 42; torch.manual_seed và NumPy seed |
| GNN split | Stratified node 70/15/15, cùng seed |
| Lấy mẫu nhỏ cũ | sample_comments.py không đặt seed mặc định |

Seed giúp cố định một phần tính ngẫu nhiên, không tự bảo đảm kết quả bit-for-bit giữa các phiên bản thư viện, GPU hoặc runtime. Split theo dòng/node chưa chứng minh tách sự kiện hoặc nguồn; TF-IDF GNN fit trên toàn bộ node trước split. Xem loại 5/6 để diễn giải kết quả đúng phạm vi.

## 5. Thứ tự tái chạy được code mô tả

Các bảng dưới mô tả entry point và cờ đã đọc từ code, **không phải các lệnh đã được thực thi/kiểm chứng thành công trong task này**. Nhiều script ghi đè output, tải model hoặc gọi mạng; không chạy chỉ để đọc tài liệu.

### 5.1 Spark và PMI

| Thứ tự logic | Entry point / input-cờ chính |
|---|---|
| Flatten/lọc rác | `preprocessing/spark/pyspark_preprocessing.py`: `--inputs`, `--output`; `--threads` mặc định 4 |
| Kiểm tra ID | `preprocessing/spark/verify_preprocessing.py`: input/output hiện viết trong constants |
| PMI Spark | `analysis/spark/pyspark_pmi_keywords.py`: `--parquet`, `--output`; top 10, min-count 3, min-pmi 1.0, threads 4; tùy chọn strip-names |
| Kiểm tra top | `analysis/spark/verify_pmi_keywords.py`: đọc Parquet và JSON keyword tại constants |
| Đo hiệu năng | Hai script `benchmark_pmi.py`, `benchmark_apples_to_apples.py` có input/output riêng |

Một số script Spark vẫn import `data.spark...` dù module đã chuyển sang preprocessing/analysis. Benchmark dùng import tới module mới nhưng module được import vẫn có thể lỗi từ dependency bên trong. Không có bảo đảm chỉ đổi thư mục chạy là khắc phục.

`benchmark_pmi.py` dùng Parquet và dữ liệu lặp x1/x3; `benchmark_apples_to_apples.py` dùng hai JSON ở data/raw. Docstring benchmark còn đường dẫn cũ, constants trong code mới là nguồn thực tế. Dữ liệu Parquet tạm có thể được dùng lại nếu thư mục đã tồn tại; chưa có fingerprint tự kiểm tra cùng nguồn.

### 5.2 PhoBERT

CLI fine-tune yêu cầu `--domain` và `--data_path`; mặc định epochs 10, batch_size 16, lr 2e-5, patience 3, output_dir `/content/phobert_checkpoints`. Mỗi domain lưu best_model.pt/config.json/test_results.json khi luồng tương ứng hoàn tất.

Batch inference yêu cầu `--domain`, `--model_dir`, `--input_csv`, `--output_path`; batch_size mặc định 32. Nó cần checkpoint/config đã chuẩn bị trước, không tự chứng minh checkpoint có ở mọi máy. Tài liệu không cung cấp một đường checkpoint chưa tồn tại làm input có thể chạy ngay.

### 5.3 GraphSAGE

Thứ tự script hiện có: build_discussion_graph → extract_phobert_features và extract_tfidf_features → concat_node_features → train_gnn_node_classification → evaluate_gnn_vs_llm. Các bước đọc/ghi mặc định vào `data/gnn/` và thường cần chạy với working directory là repo root.

`--domain` của các script GNN hỗ trợ education/showbiz/all. Feature PhoBERT có `--checkpoint` tùy chọn; không có thì dùng pretrained. Có embedding PhoBERT không đồng nghĩa classifier đã fine-tune hoặc checkpoint tùy chọn đã được sử dụng.

Concat kiểm tra thứ tự ID PhoBERT/TF-IDF khớp chuỗi canonical `event_id::comment_id` và số hàng khớp trước khi ghép. Thiết kế 768+300+3 chiều còn phụ thuộc vocabulary TF-IDF thực tế; metadata slice không tự điều chỉnh theo mọi độ rộng nhỏ hơn 300.

## 6. Artifact và kết quả cần đối chiếu

| Artifact | Nơi/giới hạn hiện tại |
|---|---|
| Metric/prediction GNN | JSON tại `data/gnn/`; cần đúng split khi đọc dự đoán |
| Feature và checkpoint GNN | Có bản trong cây `data/gnn-result/content/drive/MyDrive/NCKH/NCKH_hong_drama/data/gnn/`, khác path mặc định script |
| PhoBERT classifier | Chưa có bộ checkpoint/config/test_results đã xác minh ở các vị trí local khảo sát; notebook không thay artifact |
| Benchmark PMI | Hai JSON kết quả và JSON keyword tại `benchmark/`; thiếu manifest môi trường đầy đủ |
| Web SQLite | `serving/web_v2/backend/events.db`; ETL DROP/tạo lại bảng, không phải bản ghi lịch sử bất biến |

Metric GNN lưu seed và một số hyperparameter, nhưng thiếu loss_type/weight_mode/focal_gamma đang có trong trainer. Vì vậy không suy ra một file metric cũ được sinh bởi loss auto mặc định hiện tại. Thời gian GNN so LLM còn trộn số đo forward với thời gian/chi phí LLM giả định, xem loại 8.

Các loader pickle/checkpoint là ranh giới tin cậy của file artifact; lần khảo sát này không nạp chúng. Chưa có manifest chữ ký/hash chung để tự chứng minh nguồn gốc và sự phù hợp code/data của mọi artifact.

## 7. Phần không thể tái lập đầy đủ từ repo hiện tại

Luồng LLM phụ thuộc khóa/quota, model và thời điểm gọi; chưa có snapshot request/response/model version đủ để tái tạo toàn bộ nhãn. Thay khóa hoặc gọi lại không bảo đảm nhãn giống lần trước. Dữ liệu đã có không cho biết đầy đủ batch nào từng dùng fallback.

**Agent n8n còn thiếu ở loại 7; schema/config Supabase chưa được bổ sung ở loại 3.** Chưa thể tái dựng wiring, vùng dữ liệu, embedding/reranker hoặc memory chatbot chỉ từ prompt/báo cáo. Các dịch vụ remote và quyền tài khoản không được kiểm tra trong task này.

Chưa có bản manifest duy nhất ghi commit, môi trường, input hash, split cố định, lệnh/cờ thực thi và output hash cho mọi thí nghiệm. Những khoảng trống này là hiện trạng cần làm rõ, không được lấp bằng một kế hoạch triển khai hoặc mục tiêu tương lai.

## 8. Nguồn đối chiếu

- [GNN requirements](../ml/gnn/requirements.txt), [backend requirements](../serving/web_v2/backend/requirements.txt), [website package](../serving/web_v2/frontend/package.json), [dashboard package](../serving/dashboard/package.json).
- [Notebook PhoBERT](../ml/phobert/phobert-finetune-colab.ipynb), [notebook GNN](../ml/gnn/train_gnn_colab.ipynb), [notebook GNN trong _colab](../_colab/ml/gnn/train_gnn_colab.ipynb), [README GNN](../ml/gnn/README.md).
- [Spark factory](../preprocessing/spark/spark_session_factory.py), [Spark preprocessing](../preprocessing/spark/pyspark_preprocessing.py), [PMI Spark](../analysis/spark/pyspark_pmi_keywords.py).
- [PhoBERT CLI](../ml/phobert/phobert_finetune_colab.py), [PhoBERT inference](../ml/phobert/phobert-batch-inference.py), [export verify](../sampling_labeling/export_5k_for_verification.py).
- [Build graph](../ml/gnn/build_discussion_graph.py), [PhoBERT features](../ml/gnn/extract_phobert_features.py), [TF-IDF](../ml/gnn/extract_tfidf_features.py), [concat](../ml/gnn/concat_node_features.py), [GNN trainer](../ml/gnn/train_gnn_node_classification.py).
- [Benchmark scale](../benchmark/benchmark_pmi.py), [benchmark cùng input](../benchmark/benchmark_apples_to_apples.py), [ETL SQLite](../serving/web_v2/backend/build_db.py).
