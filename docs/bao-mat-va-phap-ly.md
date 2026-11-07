# Bảo mật, dữ liệu, pháp lý và đạo đức

Document loại 12/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

Phạm vi: cơ chế bảo mật, cách xử lý dữ liệu và bằng chứng quản trị hiện có trong code/tài liệu. Không đặt chính sách mới, không suy ra quyền sử dụng dữ liệu từ việc code thu thập được, và không kết luận hệ thống đã tuân thủ pháp luật. Phần pháp lý ghi nhận tài liệu chứng minh đang có hoặc chưa được cung cấp; không thay cho đánh giá pháp lý.

Thu thập xem [loại 4](./thu-thap-du-lieu.md), nhãn và tập dữ liệu xem [loại 5](./gan-nhan-va-tap-du-lieu.md), hợp đồng tích hợp xem [loại 9](./hop-dong-tich-hop.md). **Luồng agent n8n ở loại 7 còn thiếu**, nên quyền truy cập, lịch sử và cách gửi dữ liệu qua các node cloud chưa được đối chiếu đầy đủ.

## 1. Phạm vi bằng chứng

Nguồn là code, cấu hình được đọc theo tên biến, schema/artifact và tài liệu sẵn có. Lần rà soát không gọi API, thử đăng nhập, kiểm tra tài khoản cloud, khai thác lỗi, nạp pickle/checkpoint hoặc đọc giá trị trong file khóa/session. Không đưa khóa, cookie, credential ID hay nội dung bình luận/hội thoại của người thật vào document.

“Chưa có bằng chứng trong phạm vi rà soát” không có nghĩa một sự đồng ý, giấy phép hay biện pháp vận hành chắc chắn không tồn tại. Code local cũng không cho biết đầy đủ quyền chia sẻ Drive/Sheets, cấu hình n8n, RLS Supabase hoặc ai đang giữ bản sao dữ liệu.

## 2. Nhóm dữ liệu và vị trí xử lý

| Nhóm | Nội dung có thể được giữ theo code/schema | Nơi sử dụng |
|---|---|---|
| Sự kiện và bài báo/bài đăng | Tên sự kiện, nội dung, nhân vật, thời gian, link nguồn | JSON thô/đã gộp, SQLite và website |
| Bình luận/reply | Text, mã bình luận/sự kiện, quan hệ trả lời, likes, nhãn cảm xúc/lập trường/toxic | JSON full, file lấy mẫu, Parquet, đặc trưng/đồ thị ML |
| Hội thoại | Câu hỏi, câu trả lời, user_id, timestamp và thông tin định tuyến | history local; dashboard đọc bản GitHub raw |
| Phiên đăng nhập và bí mật | Tài khoản Facebook, cookie, khóa LLM, service account | Crawler, script, browser dashboard và cấu hình ngoài source |
| Vết vận hành | Log tiến độ/lỗi, URL, đoạn text debug và ảnh chụp trang khi nhánh debug chạy | Console, run_log.jsonl, output crawler |

Text tự do có thể chứa tên, thông tin liên hệ, thông tin về người khác hoặc nội dung nhạy cảm; việc sinh một comment_id mới không tự xóa các nội dung đó. Schema nhãn/đồ thị không chứng minh bình luận đã được ẩn danh. Không gán mọi field text thành dữ liệu vô danh chỉ vì không có cột tên người viết riêng.

`history.json` giữ user_id cùng question/answer/timestamp. Dashboard hiển thị câu hỏi, câu trả lời và thời gian; việc không hiển thị user_id trong thẻ UI không đồng nghĩa bản dữ liệu tải về đã bỏ user_id.

## 3. Khóa, cấu hình và cookie Facebook

`.gitignore` có mẫu loại `.env`, file credential, api*.txt, session JSON và thư mục export n8n; riêng `data/` được cho phép. Đây là quy tắc Git, không phải mã hóa file, phân quyền máy, kiểm soát truy cập HTTP hay bằng chứng bí mật chưa từng nằm trong lịch sử Git/bản sao khác.

Kiểm tra Git index local cho thấy history.json, QA.json, events.db và nhiều file trong data/ đang được track. Điều này cho biết dữ liệu nằm trong phạm vi phiên bản hóa local, không chứng minh repository remote đang công khai hay ai có quyền xem. Export thu thập n8n local hiện không được track và bị ignore; kiểm tra mẫu chuỗi cho thấy vẫn có literal giống khóa API trong file. Không trích lại hoặc thử xác thực các chuỗi đó.

