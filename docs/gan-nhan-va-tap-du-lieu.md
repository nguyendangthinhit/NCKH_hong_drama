# Gán nhãn và tập dữ liệu

Document loại 5/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **User đã kiểm tra xong ngày 2026-10-29.**

Phạm vi: cách gán nhãn, lấy mẫu và chuẩn bị tập dữ liệu đang có trong code, file dữ liệu local và tài liệu cũ. Không dùng lộ trình cải tiến làm mô tả cài đặt. Chưa gọi lại LLM, xuất lại dữ liệu hoặc huấn luyện mô hình trong lần rà soát này.

Thu thập xem [loại 4](./thu-thap-du-lieu.md); vị trí các kho xem [loại 3](./database-va-du-lieu.md); luồng xử lý tổng thể xem [loại 2](./data-pipeline.md).

## 1. Các tầng nhãn hiện có

| Tầng | Nguồn nhãn | Ý nghĩa |
|---|---|---|
| Bình luận đã phân tích | Rule lọc rác và Groq trong `analysis/single/` | Nhãn tự động, chưa mặc định là nhãn người kiểm chứng |
| Tập 5.000 mẫu/lĩnh vực | `export_5k_for_verification.py` | Lấy mẫu nhãn tự động để người kiểm tra; có cột `verified_label` |
| Tập thử nhỏ | `data/test-sets/*.json` | File mẫu có nhãn và một số file có `is_label_correct`; không có đầy đủ dấu vết người gán trong schema |
| Đầu vào PhoBERT | CSV được truyền vào script fine-tune | Có thể trộn nhãn kiểm chứng và nhãn tự động vì script cho fallback |
| Đầu vào GNN | Bình luận không rác có stance/emotion hợp lệ | Nhãn từ dữ liệu phân tích, không tự trở thành gold label |

Trong tài liệu này, “đã xuất để kiểm tra” khác với “đã được con người kiểm chứng”. Chỉ có tên file `verify_*` không đủ để kết luận đã có gold dataset hoàn chỉnh.

## 2. Bộ nhãn theo lĩnh vực

### 2.1 Showbiz

| Giá trị `emotion` | Cách hiểu trong prompt hiện tại |
|---|---|
| `Phẫn nộ` | Tức giận, bức xúc |
| `Cà khịa` | Mỉa mai, châm biếm |
| `Đồng cảm` | Thương, chia sẻ |
| `Ủng hộ` | Đồng ý, khen, bênh vực |
| `Trung lập` | Thông tin, hỏi hoặc không rõ cảm xúc |

`is_trash` là cờ riêng; không phải một trong năm cảm xúc. Bình luận rác do rule gán có `emotion`, `toxic`, `toxic_type` bằng null. Với bình luận không rác, `toxic` là cờ độc hại riêng; `toxic_type` trong prompt gồm `chửi bới`, `công kích cá nhân`, `công kích người thân`.

Một bình luận có cảm xúc vẫn có thể độc hại. Không suy ra toxic chỉ từ emotion và không gộp toxic thành nhãn cảm xúc thứ sáu.

### 2.2 Giáo dục

| Giá trị `stance` cuối | Cách hiểu từ prompt và hướng dẫn nhãn |
|---|---|
| `tích cực` | Đồng tình, ủng hộ, khen |
| `tiêu cực` | Phản đối, chỉ trích, lo ngại |
| `trung lập` | Không có quan điểm rõ ràng, hỏi han, chờ xem hoặc thờ ơ |
| `ý kiến riêng` | Đề xuất, phân tích hai chiều, quan điểm có điều kiện |

Rule đánh dấu rác bằng `is_trash: true`, `stance: rác`. Prompt bước 1 dùng thêm `cần xem xét` làm nhãn trung gian; bước 2 phân lại thành `trung lập` hoặc `ý kiến riêng`, phần còn sót được đổi sang `trung lập`. `cần xem xét` không phải lớp đầu ra chính thức của tập fine-tune.

### 2.3 Khác biệt giữa các biểu diễn

- Script fine-tune dùng năm/sáu lớp bằng cách thêm chuỗi `is_trash` vào bốn stance/năm emotion.
- CSV giữ `is_trash` thành cột bool; nhãn rác trong cột LLM có thể là `rác` hoặc rỗng tùy lĩnh vực.
- `sample_comments.py` đổi emotion null/rỗng thành chuỗi `null`; chuỗi này không chứng minh mọi mẫu thuộc nhóm đều đã được xác minh là rác.
- Export 5k chuẩn hóa lỗi chính tả `Ứng hộ` thành `Ủng hộ`. Các mã không dấu như `phan_no`, `tich_cuc` trong hướng dẫn cũ không phải bộ giá trị tiếng Việt mà script fine-tune hiện kiểm tra.

