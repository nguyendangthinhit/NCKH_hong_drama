# Testing và nghiệm thu

Document loại 13/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: kiểm tra đã có trong code, bằng chứng đã lưu và cách diễn giải trạng thái hoàn thành. Không bổ sung ngưỡng nghiệm thu sản phẩm hoặc mục tiêu ML từ lộ trình phát triển. Việc viết tài liệu không tự chạy lại pipeline, benchmark, gọi LLM hoặc kiểm thử cloud.

Phương pháp và số liệu đánh giá xem [loại 8](./danh-gia-va-benchmark.md); thuộc tính chất lượng xem [loại 11](./thuoc-tinh-chat-luong.md); môi trường và thứ tự tái lập xem [loại 16](./tai-lap-thi-nghiem.md).

## 1. Các lớp kiểm tra hiện có

| Lớp | Công cụ/bằng chứng trong repo | Phạm vi |
|---|---|---|
| Làm sạch Spark | `preprocessing/spark/verify_preprocessing.py` | So tập ID được giữ với rule Python |
| Từ khóa PMI | `analysis/spark/verify_pmi_keywords.py` | So tập top keyword với baseline |
| Hiệu năng | Hai script và hai JSON tại `benchmark/` | Wall-clock của các workload local |
| Nhãn | JSON có cờ `is_label_correct`, bảng verify CSV/XLSX | Dữ liệu kiểm tra nhãn, không phải test runner |
| PhoBERT/GNN | Validation/test trong trainer, metric/model artifact | Chọn checkpoint và đánh giá theo split |
| Website/dashboard | Script build/lint và code xử lý lỗi | Build/type/lint khác kiểm thử hành vi |
| API và dữ liệu local | Các kiểm tra chỉ đọc được ghi ở loại 9/10 | Hình dạng trả về và tình trạng artifact |

Hai package frontend hiện không khai báo script `test`; website có ESLint, dashboard đặt tên `lint` cho `tsc --noEmit`. Chưa có test runner chung cho toàn pipeline được xác minh. Thư mục `.github/workflows` không có trong working tree khi khảo sát; không suy ra trạng thái mọi CI hoặc dịch vụ ngoài repo từ kết quả này.

Các file debug có tên test trong thư mục tiền xử lý không tự tạo thành bộ unit/integration test có fixture, assertion và báo cáo coverage. Không đồng nhất một script chạy được với test suite có thể lặp lại.

## 2. Điều kiện kiểm tra preprocessing

Verifier đọc hai thư mục input đang cấu hình: Giáo dục `cleaned_data_input`, Showbiz `input_clean_data`. Nó duyệt comment và reply, gọi `is_trash`, rồi gom comment_id được giữ vào một set. Phía Spark collect comment_id từ `data/spark-output/clean/` và cũng tạo set.

| Điều kiện trong code | Kết quả xử lý |
|---|---|
| Có ID chỉ ở baseline hoặc chỉ ở Spark | In ví dụ khác biệt và exit 1 |
| Không có ID khác biệt | In OK; Jaccard tập ID bằng 1 |
| Cả hai tập rỗng | Jaccard được quy ước là 1 |

Thông báo “matches baseline 1:1” chỉ nói về hai tập ID. Verifier không kiểm số lần lặp, text, likes, quan hệ cha/con, thứ tự hoặc toàn bộ schema. Nó không đo độ đúng của rule lọc rác so với con người.

Trạng thái Phase 01 từng ghi đã verify khớp; đây là ghi nhận trước đó, không phải kết quả chạy mới. Đường import cũ trong các script Spark liên quan vẫn là trở ngại khi tái chạy; xem loại 2/16.

## 3. Điều kiện kiểm tra PMI

`verify_pmi_keywords.py` đọc Parquet theo lĩnh vực, ghi JSON tạm cho baseline rồi so kết quả với `benchmark/keyword_analysis_spark.json`. Baseline được gọi với min_count 3, min_pmi 1.0 và top 10.