Các script/config tham chiếu khóa LLM, thông tin Facebook và Google service account. Tài liệu chỉ ghi tên cấu hình và vai trò; không liệt kê giá trị, số tài khoản hay đường dẫn tới file bí mật để chia sẻ. Chưa xác minh secret manager, thời hạn khóa, phạm vi hạn chế theo ứng dụng hoặc quy trình thu hồi đang vận hành.

`auth.py` của crawler tự viết dùng email/password khi cần đăng nhập và lưu cookies của context thành JSON để nạp lại. Trong hàm save/load đã đọc không có lớp mã hóa cookie. Checkpoint/2FA có bước chờ người thao tác; không được coi là cơ chế xác thực cho người dùng website.

`sheets_reader.py` tạo Google credentials với scope `spreadsheets.readonly`. Scope này mô tả yêu cầu của luồng đọc crawler; không chứng minh toàn bộ service account, project Google hoặc các node n8n khác chỉ có quyền đọc.

Theo user xác nhận, crawler Facebook tự viết không hiệu quả nên dự án đã chuyển sang Apify. Code cookie/login còn lại trong repo không phải bằng chứng crawler đang là luồng thu thập chính hoặc đã được dùng trên mọi bộ dữ liệu hiện có.

## 4. Ranh giới browser, API và cloud

### 4.1 API website

FastAPI hiện có các route dữ liệu GET, không thấy auth dependency, role check hoặc rate limiter trong `app.py`. CORS cho origin `*`, method GET và header `*`; đây không phải kiểm tra danh tính người gọi. Chưa kiểm tra gateway/network policy bên ngoài app để kết luận endpoint thực tế đang công khai hay bị giới hạn.

Giá trị lọc/ID được truyền bằng placeholder SQLite. Cơ chế này không phải kết luận audit toàn bộ ứng dụng; q vẫn có ý nghĩa wildcard SQL LIKE. Response chưa có response_model, dữ liệu `links` được decode từ JSON lưu trong DB; không có validation xuyên suốt được xác minh tại ranh giới này.

API phục vụ dữ liệu sự kiện/nhân vật và số liệu tổng hợp; không có route tải toàn bộ bình luận trong file app đã đọc. Điều đó không bảo đảm các bản JSON/CSV, kho Git hoặc Drive không được chia sẻ qua cách khác.

### 4.2 Chatbot website

Client tạo UUID và lưu cookie userId với path `/`, max-age một năm; request POST gửi message/userId trực tiếp tới webhook n8n. Chuỗi gán cookie trong code không khai báo Secure hoặc SameSite; userId không phải tài khoản đăng nhập hay quyền truy cập. Request không gửi toàn bộ mảng messages của UI.

Chưa có workflow server để kiểm tra xác thực webhook, mapping userId sang Memory, cách cô lập lịch sử giữa người dùng, log request hoặc nơi lưu/xóa hội thoại. Chưa kết luận phạm vi người có thể xem lịch sử trên cloud; xem [loại 7](./llm-agent-rag.md).

### 4.3 Dashboard gọi Gemini trong browser

`InteractionView.tsx` tải danh sách khóa từ `/api.txt`, tạo GoogleGenAI và gọi `gemini-2.5-flash` ngay trong browser. Nếu tính năng chạy theo code này, client cần đọc được khóa sử dụng; Git ignore file khóa không tự bảo vệ đường dẫn HTTP đó. Chưa kiểm tra host hoặc khóa thực tế trong lần viết tài liệu.

Hàm tổng hợp nối các câu hỏi đã tải thành prompt để suy ra top chủ đề; không chỉ gửi số đếm thống kê. Đây là một luồng gửi dữ liệu ra nhà cung cấp LLM riêng với chatbot n8n.

## 5. Dữ liệu gửi tới dịch vụ bên ngoài

| Luồng theo code/tài liệu hiện có | Dữ liệu chuyển qua ranh giới | Giới hạn xác minh |
|---|---|---|
| Script gán nhãn → Groq | Nội dung sự kiện/bình luận và phần text cha của reply theo prompt | Chưa có bước che thông tin cá nhân tổng quát được xác minh trước request |
| Tiền xử lý/tổng hợp → Gemini | Text cần lọc hoặc nội dung các bài cùng sự kiện; crawler chỉ tổng hợp nhiều bài có text | Không suy ra chính sách lưu/xử lý của nhà cung cấp từ SDK |
| Dashboard → Gemini | Các câu hỏi trong lịch sử đã tải | Không có bằng chứng chỉ gửi dữ liệu đã ẩn danh |
| Thu thập n8n → SerpApi/Firecrawl/Apify | Từ khóa, URL hoặc yêu cầu lấy nội dung/bình luận | Chỉ có export thu thập local; chưa đối chiếu cấu hình cloud hiện tại |
| RAG theo báo cáo → Supabase/Cohere/LLM | Chunk, embedding, câu hỏi và ngữ cảnh truy xuất | Workflow/schema/quyền truy cập còn thiếu; không coi là flow live đã kiểm tra |