## 3. Gán nhãn tự động trong code

Hai script hiện dùng Groq `llama-3.3-70b-versatile`, batch 10 bình luận. Chúng làm phẳng bình luận gốc và reply; reply có thể kèm text cha trong prompt. Đây là code đang có, không phải bằng chứng mọi artifact local được sinh bằng đúng phiên bản script này.

1. `is_trash_rule()` loại trước những trường hợp như quá ngắn, chỉ emoji/ký tự lặp, URL, tag tên, spam hoặc chuỗi giống tên người. Mẫu bị rule loại không đi qua LLM.
2. Showbiz gửi phần còn lại để xét emotion và toxic; dùng semaphore mặc định 3.
3. Giáo dục gán stance bước 1 rồi xét lại nhóm `cần xem xét`; cấu hình concurrency tối đa 5, nhưng vòng batch bước 1 thực tế gọi tuần tự, bước 2 dùng `asyncio.gather`.
4. Parse JSON và gắn kết quả vào `comment_id`; bước 1 có kiểm tra ID thuộc batch để tránh nhận ID LLM sinh thêm.
5. Dựng lại cây comments/replies và xuất `full/`, `summary/`, kèm log phiên chạy `run_log.jsonl`.

Các fallback có ảnh hưởng trực tiếp đến chất lượng nhãn:

- Showbiz lỗi API/parse hoặc thiếu ID: gán không rác, `Trung lập`, không toxic.
- Giáo dục thiếu kết quả bước 1: gán không rác, `trung lập`; bước 2 thiếu kết quả cũng về `trung lập`.
- Bản ghi cuối chưa có trường riêng chỉ rõ nhãn nào đến từ fallback. Vì thế `Trung lập`/`trung lập` không hoàn toàn tương đương kết luận phân tích thành công.
- Rule lọc rác chạy trước prompt, có thể loại cả câu ngắn có ý nghĩa hoặc câu chứa URL; định nghĩa trong hướng dẫn con người và rule không luôn trùng nhau.

## 4. Dữ liệu phân tích dùng làm nguồn

Nguồn mà script export 5k đọc:

| Lĩnh vực | Thư mục | Số file | Bình luận gốc + reply | Không rác | Rác |
|---|---|---:|---:|---:|---:|
| Giáo dục | `data/processed/process_education/analyzed_dataa/full/` | 20 | 7.815 | 5.370 | 2.445 |
| Showbiz | `data/processed/process_showbiz/analyzed_data/full/` | 29 | 25.564 | 20.409 | 5.155 |

Số liệu đọc từ cây dữ liệu local ngày 2026-10-29. Không lấy số liệu insight thay cho số đếm nguồn export: `insights.json` hiện ghi Showbiz có 30 sự kiện phân tích và 24.252 bình luận sạch, khác cây `full/` đang có. Chưa xác định nguyên nhân/chênh lệch phiên bản dữ liệu.

`full/` giữ cây bình luận với metadata, nhãn và thông tin thread. `summary/` là số liệu tổng hợp theo sự kiện, không phải tập từng dòng dùng để người kiểm tra nhãn.

## 5. Xuất tập kiểm tra 5.000 mẫu

`sampling_labeling/export_5k_for_verification.py` đọc các file JSON đã sắp tên, lấy cả bình luận gốc lẫn reply và seed 42. Không xuất context cha/bài đăng vào bảng kiểm tra.

### 5.1 Cách lấy mẫu

- Showbiz: lấy toàn bộ lớp khác `Trung lập` hợp lệ và không rác; lấy tối đa 2.000 trung lập; dùng rác bù phần còn lại; shuffle rồi cắt tối đa 5.000.
- Giáo dục: lấy toàn bộ `ý kiến riêng` và `tích cực`; lấy tối đa 800 rác; chia phần còn lại cho `tiêu cực` và `trung lập`; shuffle rồi cắt tối đa 5.000.
- Đây không phải lấy mẫu giữ nguyên tỷ lệ tự nhiên hoặc chia đều tất cả lớp. Nếu nguồn thay đổi khiến số lớp ưu tiên vượt quota, phép lấy mẫu phần còn lại chưa có xử lý tổng quát cho số âm; không mặc định script dùng được với mọi snapshot dữ liệu.

### 5.2 File và schema

