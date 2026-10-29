# Thuộc tính chất lượng

Document loại 11/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: thuộc tính chất lượng thể hiện trong code, cấu hình, dữ liệu và kết quả đã có. Tài liệu phân biệt cơ chế cài đặt với bằng chứng kiểm chứng; không đặt thêm SLA/SLO, ngưỡng nghiệm thu hoặc mục tiêu từ lộ trình phát triển.

Kết quả đo và phương pháp xem [loại 8](./danh-gia-va-benchmark.md), hợp đồng dữ liệu xem [loại 9](./hop-dong-tich-hop.md), serving xem [loại 10](./backend-serving.md). **Loại 7 còn thiếu luồng agent n8n**, chờ user bổ sung; không suy ra chất lượng chatbot cloud từ prompt local.

## 1. Mức bằng chứng sử dụng

| Mức | Ý nghĩa trong tài liệu |
|---|---|
| Cơ chế có trong code | Đã đọc nhánh xử lý/cấu hình, chưa mặc định chạy tốt trong mọi môi trường |
| Artifact đã kiểm tra | JSON, metric hoặc SQLite đã được đọc/đối chiếu; không phải phép đo lại toàn hệ thống |
| Kết quả báo cáo cũ | Giữ nguồn và giới hạn phiên bản; không coi là xác nhận runtime hiện tại |
| Chưa xác minh | Thiếu kiểm thử, dữ liệu hoặc cấu hình thực tế để kết luận |

Không có một tỷ lệ “chất lượng toàn hệ thống” được tính chung. Đúng schema, đúng nhãn, đủ dữ liệu, tốc độ xử lý và câu trả lời có căn cứ là các thuộc tính khác nhau.

## 2. Đúng chức năng và tương thích dữ liệu

FastAPI có ràng buộc kiểu/phạm vi cho page, per_page và limit; query dùng placeholder cho giá trị lọc. Tuy nhiên response là dict trực tiếp, chưa có response_model: OpenAPI 200 có schema rỗng. Client website ánh xạ trường thủ công, còn interface TypeScript của dashboard không tự kiểm tra JSON remote khi chạy.

Một số giới hạn chức năng đã thấy trong code: platform của events được ETL gán news; một số hàm client bỏ qua tham số platform; hàm lấy “latest” vẫn theo thứ tự số bình luận của API; số bình luận ngoài top insight có thể bằng 0 do mapping. Không dùng tên hàm hoặc tên trang làm bằng chứng chức năng đã phân tách đúng nguồn.

Các verifier chỉ bảo đảm trong phạm vi hẹp:

| Kiểm tra | Điều kiện thực tế | Không chứng minh |
|---|---|---|
| Preprocessing | Hai tập comment_id giữ lại không khác nhau | Dòng lặp, text/likes/parent/schema đều khớp |
| PMI | Main yêu cầu giao tập top 5 đạt ít nhất 60% cho mỗi lĩnh vực | Top 10 đạt Jaccard cố định, thứ tự/score giống hệt |
| Route/OpenAPI local | Đã đối chiếu hình dạng trả về với SQLite chỉ đọc ở loại 9 | HTTP end-to-end, tải đồng thời hoặc cloud hoạt động |

Ngưỡng PMI trên là điều kiện đang cài trong verifier, không phải tiêu chí chất lượng mới được đặt cho sản phẩm. Docstring còn mô tả ngưỡng khác main; chi tiết tại loại 8.

## 3. Chất lượng dữ liệu và kết quả AI

Rule lọc rác, kiểm tra ID đầu ra và prompt hai bước giúp giới hạn một số lỗi gán nhãn, nhưng không thay được nhãn kiểm chứng. Fallback khi API/parse thiếu kết quả có thể gán trung lập và không toxic; artifact cuối chưa luôn tách nhãn fallback khỏi nhãn LLM thành công.