Không lấy việc gửi qua HTTPS hoặc dùng SDK làm bằng chứng có hợp đồng xử lý dữ liệu, vùng lưu trữ, thời hạn lưu, quyền xóa hay chính sách không dùng dữ liệu để huấn luyện. Các điều khoản/cấu hình tài khoản đó chưa được cung cấp để đối chiếu trong repo.

## 6. Ẩn danh, lưu giữ và khả năng truy vết

Trong các đường đi gán nhãn, xuất mẫu và hội thoại đã đọc, chưa xác minh một bước chung nhận diện/che tên, số điện thoại hoặc thông tin cá nhân trước mọi lần lưu/chia sẻ/gọi LLM. Lọc rác và cắt độ dài prompt giải quyết mục đích khác, không chứng minh đã ẩn danh dữ liệu.

`storage._clean_event()` của crawler bỏ category, source_urls, _scraped_at và url_source trước khi ghi sự kiện mới. Đây là loại bỏ metadata, không phải ẩn danh text; đồng thời làm giảm khả năng truy về nguồn/thời điểm thu thập của bản ghi lưu.

Các JSON/CSV/XLSX, Parquet, graph và embedding là nhiều bản biểu diễn của dữ liệu nguồn. Chưa có manifest chung để nối hết bản sao, phiên bản nhãn và checkpoint theo yêu cầu sửa/xóa một sự kiện hoặc bình luận. Không có bằng chứng quy trình xóa xuyên các kho đã được thực hiện và kiểm tra.

Chưa xác minh thời hạn lưu, lịch xóa, người phụ trách cấp/thu hồi quyền, chính sách backup hoặc cách phục hồi/xóa bản sao. Thời hạn một năm của cookie client không phải retention policy cho history, file Drive, n8n executions hay Supabase.

## 7. Log, ảnh debug và artifact ML

Log phiên gán nhãn giữ tiến độ, thời gian và stop_reason; các nhánh khác có thể ghi URL, phần nội dung lỗi hoặc một đoạn text bình luận. Scraper còn có nhánh chụp screenshot trang để debug. Không coi log/ảnh debug là dữ liệu đã khử nhận diện chỉ vì không thuộc dataset huấn luyện.

Các script GNN đọc graph bằng pickle.load; một số script ML nạp checkpoint bằng torch.load. Đây là ranh giới tin cậy đối với file artifact, không có bằng chứng kiểm tra chữ ký/hash nguồn trong các lệnh nạp đã khảo sát. Lần rà soát này không nạp hoặc thực thi các file đó; chưa có kết quả audit đường nạp artifact.

## 8. Bằng chứng pháp lý và quản trị còn thiếu

| Chủ đề | Thông tin hiện có / chưa được xác minh |
|---|---|
| Quyền thu thập và dùng lại | Có code lấy dữ liệu và nguồn URL; chưa có hồ sơ cho phép/điều khoản áp dụng gắn với từng nguồn/lần thu thập được đối chiếu |
| Đồng ý/thông báo cho người có dữ liệu | Chưa được cung cấp bằng chứng, phạm vi, mục đích hoặc cơ chế quản lý tương ứng trong các nguồn đã đọc |
| Nội dung báo và bài đăng | Có nội dung/trích xuất/link; chưa xác minh giấy phép tái sử dụng, điều kiện công bố hoặc quyền ảnh |
| Phê duyệt nghiên cứu/đạo đức | Có bối cảnh đề tài NCKH; chưa xác minh hồ sơ phê duyệt, người chịu trách nhiệm hoặc giới hạn nghiên cứu |
| Dữ liệu về học sinh/người chưa thành niên | Chủ đề Giáo dục có thể liên quan nhóm này; chưa có phân loại/đối chiếu danh tính, độ tuổi hay quy trình riêng được xác minh |
| Cloud và bên nhận dữ liệu | Có tên dịch vụ trong code/báo cáo; chưa đối chiếu hợp đồng, quyền tài khoản, vùng xử lý/lưu giữ hoặc khả năng xóa |
| Chia sẻ/công bố/chỉnh sửa | Chưa xác minh quy trình duyệt dữ liệu được công bố, tiếp nhận phản hồi và sửa/xóa xuyên các bản sao |

