# Maintenance

Document loại 14/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: thao tác duy trì dữ liệu, cấu hình và khả năng chạy lại được hỗ trợ bởi code/tài liệu hiện có. Không đặt lịch bảo trì, phân công nhân sự, SLA hoặc quy trình backup chưa được xác minh. Các thao tác sinh lại dữ liệu dưới đây chỉ được mô tả, không được thực thi khi viết tài liệu.

Pipeline xem [loại 2](./data-pipeline.md), thu thập xem [loại 4](./thu-thap-du-lieu.md), serving xem [loại 10](./backend-serving.md). Agent n8n ở [loại 7](./llm-agent-rag.md) còn thiếu; vận hành workflow cloud chưa đủ thông tin để viết thành runbook hoàn chỉnh.

## 1. Các điểm bảo trì hiện có

| Thành phần | Cơ chế trong code | Giới hạn |
|---|---|---|
| Tiền xử lý Python | Kiểm tra file output tồn tại rồi bỏ qua | Không kiểm tra hash nguồn hoặc nội dung output đã đủ |
| Phân tích LLM | Ghi full/summary và run_log.jsonl; bỏ qua sự kiện đã có cả hai file | Không có checkpoint theo từng batch bình luận |
| Crawler Facebook Python | Đọc mã sự kiện đã lưu để lọc lần chạy tiếp theo | Sự kiện cào dở vẫn có thể bị bỏ qua nếu đã lưu |
| Gộp và insight | Script nhận đường dẫn input/output, tạo artifact phục vụ downstream | Không tự đồng bộ mọi kho hoặc kiểm tra snapshot chung |
| Website SQLite | build_db chạy riêng để tái tạo dữ liệu API | Dựng lại bảng, không phải cập nhật lịch sử tăng dần |
| Dashboard | Định kỳ fetch JSON và giữ state khi tải lỗi | Không tự sửa nguồn remote hoặc xác nhận độ mới dữ liệu |

Không có bằng chứng lịch bảo trì chung, job quản lý vòng đời artifact hoặc điều phối toàn bộ pipeline local đã được cài đặt. Node schedule trong export thu thập không đủ để suy ra tất cả các nhánh đều được lên lịch; xem loại 4.

## 2. Duy trì và làm mới dữ liệu

Luồng dữ liệu hiện tại đi từ dữ liệu thu thập, qua làm sạch/gán nhãn, tới summary, dữ liệu sự kiện đã gộp, insight và SQLite. Việc thay đổi một đầu vào không tự kích hoạt tất cả bước sau.

| Khi dữ liệu nguồn thay đổi | Thành phần có liên quan | Điểm phải đối chiếu |
|---|---|---|
| Thêm hoặc sửa bình luận | Preprocessing và hai script phân tích | ID, text, quan hệ reply và nhãn theo lĩnh vực |
| Summary thay đổi | merge_final_data.py → analyze_insights.py | id_content, số lượng sự kiện có phân tích, phân bố nhãn |
| Nội dung web/insight thay đổi | build_db.py | SQLite được dựng từ đúng bộ JSON đang dùng |
| Dữ liệu công bố trên GitHub thay đổi | Dashboard và các nguồn RAG theo tài liệu | Đường dẫn, quyền truy cập và phiên bản remote chưa được suy từ local |
| Kho vector thay đổi | Workflow n8n/Supabase | Chưa có quy trình nạp lại, xóa embedding cũ và đối chiếu live được xác minh |

Hai lĩnh vực có schema nhãn khác nhau; không thay tên trường hoặc gộp lớp chỉ để làm cho một script đọc được. Chi tiết hợp đồng ở [loại 9](./hop-dong-tich-hop.md).

Thư mục full Showbiz, insight và artifact ML hiện không hoàn toàn cùng snapshot. Chạy lại một bước với nguồn mới không chứng minh tái tạo đúng kết quả lịch sử; nguồn và giới hạn số liệu ở [loại 8](./danh-gia-va-benchmark.md).

## 3. Tiếp tục công việc sau gián đoạn

`tienxuly_vietlaiorder.py` bỏ qua khi file đích đã tồn tại. Hai script gán nhãn bỏ qua sự kiện khi đã có cả full và summary; nếu chỉ có một file, sự kiện vẫn có thể được xử lý lại và ghi lại output tương ứng. Không có kiểm tra checksum hoặc xác nhận đủ mọi batch trước khi quyết định skip.

Log phiên gán nhãn ghi thời gian, processed, remaining, stop_reason, files_done và files_remaining. Đây là dữ liệu quan sát để đối chiếu; script không coi log là một transaction bảo đảm mọi output đồng bộ. Dòng completed không chứng minh nhãn đúng hoặc không có fallback.