Hai tập verify 5k hiện có cột verified_label trống trong cả CSV/XLSX; có ID bình luận lặp và các snapshot dữ liệu không hoàn toàn khớp. Tập test nhỏ có cờ đúng/sai nhưng thiếu nhãn thay thế và dấu vết kiểm duyệt đầy đủ. Không coi tên file verify hoặc số dòng đã xuất là bằng chứng gold set hoàn tất; xem [loại 5](./gan-nhan-va-tap-du-lieu.md).

GNN có F1-macro lưu sẵn 0,5239 Giáo dục và 0,2170 Showbiz; đây là khớp nhãn artifact trong cách chia node hiện có. Weighted F1 Showbiz cao không thay thế macro F1 thấp. PhoBERT/GNN vẫn cần làm lại theo trạng thái user đã lưu; chưa có bằng chứng classifier đã thay LLM trong serving. Phương pháp, metric và giới hạn rò rỉ/chia tập ở [loại 6](./mo-hinh-ml-va-phan-tich.md) và loại 8.

Prompt RAG yêu cầu không bịa hoặc báo thiếu dữ liệu là cơ chế chỉ dẫn, không phải bảo đảm loại bỏ ảo giác. Workflow agent, retrieved contexts, rubric và log chấm chưa đủ để xác minh lại các chỉ số RAG trong báo cáo; phần này tiếp tục mở theo loại 7.

## 4. Hiệu năng và thời gian phản hồi

| Thành phần | Cơ chế / bằng chứng hiện có | Giới hạn kết luận |
|---|---|---|
| API | SELECT trực tiếp, phân trang; chỉ mục category và số bình luận | Chưa có latency p50/p95, throughput, tải đồng thời hoặc mức dùng bộ nhớ API |
| LLM offline | Batch 10; semaphore Showbiz 3, Giáo dục tối đa 5 | Không đồng nghĩa mọi batch đều chạy song song; bước 1 Giáo dục gọi tuần tự |
| PMI Python/Spark | Hai bộ benchmark local lưu sẵn | Phạm vi timer khác nhau, một phép đo/cấu hình; chưa có độ biến thiên |
| GNN | Artifact đo forward khi đã có graph/feature/model | Không tính tổng chi phí tạo đặc trưng, thu thập hoặc pipeline end-to-end |
| Dashboard | Poll JSON mỗi 30 giây | Không phải cam kết dữ liệu mới nhất hoặc phản hồi trong 30 giây |

Benchmark cùng input đang lưu cho thấy Python nhanh hơn Spark ở các cấu hình đã đo. Scale x3 chỉ nhân lại text, không phải thêm các sự kiện độc lập; local[4] đạt khoảng 1,03x trong bảng scale, chưa đủ chứng minh lợi thế ổn định. Các hệ số tăng tốc GNN/LLM dùng thời gian LLM giả định, không phải benchmark API LLM thực tế.

Chưa có cam kết uptime, thời gian đáp ứng tối đa, tải hỗ trợ hoặc ngân sách chi phí được xác minh. Timeout từng request và số lần retry không được diễn giải thành SLA toàn tác vụ.

## 5. Độ tin cậy khi phụ thuộc bên ngoài lỗi

| Luồng | Xử lý trong code | Hệ quả còn lại |
|---|---|---|
| Groq Showbiz | Tối đa 5 lượt mặc định, timeout HTTP 120 giây; có backoff/xoay khóa theo lỗi | Có thể trả fallback sau lỗi; chưa có deadline chung cho toàn bộ file |
| Apps Script lúc build DB | Timeout 20 giây; lỗi trả lookup rỗng và tiếp tục | Links/status có thể trống trong DB mới |
| Lấy ảnh | Timeout 8 giây, concurrency 10; lỗi trả None; ETL thử tối đa hai URL theo nhánh hiện có | Không bảo đảm mọi event có ảnh hoặc URL ảnh còn sống về sau |
| Dashboard insight | State khởi tạo từ constants; fetch lỗi giữ dữ liệu đang có | Có giao diện/số liệu không chứng minh tải dữ liệu mới thành công |
| API client website | Kiểm tra res.ok rồi ném lỗi | Chưa có timeout/abort/retry trong helper |
| Chatbot client | Hiển thị loading và khóa input; lỗi có thể lấy câu mẫu | Không kiểm tra res.ok/timeout/retry; câu mẫu không phải câu trả lời RAG đã xác minh |