| Chỉ số | Cách dùng thực tế trong main |
|---|---|
| Jaccard top 10 | Tính giao/hợp keyword và in ra; không gate pass/fail |
| Top 5 match | Kích thước giao hai set top 5 chia 5 |
| Điều kiện pass | Mỗi lĩnh vực có top 5 match ít nhất 0,6 |
| Thiếu file output Spark | Exit 2 trước khi so |
| Top 5 thấp hơn 0,6 | Exit 1 |

Docstring nói Jaccard ít nhất 0,7 và top 5 khớp toàn bộ, nhưng main không thực thi hai điều kiện đó. Top 5 match không kiểm thứ tự xếp hạng; không có assertion cho sai số score, PMI hoặc tần suất. Khi danh sách có ít hơn năm keyword, mẫu số vẫn là 5.

Hàm materialize còn import `data.spark.spark_session_factory`; việc đã có JSON keyword không chứng minh verifier chạy được trên cấu trúc hiện tại hoặc kết quả đã đạt ngưỡng. Đây là điều kiện kiểm tra đang cài, không phải ngưỡng nghiệm thu mới của dự án.

## 4. Kiểm tra nhãn và mô hình

| Nguồn | Điều xác minh được | Giới hạn |
|---|---|---|
| `verify_{domain}_5k.csv/.xlsx` | Có 5.000 dòng mỗi lĩnh vực; verified_label hiện trống | Chưa là gold set đã hoàn tất |
| `data_test_edu.json` | Có 300 mẫu và cờ đúng/sai | Cờ không cung cấp nhãn thay thế cho mẫu sai |
| `data_test_show_da_check.json` | Có 316 mẫu và cờ đúng/sai | Không có đầy đủ annotator, guideline, event ID |
| PhoBERT trainer | Chọn best checkpoint bằng val F1-macro, đánh giá test | Có thể fallback nhãn tự động; chưa xác minh classifier artifact tương ứng |
| GNN trainer | Stratified node split, val F1-macro và metric test | Chia node không chứng minh tách sự kiện hoặc hết rò rỉ |

Tỷ lệ cờ đúng/sai và chênh lệch với báo cáo cũ ở loại 8. Chỉ từ cờ nhị phân không dựng được confusion matrix đầy đủ cho các lớp sentiment/stance. F1 lưu trong artifact không tự trở thành tiêu chí đã được user chấp nhận.

Trainer dùng validation để chọn checkpoint; không có ngưỡng test F1 tối thiểu được dùng làm cổng hoàn thành sản phẩm trong các script đã khảo sát. PhoBERT/GNN vẫn có trạng thái cần làm lại theo user dù đã có code hoặc metric. Chi tiết nhãn và split ở loại 5/6.

## 5. Build, lint và kiểm tra API

| Thành phần | Kiểm tra có thể gọi theo package/code | Ý nghĩa khi có kết quả thực thi |
|---|---|---|
| Website | Script `build` chạy Vite; `lint` chạy ESLint | Build/lint của source hiện tại, không chứng minh thao tác UI hoặc API |
| Dashboard | Script `build` chạy Vite; `lint` chạy TypeScript | Type-check không phải ESLint hoặc test mạng |
| API | Sinh OpenAPI từ app; các handler đọc SQLite | Parameter/schema sinh được khác kiểm thử HTTP |
| SQLite | Truy vấn chỉ đọc, quick_check, foreign_key_check | Kiểm tra artifact tại thời điểm đọc |

Bảng trên mô tả các entry point đã xác minh trong code, không phải tuyên bố đã chạy build/lint trong task tài liệu. Không có cài dependency, mở server hoặc gọi endpoint remote được thực hiện để viết bản nháp này.

Các kiểm tra local được ghi tại loại 9/10 gồm OpenAPI, gọi trực tiếp hàm route với SQLite chỉ đọc, envelope danh sách/chi tiết/categories/stats và lỗi detail thiếu. Chúng không đi qua HTTP routing/middleware, không kiểm tải đồng thời và không xác minh n8n.