Mỗi lĩnh vực xuất cặp `verify_{domain}_5k.xlsx` và `.csv` tại `sampling_labeling/data_labels/`; CSV dùng UTF-8 BOM.

| Cột | Nội dung |
|---|---|
| `comment_id`, `event_id` | Mã bình luận và sự kiện từ nguồn |
| `text` | Nội dung bình luận |
| `llm_emotion` / `llm_stance` | Nhãn đang có; tên cột không phân biệt nhãn rule/fallback/LLM |
| `is_trash` | Cờ rác từ dữ liệu phân tích |
| `verified_label` | Khởi tạo rỗng để người điền |
| `notes` | Khởi tạo rỗng để ghi chú |

### 5.3 CSV đang có

| CSV | Dòng | Sự kiện | Dòng có `verified_label` | Phân bố |
|---|---:|---:|---:|---|
| `verify_education_5k.csv` | 5.000 | 20 | 0 | trung lập 1.601; tiêu cực 1.600; rác 800; tích cực 644; ý kiến riêng 355 |
| `verify_showbiz_5k.csv` | 5.000 | 29 | 0 | Trung lập 2.000; Cà khịa 804; Phẫn nộ 291; Đồng cảm 57; Ủng hộ 42; rác 1.806 |

Các mẫu rác Showbiz có nhãn emotion rỗng trong CSV. Hai file XLSX đi kèm cũng có 5.000 dòng dữ liệu và không có ô `verified_label` được điền khi kiểm tra read-only. Chưa coi đây là gold set đã xác nhận; trạng thái kiểm duyệt có thể khác ở file ngoài repo, hiện chưa có thông tin.

Theo khóa ghép `(event_id, comment_id)`, số dòng dư do lặp khóa là 478 ở CSV Giáo dục và 116 ở CSV Showbiz. Text lặp chính xác có số dòng dư tương ứng 67 và 84. Đây là thống kê trùng khóa/nội dung, chưa kết luận nguyên nhân hoặc cách loại mẫu. Không mặc định 5.000 dòng tương ứng 5.000 bình luận độc nhất.

## 6. Tập thử nhỏ và script lấy mẫu cũ

| File trong `data/test-sets/` | Dòng | Trường |
|---|---:|---|
| `data_test_edu.json` | 300 | `text`, `emotion`, `is_label_correct` |
| `data_test_show.json` | 316 | `text`, `emotion` |
| `data_test_show_da_check.json` | 316 | `text`, `emotion`, `is_label_correct` |

Ở tập Giáo dục, trường tên `emotion` chứa các nhãn stance viết thường; không được hiểu là dùng bộ năm emotion Showbiz. `is_label_correct` có giá trị 1/0: Giáo dục 209/91 dòng, Showbiz đã check 253/63 dòng. Đây là giá trị cờ lưu trong file, không đủ dấu vết để xác minh quy trình kiểm tra. Mỗi file JSON có một dòng dư do text lặp chính xác. Các file không giữ `comment_id`/`event_id`, nên khó truy về sự kiện hoặc loại trùng với tập train chỉ bằng mã.

`sample_comments.py` hiện chỉ chạy Showbiz; phần Education bị comment. Quota trong code: `null` 20, `Ủng hộ` 20, `Đồng cảm` 40, `Phẫn nộ` 80, `Cà khịa` 80, `Trung lập` 80, tổng mục tiêu 320. Nếu thiếu lớp thì lấy hết số có sẵn; seed mặc định không được đặt. Đầu ra chỉ còn `text`, `emotion`.

Đường dẫn mặc định script là `data/showbiz_comments_new.json` → `data/data_test_show.json`, khác vị trí file mẫu hiện ở `data/test-sets/`. File 316 dòng hiện có ít hơn quota ở lớp Đồng cảm; chưa đủ dấu vết để khẳng định phiên chạy sinh file.

`aggregate_comments_v2.py` chỉ lấy comment gốc không rác, không duyệt `replies[]`; khác export 5k lấy cả hai cấp. Script này còn trỏ `data/process_*` thay vì `data/processed/process_*` và ghi cứng thư mục máy. Hướng dẫn cũ không nên được dùng như lệnh chạy đã kiểm chứng.

## 7. Kiểm duyệt của con người: hướng dẫn và bằng chứng

`labeling-guide.md` cũ mô tả human-in-the-loop: sửa nhãn LLM sai, giữ nhãn hợp lý, gắn uncertain cho mẫu khó và kiểm tra chéo. Các định nghĩa lớp vẫn là nguồn tham khảo, nhưng ví dụ/tiêu chí rác có chỗ khác rule/prompt hiện tại; chưa có bản phân xử thống nhất được xác nhận.

