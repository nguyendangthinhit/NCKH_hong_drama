# Đánh giá và benchmark

Document loại 8/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **User đã chốt ngày 2026-10-29.**

Phạm vi: script kiểm tra, cách đo và kết quả đang lưu trong codebase, kết hợp tài liệu đã có. Chỉ đọc code/JSON; không chạy lại Spark, benchmark, huấn luyện hoặc gọi API trong lần rà soát này. Số liệu dưới đây là artifact cũ, không phải phép đo mới trên môi trường hiện tại.

Nguồn nhãn xem [loại 5](./gan-nhan-va-tap-du-lieu.md), mô hình và thuật toán xem [loại 6](./mo-hinh-ml-va-phan-tich.md), phần agent n8n còn thiếu xem [loại 7](./llm-agent-rag.md). Tài liệu này không đặt thêm mục tiêu từ lộ trình phát triển.

## 1. Các lớp đánh giá hiện có

| Đối tượng | Nguồn code / artifact | Ý nghĩa |
|---|---|---|
| Spark preprocessing | `verify_preprocessing.py` | So tập ID giữ lại với rule Python |
| PMI Python/Spark | `verify_pmi_keywords.py` | Đo giao tập từ khóa top, có điều kiện pass trong code |
| Tốc độ PMI | Hai script tại `benchmark/`, hai JSON kết quả | Wall-clock cho các phạm vi input/timing khác nhau |
| Nhãn LLM | Ba JSON tại `data/test-sets/` và báo cáo cũ | Mẫu có nhãn, một số file có cờ kiểm tra đúng/sai |
| PhoBERT / GNN | Trainer, metric JSON, script so GNN/LLM | F1 theo nhãn của tập chia; inference GNN và ngoại suy LLM |
| Chatbot RAG | Báo cáo, prompt, lịch sử local | Minh họa/khẳng định cũ; chưa đủ bằng chứng đo lại agent n8n |

Không gộp các lớp trên thành một tỷ lệ chính xác chung cho toàn hệ thống. Đúng tập ID, trùng top từ khóa, F1 phân loại và câu trả lời chatbot là các tiêu chí khác nhau.

## 2. Kiểm tra tương đương preprocessing

`preprocessing/spark/verify_preprocessing.py` đọc JSON từ hai thư mục input đang cấu hình, lấy bình luận gốc và reply, gọi cùng hàm Python `is_trash` rồi tạo tập comment_id được giữ. Phía Spark đọc `data/spark-output/clean/`, collect cột comment_id và chuyển thành tập.

- Tính giao, hợp, ID chỉ có ở mỗi bên; Jaccard bằng kích thước giao chia kích thước hợp, quy ước hai tập rỗng bằng 1.
- Nếu có ID lệch thì exit 1; không lệch thì in thông báo OK. Đây là điều kiện tương đương tập ID, tương ứng Jaccard 1.
- Không so sánh text, likes, parent, thứ tự, schema đầy đủ hoặc số lần xuất hiện của một ID. Do dùng set, ID lặp bị gộp; thông báo “1:1” của script không chứng minh từng dòng dữ liệu khớp một-một.
- Đây là đối chiếu implementation Spark với rule Python cùng logic, không phải đo độ chính xác lọc rác so với người gán nhãn.

Trạng thái dự án ghi bản Phase 01 trước đây đã kiểm tra khớp, nhưng lần viết document này chưa chạy lại verifier và chưa có báo cáo verifier được tạo mới. Code Spark hiện còn lỗi import đường dẫn cũ nêu ở loại 2; không mặc định chạy lại thành công.

## 3. Kiểm tra top từ khóa PMI

`analysis/spark/verify_pmi_keywords.py` lấy Parquet theo từng lĩnh vực, xuất JSON tạm cho baseline Python, chạy `analyze_file` với min_count 3/min_pmi 1.0 rồi so với `benchmark/keyword_analysis_spark.json`.