Code Giáo dục có nhánh dừng khi tất cả tài khoản hết quota và lưu lý do quota_exhausted; code Showbiz có xử lý retry/xoay khóa và có thể dùng nhãn fallback. Không suy ra chỉ chạy lại là dữ liệu sẽ được sửa đầy đủ, vì các file đã tồn tại có thể tiếp tục bị bỏ qua.

Crawler Facebook tự viết chỉ resume ở cấp id_content đã có trong file output. Một URL thành công và một URL thất bại vẫn có thể dẫn tới lưu sự kiện; lần sau cả sự kiện bị lọc khỏi pending. Metadata source_urls/thời điểm còn bị clean bỏ. Theo user, dự án đã chuyển sang Apify do crawler tự viết không hiệu quả; không dùng cơ chế resume này làm mô tả cho Apify.

Chưa có hướng dẫn đã xác minh để tự động chọn lại các batch/URL thiếu mà giữ nguyên toàn bộ nhãn hoặc phần con người đã sửa. Tài liệu không đưa thao tác xóa output như một cách phục hồi mặc định.

## 4. Tái tạo SQLite và bảo toàn artifact

`build_db.py` đọc hai JSON local và gọi Apps Script trước khi mở DB, sau đó DROP/tạo lại bảng events/actors. Dữ liệu cơ bản được commit trước giai đoạn lấy ảnh; giai đoạn ảnh có commit riêng theo nhánh xử lý. API không tự gọi script này khi startup hoặc khi DB thiếu.

Nếu Apps Script lỗi, lookup links/status rỗng và build vẫn có thể tiếp tục. Ảnh lỗi có thể để image_url null. Dựng lại DB vì vậy không bảo đảm giữ các enrichment cũ hoặc tạo bản sao giống hệt DB đang có.

| Artifact/thao tác | Hành vi ghi đang có | Ý nghĩa khi bảo trì |
|---|---|---|
| events.db | DROP/tạo lại bảng; không dựng file DB tạm rồi thay nguyên tử | Có thể mất snapshot cũ; chưa kiểm thử build đồng thời với API |
| Full/summary và output crawler | Ghi JSON trực tiếp; crawler ghi lại cả danh sách | Chưa có bảo đảm phục hồi khi gián đoạn giữa lúc ghi |
| Tập kiểm duyệt 5k | Export ghi lại CSV/XLSX cùng tên, tạo verified_label/notes rỗng | Không coi export lại là thao tác giữ nguyên phần kiểm duyệt thủ công |
| Model/feature/benchmark | Script ghi các tên đầu ra theo domain/cấu hình | Tên file không tự bảo toàn nhiều phiên thí nghiệm |

Tạo lại artifact từ nguồn và phục hồi một bản sao lưu là hai việc khác nhau. Chưa xác minh backup tự động, nơi giữ bản sao, lịch lưu, thời hạn giữ hoặc bài thử restore. Không kết luận Git thay thế các cơ chế đó.

## 5. Cấu hình, dependency và môi trường

Backend, hai frontend và GNN có manifest riêng; các lệnh cài/chạy hiện có được mô tả ở README từng phần. Tài liệu này không yêu cầu nâng phiên bản, cài lại hoặc thay dependency khi chưa có task tương ứng.

Những điểm dễ lệch giữa máy hoặc lần chạy:

- Frontend mặc định API cổng 8000; README local hướng dẫn backend 8001 và đặt VITE_API_BASE.
- Spark factory mặc định đường dẫn JDK 17/Hadoop/Python trên Windows; một số script còn import data.spark theo cấu trúc cũ.
- Một số script lấy đường dẫn theo file, một số phụ thuộc thư mục chạy hoặc đường dẫn máy viết cứng. Không chuyển lệnh từ README cũ sang thư mục mới chỉ dựa trên tên script.
- Thư mục chứa artifact ML thực tế có thể khác đường dẫn mặc định mà script đọc; vị trí và tái lập xem [loại 16](./tai-lap-thi-nghiem.md).

Khóa dịch vụ, credential và cookie có vòng đời riêng bên ngoài dữ liệu nghiệp vụ. Chưa xác minh cơ chế hết hạn/thu hồi, owner tài khoản hoặc secret manager đang vận hành. Không đưa giá trị bí mật vào log bảo trì, commit hoặc document; hiện trạng ở [loại 12](./bao-mat-va-phap-ly.md).

## 6. Dấu hiệu lỗi và nơi đối chiếu