Root `/` chỉ trả thông tin dịch vụ; thành công ở route này không chứng minh DB sẵn sàng. API thiếu DB có nhánh 503, detail thiếu có nhánh 404; validation integer là hành vi framework. Phân biệt nhánh đã đọc trong code với tình huống đã được thực thi kiểm tra.

## 6. Kiểm tra tay và tích hợp: phần đã biết/chưa biết

| Luồng trong sản phẩm | Bằng chứng local | Phần chưa có kết quả thực thi đầy đủ |
|---|---|---|
| Website tải danh sách/tìm kiếm/phân trang | Route, helper API và page component | HTTP/UI xuyên suốt trên browser, nhiều loại dữ liệu và lỗi mạng |
| Dashboard hiển thị insight/history | Fetch và fallback trong component | Nguồn remote hiện tại, quyền truy cập, dữ liệu cùng snapshot |
| Chatbot gửi câu hỏi | Client POST message/userId và nhận reply | Wiring n8n, Memory, retrieval/rerank, trả lời có căn cứ |
| ETL dựng web DB | Code DROP/insert/enrichment và artifact SQLite | Dựng lại an toàn, lỗi giữa chừng, ETL đồng thời với API |
| Thu thập Facebook | Export Apify và code crawler chưa hoàn thiện | Độ bao phủ, chạy bù URL thất bại, hành vi cloud hiện tại |

Đây là bảng phân biệt phạm vi bằng chứng, không phải checklist nghiệm thu mới hoặc khẳng định đã kiểm thử hết các tình huống. Chu kỳ reload 30 giây của dashboard không phải SLA về độ mới dữ liệu.

## 7. Trạng thái nghiệm thu hiện tại

Việc user duyệt tài liệu là duyệt nội dung hiện trạng; không đồng nghĩa nghiệm thu vận hành toàn hệ thống, chất lượng ML hay deployment. Trạng thái tài liệu được giữ tại doc-map, trạng thái các nhánh ML tại memory dự án.

Các cổng có thể trỏ trực tiếp về code hiện có là set-ID preprocessing và top5 PMI nêu trên. Các script benchmark chỉ ghi số đo; không có điều kiện speedup tối thiểu để tự pass/fail sản phẩm. Các số đo giả định GNN/LLM không thay một phép đo end-to-end cùng điều kiện.

Chưa có bộ tiêu chí nghiệm thu toàn hệ thống được user chốt và gắn với một snapshot code/dữ liệu/môi trường trong các nguồn đã đọc. Không lấy mục tiêu trong tài liệu ý tưởng hoặc số liệu báo cáo để tự điền tiêu chí này.

**Loại 7 còn thiếu agent n8n; loại 3 còn thiếu schema Supabase.** Vì vậy chưa thể chốt kiểm thử tích hợp toàn chuỗi RAG. Những thông tin này không cản trở mô tả các kiểm tra local đang có.

## 8. Nguồn đối chiếu

- [Verifier preprocessing](../preprocessing/spark/verify_preprocessing.py), [verifier PMI](../analysis/spark/verify_pmi_keywords.py), [Spark preprocessing](../preprocessing/spark/pyspark_preprocessing.py).
- [Benchmark scale](../benchmark/benchmark_pmi.py), [benchmark cùng input](../benchmark/benchmark_apples_to_apples.py).
- [Package website](../serving/web_v2/frontend/package.json), [package dashboard](../serving/dashboard/package.json), [API](../serving/web_v2/backend/app.py).
- [Xuất mẫu kiểm duyệt](../sampling_labeling/export_5k_for_verification.py), [PhoBERT trainer](../ml/phobert/phobert_finetune_colab.py), [GNN trainer](../ml/gnn/train_gnn_node_classification.py).
- [Nhãn và tập dữ liệu](./gan-nhan-va-tap-du-lieu.md), [mô hình](./mo-hinh-ml-va-phan-tich.md), [backend](./backend-serving.md).