| Chỉ số | Cách tính / điều kiện thực tế |
|---|---|
| Jaccard top 10 | Giao/hợp hai tập keyword; được in ra nhưng không dùng để quyết định pass |
| Top 5 match | Kích thước giao hai tập top 5 chia 5; không yêu cầu cùng thứ tự xếp hạng |
| Pass toàn bộ | Mỗi lĩnh vực có top5 match ít nhất 0,6; thấp hơn thì exit 1 |
| Điểm số / tần suất | Không có assertion so giá trị số giữa hai implementation |

Docstring ghi Jaccard ≥0,7 và top 5 khớp 100%, nhưng `main()` thực tế chỉ chặn theo top5 ≥60%. Tài liệu này mô tả điều kiện chạy thật, không dùng docstring làm tiêu chí đã đạt. Khi top có ít hơn năm phần tử, mẫu số trong code vẫn là 5.

Verifier còn import `data.spark.spark_session_factory` ở bước materialize, không khớp cấu trúc hiện tại. File keyword đã lưu và sự tồn tại của script chưa đủ chứng minh verifier hiện chạy pass; chưa có kết quả so sánh mới trong lần rà soát.

## 4. Benchmark PMI trên Parquet và dữ liệu nhân bản

### 4.1 Phạm vi đo của `benchmark_pmi.py`

Script đọc Parquet sạch, collect comment_id/text để tạo JSON cho Python và tạo Parquet scale x1/x3 cho Spark. x3 lặp lại cùng text ba lần, đổi suffix ID cho các bản thêm; đây là tăng tải tổng hợp, không phải ba lần lượng sự kiện độc lập.

Python baseline chạy một lần trên JSON **gộp cả hai lĩnh vực**, tính tokenize/PMI/top keywords. Spark chạy `analyze()` riêng Giáo dục rồi Showbiz, cộng hai thời gian. Vì PMI được tính trên corpus khác cách nhóm, bảng này không phải đối chiếu hai workload hoàn toàn giống nhau; benchmark cùng input ở mục 5 có phạm vi khác.

Tạo SparkSession và materialize input nằm ngoài timer từng phép phân tích. Timer Spark bên ngoài `analyze()` gồm đọc Parquet, tokenize, Spark actions, PMI/frequency xử lý driver và top keywords; không phải thời gian toàn pipeline từ JSON thô. `analyze()` cache token trong một lượt rồi unpersist. Một số dữ liệu và n-gram được collect về driver, nên không diễn giải đây là benchmark mọi bước chạy phân tán.

Script chỉ lấy một phép đo cho mỗi cấu hình, không có vòng lặp thống kê độ lệch hoặc khoảng tin cậy. Chạy lần lượt Python rồi local[1]/local[4]/local[*], không đảo thứ tự; warmup thư viện và cache hệ điều hành có thể ảnh hưởng. Thư mục Parquet tạm đã tồn tại có thể được dùng lại mà không kiểm tra fingerprint nguồn.

### 4.2 Kết quả đang lưu: `benchmark_results.json`

| Scale | Số dòng Spark Giáo dục / Showbiz | Python (giây) | Spark local[1] | Spark local[4] | Spark local[*] |
|---|---|---:|---:|---:|---:|
| x1 | 7.660 / 24.097 | 26,66 | 48,89 (0,55x) | 54,06 (0,49x) | 53,10 (0,50x) |
| x3 | 22.980 / 72.291 | 82,19 | 105,55 (0,78x) | 79,50 (1,03x) | 137,51 (0,60x) |

Hệ số trong ngoặc là `thời gian Python / thời gian Spark`; nhỏ hơn 1 nghĩa Spark chậm hơn trong phép đo đó. Chỉ local[4] ở x3 hơi vượt Python trong artifact này; khác biệt nhỏ và không có độ biến thiên nên chưa đủ kết luận lợi thế ổn định. `local[*]` là dùng core khả dụng theo Spark, không xác định số core cố định từ JSON.