Retry và xoay khóa giảm một số gián đoạn nhưng không bảo đảm tác vụ hoàn tất, dữ liệu đầy đủ hoặc kết quả đúng. Chưa có số đo tỷ lệ lỗi, retry success, quota exhaustion hoặc thời gian phục hồi toàn hệ thống.

## 6. Khôi phục, toàn vẹn ghi và nhất quán

Một số script phân tích lưu full/summary và log theo file/sự kiện; kiểm tra output tồn tại có thể giúp bỏ qua việc đã xử lý. Tuy vậy, một file đã tồn tại không tự chứng minh mọi batch/URL đều hoàn chỉnh hoặc đúng phiên dữ liệu.

Crawler Facebook Python lọc mã sự kiện đã có trong output; nếu chỉ một phần URL thành công thì sự kiện vẫn được lưu và lần sau có thể bị bỏ qua toàn bộ. Storage ghi lại danh sách bằng mode w, chưa có ghi file tạm rồi đổi tên nguyên tử. Metadata nguồn/thời điểm của bản ghi mới còn bị clean bỏ; không coi đây là cơ chế resume theo từng URL hoặc audit đầy đủ. Crawler này chưa hoàn thiện; dự án đã chuyển sang Apify do cào tự viết không hiệu quả, xem [loại 4](./thu-thap-du-lieu.md).

ETL SQLite DROP/tạo lại bảng, commit dữ liệu cơ bản trước giai đoạn ảnh. Chưa có cơ chế dựng DB tạm rồi công bố nguyên tử được xác minh; chưa kiểm thử chạy ETL đồng thời với API. API không tự dựng lại DB khi thiếu và `/` không phải kiểm tra readiness của dữ liệu.

Kiểm tra SQLite local ở loại 10 có quick_check=ok và foreign_key_check không báo vi phạm. Đây là kiểm tra artifact tại thời điểm đọc, không chứng minh backup/restore, chịu lỗi khi đang ghi hoặc cưỡng chế khóa ngoại trên mọi kết nối.

Website dùng SQLite, dashboard đọc JSON remote và chatbot dùng nguồn n8n/Supabase chưa đối chiếu đầy đủ. Chưa có manifest/hash/version chung để bảo đảm chúng cùng snapshot; thời điểm tải thành công của dashboard không phải thời điểm dữ liệu được thu thập/phân tích.

## 7. Khả năng mở rộng và tính di động

Spark factory tạo local[N]/local[*], mặc định theo đường dẫn JDK 17, Hadoop và Python Windows. PMI còn collect dữ liệu về driver; GNN huấn luyện trên graph/tensor toàn bộ node; crawler Python xử lý sự kiện/URL tuần tự. Các cơ chế này không chứng minh đã chạy cụm nhiều máy, phân vùng job, autoscaling hoặc giới hạn bộ nhớ được kiểm soát ở tải lớn.

API dùng một kết nối SQLite mới cho mỗi handler dữ liệu, đóng trên đường chạy bình thường; không có pool/cache trong file app. Chưa có kết quả nhiều worker, lock contention hoặc chạy ETL và API cùng lúc để chốt năng lực phục vụ đồng thời.

Một số module neo đường dẫn theo vị trí file, nhưng script khác còn đường dẫn máy/thư mục chạy cố định, import Spark cũ và dependency theo từng thành phần. README local giúp tái tạo thao tác trên máy hiện tại, chưa chứng minh khả năng chuyển sang môi trường khác không cần chỉnh cấu hình.

## 8. Quan sát vận hành, bảo trì và tái lập

Script gán nhãn có print tiến độ và run_log.jsonl theo phiên: session_id, thời gian bắt đầu/kết thúc, elapsed, số file đã làm/còn lại và stop_reason. Crawler dùng logging; Spark factory tắt hiển thị tiến độ console, còn các script gọi Spark đặt log level theo từng luồng. Đây là các điểm quan sát cục bộ, chưa có bằng chứng hệ thống log/metric tập trung và cảnh báo vận hành đã được nối. Log local hiện có bốn phiên Giáo dục (ba quota_exhausted, một completed) và một phiên Showbiz completed; đây là số phiên được lưu, không đại diện toàn bộ lần chạy hoặc chứng minh độ đúng của nhãn.