| Dấu hiệu | Nguồn kiểm tra trong cài đặt hiện có | Giới hạn |
|---|---|---|
| API dữ liệu 503 | DB_PATH và file events.db | `/` trả thông tin dịch vụ dù dữ liệu chưa sẵn sàng |
| Không thấy sự kiện/ảnh/số bình luận | Input web, insight, links/status và mapping ETL | Không tự kết luận mất bình luận chỉ vì số liệu ngoài top là 0 |
| LLM quota/parse lỗi hoặc output thiếu | Console, run_log.jsonl, full/summary của đúng domain | Fallback có thể giữ tiến trình chạy nhưng làm giảm chất lượng nhãn |
| Spark ModuleNotFoundError | Import và vị trí module hiện tại | Không quy lỗi cho Java trước khi kiểm tra đường dẫn Python |
| Dashboard có số liệu nhưng nguồn mới không tải | fetchData, console và URL GitHub đang cấu hình | State có thể là constants ban đầu hoặc lần tải thành công trước |
| Chatbot báo lỗi hoặc trả câu mẫu | Client webhook và log nếu được cung cấp | Không có workflow agent local để tự xác minh toàn bộ backend n8n |

Tại thời điểm viết, App.tsx trỏ `main/data/analysis-ouput/insights.json`, trong khi file local ở `data/analysis-output/insights.json`. Tên thư mục khác nhau; chưa kiểm tra nguồn remote hoặc tự sửa thay đổi của user. URL hiện tại trong source là căn cứ khi bảo trì, không dùng URL cũ trong báo cáo thay thế.

Dashboard polling 30 giây không tự khắc phục sai đường dẫn; refresh thành công cũng không xác nhận nội dung upstream vừa được tạo. Chi tiết hiển thị và luồng dữ liệu ở [loại 15](./user-workflow-va-chuc-nang.md).

## 7. Trạng thái dự án và tri thức vận hành

AGENTS.md quy định đọc setup-status và TASK_STATE trước task, cập nhật các file memory bị ảnh hưởng sau công việc có ý nghĩa. Document được tra qua doc-map. Các quyết định quan trọng phải giữ vết; không tự đổi trạng thái pending thành hoàn thành chỉ vì có artifact.

`.gitignore` bỏ qua .claude/, plans/, AGENTS*, môi trường ảo và các file bí mật; data được cho phép. Memory/plan local vì vậy không được chứng minh tự đi theo Git sang máy khác. Git theo dõi dữ liệu cũng không tự chứng minh dữ liệu đã có backup được thử phục hồi hay quyền chia sẻ đã được duyệt.

Chưa có lịch bảo trì, người chịu trách nhiệm từng dịch vụ, quy trình nâng cấp/rollback, giám sát tập trung hoặc diễn tập sự cố được xác minh. Đây là thông tin còn mở, không phải một quy trình đã vận hành.

## 8. Phạm vi kiểm chứng và phần còn thiếu

Lần viết tài liệu chỉ đối chiếu source và tài liệu hiện có; không chạy ETL, ghi dữ liệu, gọi nhà cung cấp, dọn thư mục hoặc thay môi trường. Các kiểm tra phù hợp và bằng chứng mới nhất thuộc [loại 13](./testing-va-nghiem-thu.md).

Các phần cần user bổ sung khi có thông tin: export agent n8n; schema/quyền Supabase; nguồn dữ liệu chuẩn cho từng thí nghiệm; cơ chế quản lý khóa/quota; quy trình backup/restore, owner và lịch bảo trì thực tế. Việc thiếu thông tin không đồng nghĩa các biện pháp ngoài repo chắc chắn không tồn tại.

## 9. Nguồn đối chiếu

- [Preprocessing Python](../preprocessing/single/tienxuly_vietlaiorder.py), [phân tích Showbiz](../analysis/single/analyze_comments.py), [Giáo dục](../analysis/single/analyze_education_async.py).
- [Gộp dữ liệu](../analysis/single/merge_final_data.py), [tạo insight](../analysis/single/analyze_insights.py), [export tập kiểm duyệt](../sampling_labeling/export_5k_for_verification.py).
- [Điều phối crawler](../ingestion/code_cao_fb_chuahoanthien/main.py), [storage crawler](../ingestion/code_cao_fb_chuahoanthien/storage.py), [dựng DB](../serving/web_v2/backend/build_db.py).
- [API](../serving/web_v2/backend/app.py), [Dashboard App](../serving/dashboard/src/App.tsx), [Spark factory](../preprocessing/spark/spark_session_factory.py).
- [Backend README](../serving/web_v2/backend/README.md), [website README](../serving/web_v2/README.md), [dashboard README](../serving/dashboard/README.md), [quy tắc Git ignore](../.gitignore).