Phần batch 500 mẫu, `parent_text`, `confidence`, `verified_final.json`, split JSON và các script merge/consensus trong hướng dẫn là quy trình được mô tả ở tài liệu cũ; không coi là tooling đã được triển khai. Export hiện chỉ có bảy cột nêu ở mục 5, không có trường người gán nhãn, thời gian duyệt hoặc confidence.

Chưa có bằng chứng trong phạm vi rà soát về danh sách annotator, phân xử bất đồng, Cohen's Kappa, phiên bản guideline áp dụng hoặc gold dataset đã được ký duyệt. Mục tiêu 4.000 mẫu trong hướng dẫn cũ không phải số gold đã hoàn tất.

## 8. Chuẩn bị nhãn và chia tập cho ML

`ml/phobert/phobert_finetune_colab.py` thực hiện:

1. Đọc CSV; lấy `verified_label` nếu không null/rỗng, nếu không thì dùng `llm_emotion`/`llm_stance`.
2. Nếu `is_trash == True`, ghi đè nhãn cuối thành `is_trash`, kể cả người đã điền nhãn khác. Không có bước cập nhật lại cờ rác từ ý kiến người duyệt.
3. Chỉ giữ nhãn đúng bộ giá trị hợp lệ, tạo `label_id`, bỏ dòng text/label thiếu.
4. Stratified split 70/15/15 theo nhãn, seed 42, ở cấp dòng bình luận. Không nhóm theo `event_id`, thread hoặc người viết.

Các tập chia được tạo trong bộ nhớ khi chạy; không đồng nghĩa đã có ba file JSON split như hướng dẫn cũ. Việc cho phép fallback khiến tập huấn luyện/test có thể dùng nhãn tự động nếu CSV chưa duyệt. Giá trị như mã không dấu hoặc `uncertain` không thuộc bộ nhãn hợp lệ sẽ bị loại, không có hàng đợi phân xử riêng.

GNN cũng chia node 70/15/15 có stratify, seed mặc định 42 trong `train_gnn_node_classification.py`. Không có bảo đảm tách sự kiện giữa train/val/test chỉ từ cách chia này. Do đó không diễn giải kết quả như đánh giá trên các sự kiện hoàn toàn mới.

## 9. Giới hạn và câu hỏi mở

1. Snapshot nguồn `full/`, insight và dữ liệu kiểm thử không hoàn toàn khớp; bộ nào là dữ liệu chính thức cho từng thí nghiệm?
2. Có file kiểm duyệt hoàn thành ngoài hai CSV hiện tại hoặc ngoài repo không? Cần xác nhận trước khi gọi là gold set.
3. Những mẫu mang `is_label_correct` đã được ai kiểm tra và theo phiên bản guideline nào? Cờ đúng/sai không tự cung cấp nhãn thay thế cho mẫu sai.
4. Nhãn trung lập do fallback, nhãn rule và nhãn LLM chưa có provenance riêng ở từng dòng; chưa định lượng được tỷ lệ lỗi gán nhãn từ artifact cuối.
5. Chia theo dòng/node không ngăn trùng nội dung hoặc sự kiện giữa các tập; chưa xác minh một bộ test độc lập được cố định xuyên các phiên bản.

## 10. Nguồn đối chiếu

- [Code gán nhãn Showbiz](../analysis/single/analyze_comments.py), [Code gán nhãn Giáo dục](../analysis/single/analyze_education_async.py).
- [Export 5k](../sampling_labeling/export_5k_for_verification.py), [lấy mẫu nhỏ](../sampling_labeling/sample_comments.py), [gộp bình luận](../sampling_labeling/aggregate_comments_v2.py).
- [Hướng dẫn gán nhãn cũ](../sampling_labeling/data_labels/labeling-guide.md), [quy trình lấy mẫu cũ](../sampling_labeling/data_sampling_process.md) — giữ làm tham chiếu, đối chiếu lại với code.
- [CSV Giáo dục](../sampling_labeling/data_labels/verify_education_5k.csv), [CSV Showbiz](../sampling_labeling/data_labels/verify_showbiz_5k.csv).
- [Tập thử Giáo dục](../data/test-sets/data_test_edu.json), [Showbiz](../data/test-sets/data_test_show.json), [Showbiz có cờ kiểm tra](../data/test-sets/data_test_show_da_check.json).
- [Chuẩn bị và chia tập PhoBERT](../ml/phobert/phobert_finetune_colab.py), [chia tập GNN](../ml/gnn/train_gnn_node_classification.py).