## 5. Benchmark cùng input Python và Spark

`benchmark_apples_to_apples.py` dùng `data/raw/education_comments_new.json` và `data/raw/showbiz_comments_new.json`. Python gọi baseline riêng mỗi lĩnh vực; Spark nạp cùng JSON, suy id_content từ comment_id, ghi Parquet tạm rồi gọi `analyze(..., domain_filter=None)` trên từng phần.

Việc đọc JSON, tạo/repartition DataFrame và ghi Parquet cho Spark được thực hiện **trước timer**; Python đọc JSON bên trong hàm được đo. Timer cũng không gồm khởi động/dừng Spark. Vì vậy “cùng input” mô tả nguồn dữ liệu, không chứng minh tổng chi phí đọc/chuyển đổi đầu vào được tính đối xứng.

| Nguồn `benchmark_apples.json` | Giáo dục (giây) | Showbiz (giây) | Tổng (giây) | Python/Spark |
|---|---:|---:|---:|---:|
| Python single | 4,99 | 11,70 | 16,69 | — |
| Spark local[1] | 18,53 | 24,24 | 42,77 | 0,39x |
| Spark local[2] | 18,90 | 19,77 | 38,67 | 0,43x |
| Spark local[4] | 26,69 | 25,27 | 51,96 | 0,32x |
| Spark local[*] | 60,35 | 62,94 | 123,29 | 0,14x |

Artifact ghi n_docs là 4.285 Giáo dục và 13.960 Showbiz. Đây là corpus khác bảng scale ở mục 4; không trộn hai bảng thành một đường scaling. Ở tất cả cấu hình trong bảng cùng input này, Python nhanh hơn Spark. Không ngoại suy kết quả local sang cụm nhiều máy, GPU hay dữ liệu lớn hơn chưa đo.

Hai JSON benchmark không lưu đầy đủ CPU/RAM/OS, version thư viện, số core local[*], timestamp phép đo, commit và hash dữ liệu. Không khẳng định chúng được sinh bởi đúng phiên bản script hiện tại chỉ từ tên file. Thời gian là wall-clock giây, không kèm memory peak hoặc chi phí hạ tầng.

## 6. Mẫu kiểm tra nhãn LLM

Ba file `data/test-sets/` gồm Giáo dục 300 dòng, Showbiz chưa check 316 dòng, Showbiz có cờ kiểm tra 316 dòng. File Giáo dục và Showbiz đã check có `is_label_correct`, nhưng không có đầy đủ annotator, phiên bản guideline hay nhãn thay thế cho các mẫu sai.

| File có cờ kiểm tra | Giá trị 1 / 0 | Tỷ lệ cờ 1 trên số dòng |
|---|---:|---:|
| `data_test_edu.json` | 209 / 91 | 69,67% |
| `data_test_show_da_check.json` | 253 / 63 | 80,06% |

Đây là tỷ lệ từ cờ đã lưu, không phải F1-macro hoặc một lần gọi lại LLM để đánh giá. Không có nhãn tham chiếu đầy đủ để dựng confusion matrix chỉ từ đúng/sai. Mỗi file có một dòng dư do text lặp chính xác; các file thiếu event_id/comment_id để chứng minh độc lập với dữ liệu train. Hai tập verify 5k chưa có verified_label; xem loại 5.

Báo cáo cũ mô tả 616 mẫu và human annotation. Bảng kết quả Giáo dục trong báo cáo ghi 226 đúng/74 sai (75,3%), khác file local hiện có 209/91 (69,67%); Showbiz ghi 253/316 (80,1%), khớp tỷ lệ file sau làm tròn. Chưa xác định nguyên nhân khác snapshot hay cách chấm. Báo cáo còn có ghi chú chờ điền F1 dạng X%; không coi đó là một giá trị đã đo. Số mẫu khớp 300+316 không đủ xác nhận provenance từng dòng; không chuyển tỷ lệ cờ thành F1 hoặc độ chính xác toàn bộ LLM hiện tại.