Những khoảng trống trên là trạng thái bằng chứng, không phải kết luận vi phạm hoặc khẳng định không tồn tại sự cho phép ngoài repo. Việc Facebook/báo chí được tải thành công, dùng Apify hay được mô tả trong báo cáo không tự chứng minh các quyền và điều kiện áp dụng đã được xác nhận. Tài liệu này không chốt văn bản pháp luật hay diễn giải nghĩa vụ cho dự án.

## 9. Giới hạn đạo đức khi phân tích và trình bày

Emotion, stance, toxic và controversial là đầu ra rule/LLM hoặc mô hình, có thể sai và chịu ảnh hưởng ngữ cảnh tiếng Việt, cách lấy mẫu, nhãn lệch lớp và fallback trung lập. Chúng mô tả phân loại của hệ thống, không phải kết luận về phẩm chất, ý định, hành vi vi phạm hoặc sự thật của cáo buộc đối với người được nhắc tới.

Top sự kiện trong insight dựa trên tập bình luận đã thu thập; top câu hỏi dashboard là kết quả LLM trên lịch sử. Không có thiết kế mẫu đại diện toàn bộ cộng đồng được xác minh, nên các kết quả này không đủ làm kết luận quan điểm của toàn xã hội.

Text bình luận, tên sự kiện và nhân vật có thể lặp lại cáo buộc, ngôn từ xúc phạm hoặc thông tin chưa kiểm chứng. Chưa xác minh cơ chế duyệt trước công bố, khiếu nại/chỉnh sửa hoặc phân xử nhãn sai; các ví dụ hội thoại và prompt không chứng minh những cơ chế đó đã vận hành.

Prompt yêu cầu không bịa/không tự trả lời chỉ là chỉ dẫn. Chưa có bằng chứng kiểm thử toàn diện việc chống prompt injection từ nội dung thu thập, dẫn nguồn sai, suy diễn quá ngữ cảnh hoặc lộ dữ liệu qua câu trả lời. Phần agent n8n tiếp tục thiếu bằng chứng theo loại 7.

## 10. Phần cần user làm rõ khi bổ sung hiện trạng

1. Ai đang có quyền với Git/Drive/Sheets/n8n/Supabase, dữ liệu nào được công bố, khóa/session nào đang sử dụng và cơ chế thu hồi thực tế?
2. Có hồ sơ quyền sử dụng nguồn, thông báo/đồng ý, giấy phép nội dung hoặc phê duyệt nghiên cứu ngoài repo không?
3. Chính sách lưu/xóa/backup, xử lý phản hồi và xóa dữ liệu xuyên các kho đang áp dụng là gì?
4. Workflow agent n8n, schema/RLS Supabase và điều khoản/cấu hình xử lý dữ liệu của các dịch vụ đang dùng cụ thể ra sao?

## 11. Nguồn đối chiếu

- [Quy tắc Git ignore](../.gitignore), [API website](../serving/web_v2/backend/app.py), [ETL và nguồn ảnh](../serving/web_v2/backend/build_db.py), [tải ảnh](../serving/web_v2/backend/og_image_scraper.py).
- [Cookie/login crawler](../ingestion/code_cao_fb_chuahoanthien/auth.py), [đọc Sheets](../ingestion/code_cao_fb_chuahoanthien/sheets_reader.py), [storage](../ingestion/code_cao_fb_chuahoanthien/storage.py), [scraper/debug](../ingestion/code_cao_fb_chuahoanthien/scraper.py).
- [Gán nhãn Showbiz](../analysis/single/analyze_comments.py), [Giáo dục](../analysis/single/analyze_education_async.py), [tiền xử lý](../preprocessing/single/tienxuly_vietlaiorder.py), [tổng hợp bài](../ingestion/code_cao_fb_chuahoanthien/gemini_summarizer.py).
- [Chatbot client](../serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx), [Gemini dashboard](../serving/dashboard/src/components/views/InteractionView.tsx), [graph/feature loader](../ml/gnn/concat_node_features.py), [PhoBERT checkpoint loader](../ml/phobert/phobert-batch-inference.py).