Log phiên không tự cung cấp provenance nhãn ở từng bình luận hoặc liên kết đầy đủ request → nguồn → output → câu trả lời. Việc bắt exception rồi dùng fallback có thể giúp tiến trình tiếp tục nhưng cần đọc log/nguồn để nhận ra dữ liệu suy giảm chất lượng.

Metric/model artifact lưu một phần seed và hyperparameter; benchmark thiếu manifest môi trường và hash input. GNN metric chưa ghi đủ lựa chọn loss/weight so với trainer hiện tại. Các phép đo cũ không được coi là tái lập chỉ từ tên file; xem loại 8.

Code chia thư mục theo thu thập/xử lý/ML/serving; API và ETL tách riêng nên có thể khảo sát từng phần. Tuy nhiên chưa có schema dữ liệu phiên bản chung hoặc validation xuyên toàn pipeline; tài liệu phải tiếp tục đối chiếu code khi chỉnh một đầu nối.

## 9. Bảo mật và trải nghiệm sử dụng ở mức hiện trạng

API dùng placeholder SQL nhưng chưa có auth dependency, rate limiter hay CORS allowlist riêng. Dashboard đọc khóa Gemini từ file public để gọi trong browser; cookie userId của chatbot chỉ là định danh hội thoại. Các điểm này giới hạn cách diễn giải “an toàn” của hệ thống; chưa có kết quả audit/pháp lý hoặc kiểm thử bảo mật toàn diện trong phạm vi tài liệu này.

Website/dashboard có trạng thái loading, thông báo lỗi, theme và các trang/tab trong code. Chưa có bằng chứng kiểm thử accessibility, khả dụng trên thiết bị/browser, người dùng thật hoặc khả năng nhận biết mọi trạng thái fallback. Không dùng việc giao diện render được để kết luận độ dễ dùng/khả năng tiếp cận đã đạt chuẩn.

## 10. Phạm vi kiểm chứng và phần còn mở

Lần viết tài liệu này chỉ đối chiếu code và nguồn hiện có; không chạy lại benchmark, training, HTTP/load test, fault injection hoặc gọi cloud. Các số đo/kiểm tra trước đó được dẫn đúng phạm vi ở loại 8–10, không đổi thành kết quả thử nghiệm mới.

Thông tin chưa đủ để chốt: mục tiêu chất lượng định lượng do user chấp thuận; manifest dữ liệu/môi trường; phép đo end-to-end và tải lặp; hành vi phục hồi sau lỗi; workflow agent n8n và schema Supabase; kết quả bảo mật/khả dụng/accessibility. Không tự lấp các khoảng trống này bằng ngưỡng giả định hoặc ý tưởng phát triển.

## 11. Nguồn đối chiếu

- [API](../serving/web_v2/backend/app.py), [ETL SQLite](../serving/web_v2/backend/build_db.py), [lấy ảnh](../serving/web_v2/backend/og_image_scraper.py), [client API](../serving/web_v2/frontend/src/services/api.js).
- [Gán nhãn Showbiz](../analysis/single/analyze_comments.py), [Giáo dục](../analysis/single/analyze_education_async.py), [storage crawler](../ingestion/code_cao_fb_chuahoanthien/storage.py), [điều phối crawler](../ingestion/code_cao_fb_chuahoanthien/main.py).
- [Spark factory](../preprocessing/spark/spark_session_factory.py), [PMI Spark](../analysis/spark/pyspark_pmi_keywords.py), [verify preprocessing](../preprocessing/spark/verify_preprocessing.py), [verify PMI](../analysis/spark/verify_pmi_keywords.py).
- [Dashboard App](../serving/dashboard/src/App.tsx), [Interaction](../serving/dashboard/src/components/views/InteractionView.tsx), [Chatbot](../serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx).