## 7. Đánh giá PhoBERT và GNN

PhoBERT trainer chọn checkpoint theo val F1-macro rồi tính test loss/F1-macro, classification report và confusion matrix, dự kiến xuất `test_results.json`. Trong các artifact local đã khảo sát chưa tìm thấy bộ kết quả classifier PhoBERT tương ứng; không tự điền một kết quả từ kế hoạch hoặc nhầm embedding GNN thành classifier đã được đánh giá.

GNN trainer chia node train/val/test 70/15/15, seed 42; chọn checkpoint theo val F1-macro. File `metrics_{domain}.json` lưu F1 test, classification report, confusion matrix và cấu hình cơ bản.

| Metric GNN đang lưu | Train / val / test | Test F1-macro | Test F1-weighted |
|---|---|---:|---:|
| Giáo dục | 3.759 / 805 / 806 | 0,5239 | 0,6267 |
| Showbiz | 14.280 / 3.060 / 3.060 | 0,2170 | 0,9161 |

Đánh giá này đo khớp nhãn artifact, phần lớn nhãn tự động; chưa chứng minh một gold set độc lập. Weighted F1 Showbiz cao đi cùng macro F1 thấp, không coi hai chỉ số tương đương. Chia node giữ toàn graph/feature khi message passing, TF-IDF fit trước split và nguồn có ID lặp; chưa chứng minh khả năng tổng quát sang sự kiện mới hoặc loại hết rò rỉ dữ liệu. Chi tiết mô hình tại loại 6.

Theo trạng thái user đã lưu, PhoBERT/GNN vẫn cần làm lại; đọc được metric không đổi trạng thái hoàn thành đó. Saved hyperparameter GNN thiếu các lựa chọn loss/weight hiện có trong trainer, nên chưa tái lập đầy đủ chỉ từ metric JSON.

## 8. Thời gian GNN và ngoại suy chi phí LLM

`evaluate_gnn_vs_llm.py` đọc metric và có hàm đo GNN: nạp graph/feature/checkpoint, tạo tensor, warmup một forward pass, sau đó lấy trung bình năm forward pass trên toàn node. Trên CUDA có synchronize. Timer không tính dựng đặc trưng PhoBERT/TF-IDF, dựng graph, nạp model hoặc pipeline thu thập/gán nhãn.

| Artifact đánh giá | Node | GNN CPU, giây/toàn graph | LLM giả định, giây | Hệ số được lưu |
|---|---:|---:|---:|---:|
| Giáo dục | 5.370 | 0,0868 | 2.685 | 30.951x |
| Showbiz | 20.400 | 0,5245 | 10.200 | 19.447x |

Phía LLM không chạy benchmark API: lấy 0,5 giây/bình luận nhân số node. Chi phí lấy hằng số token/giá trong code, tương đương 0,00002025 USD/bình luận, và quy đổi bằng tỷ giá cố định. Đây là giả định lịch sử của script, không phải bảng giá/tỷ giá hiện tại, hóa đơn hay mức tiết kiệm đã đo thực tế.

Vì mẫu số là forward GNN đã có feature còn tử số là ngoại suy API tuần tự, hệ số trên không phải so end-to-end đồng điều kiện. Inference chạy trên mọi node, còn F1 chỉ trên test; không nhầm thời gian toàn graph với thời gian chỉ tập test. Nếu đo GNN lỗi, script vẫn xuất ước tính LLM và để thời gian GNN null.

## 9. Chatbot RAG và phạm vi chưa đánh giá

Báo cáo cũ có hội thoại minh họa, các khẳng định về fallback web/chống ảo giác và bảng đánh giá trên 30 log n8n: Hit Rate 29/30 (ghi 97%), Faithfulness 9,34/10, Relevance 9,20/10. Báo cáo gọi phương pháp chấm là LLM-as-a-Judge; chưa có model judge/rubric hoặc log điểm đầy đủ để kiểm chứng. Các chỉ số MRR/Recall@K được liệt kê trong bảng phương pháp nhưng chưa có giá trị tương ứng được xác minh. Đây là kết quả được báo cáo mô tả, chưa được tái kiểm chứng từ workflow hoặc log chấm local.

File history local chứa 34 lượt nhưng không có retrieved contexts, điểm judge hay danh sách chunk đúng mong đợi để tái tính các chỉ số trên; QA local rỗng. Chưa xác định 30 log báo cáo là tập con nào, rubric/nguồn chấm điểm hoặc phiên workflow/model. Không coi 34 lượt history là 30 mẫu đánh giá đã khớp. Chưa có artifact đủ để xác nhận lại retrieval/rerank quality, độ đúng câu trả lời, latency p50/p95, tỷ lệ lỗi hoặc tải đồng thời hiện tại.

User xác nhận phần agent nằm trong n8n, luồng không còn ở repo và sẽ giải thích sau. **Loại 7 còn thiếu n8n agent**, nên tài liệu này chưa coi nhánh đó đã được đánh giá end-to-end. Prompt chống bịa và ví dụ hội thoại không thay bằng chứng đo lường.

## 10. Giới hạn và thông tin còn mở

1. Cần xác định phiên code, snapshot input và môi trường đã sinh từng artifact benchmark/metric; chưa có manifest chung.
2. Chưa có log verifier mới hoặc bằng chứng chạy thành công trên cấu trúc đường dẫn hiện tại. Mức pass thực tế của PMI khác docstring, cần giữ rõ khi đọc kết quả cũ.
3. Chưa có phép đo lặp và độ biến thiên cho PMI, benchmark cụm thật hoặc số đo toàn pipeline cùng điều kiện.
4. Chưa có gold dataset/chia tập độc lập được xác nhận cho mọi mô hình; tỷ lệ đúng/sai từ cờ test không đồng nhất với F1.
5. Workflow agent n8n và thông tin đánh giá chatbot chờ user bổ sung; không suy diễn từ ý tưởng phát triển.

## 11. Nguồn đối chiếu

- [Benchmark scale PMI](../benchmark/benchmark_pmi.py), [kết quả scale](../benchmark/benchmark_results.json), [benchmark cùng input](../benchmark/benchmark_apples_to_apples.py), [kết quả cùng input](../benchmark/benchmark_apples.json).
- [Verify preprocessing](../preprocessing/spark/verify_preprocessing.py), [verify PMI](../analysis/spark/verify_pmi_keywords.py), [PMI Spark](../analysis/spark/pyspark_pmi_keywords.py), [PMI Python](../analysis/single/Analyze%20keywords.py).
- [Mẫu Giáo dục](../data/test-sets/data_test_edu.json), [mẫu Showbiz](../data/test-sets/data_test_show.json), [Showbiz có cờ check](../data/test-sets/data_test_show_da_check.json).
- [PhoBERT trainer](../ml/phobert/phobert_finetune_colab.py), [GNN trainer](../ml/gnn/train_gnn_node_classification.py), [so sánh GNN/LLM](../ml/gnn/evaluate_gnn_vs_llm.py).
- [Metric Giáo dục](../data/gnn/metrics_education.json), [metric Showbiz](../data/gnn/metrics_showbiz.json), [tóm tắt GNN cũ](../data/gnn/eval_summary.md), [báo cáo cũ dạng trích](./reports/_report_extract.txt).
- [Artifact so sánh GNN/LLM Giáo dục](../data/gnn/eval_gnn_vs_llm_education.json), [Showbiz](../data/gnn/eval_gnn_vs_llm_showbiz.json).
