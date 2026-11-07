# LLM / Agent / RAG

Document loại 7/16 (xem [doc-map](./doc-map.md)). Cập nhật: 2026-10-29. **Bản nháp chờ user đọc và sửa.**

**Chưa đủ phần agent n8n:** user xác nhận ngày 2026-10-29 luồng agent nằm trong n8n và không có bản luồng tại repo hiện tại; user sẽ giải thích/bổ sung sau. Tạm chuyển sang tài liệu tiếp theo, không coi tài liệu này đã hoàn chỉnh hoặc đã duyệt.

Phạm vi: prompt chatbot, code tích hợp LLM và mô tả RAG trong tài liệu đã có. Chỉ đọc nguồn local; chưa gọi webhook, LLM, Supabase hoặc kiểm tra workflow cloud. Không dùng ý tưởng phát triển làm mô tả cài đặt hiện tại.

Gán nhãn offline và mô hình ML xem [loại 5](./gan-nhan-va-tap-du-lieu.md), [loại 6](./mo-hinh-ml-va-phan-tich.md); các kho dữ liệu xem [loại 3](./database-va-du-lieu.md).

## 1. Nguồn bằng chứng và phạm vi xác minh

| Nguồn local | Xác minh được | Không tự suy ra |
|---|---|---|
| `Chatbot.jsx` | Request/response mà website sử dụng, cookie và fallback giao diện | Workflow server đang chạy đúng prompt nào |
| Bốn file trong `docs/prompts/` | Chỉ dẫn Dispatcher, Insight, Retrieval Showbiz và Final LLM | Tool đã được gắn, schema đầu ra đã có validator |
| Báo cáo nghiệm thu, bản trích `_report_extract.txt` | Mô tả hệ thống tại thời điểm viết báo cáo | Model, bảng, thông số retrieval đang dùng trên cloud |
| `InteractionView.tsx` | Dashboard gọi Gemini để phân tích lịch sử câu hỏi | Đây là một nhánh chatbot RAG hoặc đã được triển khai thành công |

Chưa tìm thấy bản export workflow chatbot/RAG tương ứng trong các nguồn dự án đã khảo sát. `ingestion/n8n/cào data.json` là export thu thập dữ liệu, không dùng làm bằng chứng wiring các agent chatbot.

## 2. Vai trò agent và luồng được mô tả

Báo cáo chương 2.2 và 3.1 mô tả n8n điều phối: câu hỏi → Dispatcher → Retrieval Giáo dục/Showbiz hoặc Insight Analyst → chọn lọc ngữ cảnh → câu trả lời. Nhánh Retrieval dùng Supabase, embedding và rerank; nhánh Insights đọc JSON thống kê. Báo cáo còn mô tả fallback Firecrawl và ghi khoảng trống dữ liệu lên Sheets.

Đây là luồng được tài liệu cũ mô tả. Client hiện chỉ gọi webhook và nhận `reply`; không chứa cài đặt local cho toàn bộ chuỗi trên. Tên “Multi-Agent” trong báo cáo mô tả vai trò các tác nhân, chưa chứng minh mọi bước là agent tự chủ: báo cáo gọi khâu cuối là LLM Chain tĩnh.

| Vai trò | Nguồn mô tả chính | Công việc |
|---|---|---|
| Dispatcher | `agent đầu tien.md` | So khớp sự kiện, phân nhánh và xuất JSON định tuyến |
| Retrieval Showbiz | `lllmsshowbiz.txt` | Trả chunks thô từ Supabase, không trả lời người dùng |
| Retrieval Giáo dục | Báo cáo, chưa có prompt riêng tương ứng | Truy xuất chunks, thử từ khóa ngắn hơn nếu thiếu |
| Insight Analyst | `insight.txt` | Dùng tool Get insight, lấy số liệu đúng nguồn và trình bày |
| Final LLM | `llms trả lời.txt` | Chọn lọc thông tin nhận được để trả lời câu hỏi |

## 3. Dispatcher trong prompt local

### 3.1 Tra cứu và định tuyến

Prompt yêu cầu dùng công cụ tra `data_Sukien.json` trước khi phân luồng, so khớp `ten_su_kien`, `actor_related`; nếu có đại từ như “vụ đó” thì xem Memory để giải nghĩa. File local `data/raw/data_Sukien.json` có 45 sự kiện Showbiz và 40 Giáo dục; actor_related có ở 40/45 và 14/40 record tương ứng. Các trường trong tập chỉ mục còn có highlights; không mặc định mọi sự kiện đủ thông tin nhân vật. Chưa có binding tool hoặc cấu hình Memory đã xác minh để biết workflow đang đọc đúng chỉ mục này.

Prompt phân biệt ba nguồn logic: education/showbiz cho diễn biến và nhân vật; insights cho số liệu, top sự kiện và phản ứng dư luận. Câu hỏi có yếu tố top/thống kê/cảm xúc phải chuyển insights, kể cả đã nhắc tên lĩnh vực.

| `decision` | `type` | Ý nghĩa |
|---|---|---|
| `branch_greeting` | `greeting`, `spam`, `unrelated`, `info`, `clarify` | Chào/từ chối/giới thiệu hoặc hỏi rõ khi không khớp sự kiện |
| `branch_database` | `education`, `showbiz`, `insights` | Diễn biến theo lĩnh vực hoặc số liệu/ý kiến dư luận |

### 3.2 Hợp đồng đầu ra theo prompt

| Trường | Nội dung yêu cầu |
|---|---|
| `reasoning` | Giải thích vì sao chọn nhánh/type |
| `decision`, `type` | Giá trị trong bảng trên |
| `response_data` | Câu trả lời với nhánh greeting; chuỗi rỗng với database |
| `routing_info.database_needed` | `education`, `showbiz`, `insights`, `none` |
| `routing_info.entities` | Danh sách sự kiện/nhân vật đã nhận diện |
| `routing_info.resolved_query` | Câu hỏi viết lại rõ tên sự kiện và điều kiện lọc |

File prompt minh họa các lựa chọn bằng ký hiệu `|`; đó là mô tả tập giá trị, không phải JSON có thể parse nguyên văn. Chưa có code validator/parser định tuyến tương ứng được xác minh trong repo.

### 3.3 Khác phiên bản báo cáo

Báo cáo còn có `branch_firecrawl`, các type `education_drama`, `showbiz_drama`, `system_insight`, `need_live_search` và thông báo Showbiz chưa cập nhật. Prompt Dispatcher local hiện có hai nhánh và bộ type khác, không giữ thông báo thiếu Showbiz đó. Chưa xác định bản nào đang được triển khai; không lấy tình trạng Showbiz trong báo cáo làm tình trạng cloud hiện tại.

## 4. Truy xuất, embedding và rerank

### 4.1 Quy tắc Retrieval Showbiz local

`lllmsshowbiz.txt` yêu cầu dùng nguyên văn câu hỏi cho tool Supabase Vector Store. Nếu không có kết quả, thử thêm một lần bằng tên nhân vật/sự kiện chính. Trả nguyên văn danh sách chunks, không tự trả lời hoặc thêm lời dẫn; sau hai lần vẫn thiếu thì chỉ trả `Không tìm thấy dữ liệu`.

Quy tắc này khác mô tả Retrieval tổng quát trong báo cáo vốn bắt đầu bằng trích từ khóa. Chưa có prompt Retrieval Giáo dục riêng để khẳng định cả hai lĩnh vực dùng cùng thuật toán retry.

### 4.2 Thông số chỉ thấy trong báo cáo

| Bước | Mô tả trong báo cáo | Giới hạn xác minh |
|---|---|---|
| Nạp dữ liệu | JSON Giáo dục/Showbiz từ GitHub → parse/chuyển chuỗi → loader/chunk → Supabase | Chưa có manifest nguồn/lần nạp |
| Embedding | Gemini, vector 3.072 chiều; tên model được ghi nhiều cách như embedding-002/Gemini embedding 2 | Chưa có cấu hình API cloud để chốt model ID |
| Chunking | Báo cáo ghi đổi từ cắt nhỏ sang `chunk_size = 7000` | Chưa rõ đơn vị, overlap, metadata và ranh giới sự kiện |
| Vector search | Cosine, lấy top 10 chunks | Chưa xác minh score threshold, filter hoặc RPC đang dùng |
| Rerank | Cohere lọc top 3, sau đó agent chọn thông tin phù hợp | Chưa có model ID, ngưỡng hoặc cấu hình reranker |
| Generation | Llama 3.3 qua Groq | Chưa có node/model config chatbot được xác minh |

Báo cáo nêu bảng `documents` cho Giáo dục, nhưng tên bảng Showbiz xuất hiện cả `showbiz_documents` và `documents_showbiz`. Có mô tả hàm `public.match_documents` nhận filter/match_count/query_embedding và tính `1 - cosine distance`; không có DDL live đã đối chiếu. Thông tin schema còn mở theo loại 3, không tạo SQL hoặc suy ra quyền truy cập từ đoạn mô tả này.

## 5. Insight Analyst và Final LLM

`insight.txt` bắt buộc dùng tool `Get insight` để đọc `data/insights.json`; lỗi/không có dữ liệu phải báo hệ thống chưa thể tải dữ liệu, không dùng kiến thức bên ngoài thay thế. Với top sự kiện, đọc `top_events_by_comments` của đúng lĩnh vực, trình bày văn xuôi và kèm số `total` hoặc `trash`.

Đường dẫn trong prompt khác vị trí insight local `data/analysis-output/insights.json`. Chưa có tool binding để biết `Get insight` đang đọc nguồn nào. Top insight là thống kê từ summary; không đồng nghĩa top câu hỏi chatbot hoặc lượt xem website.

`llms trả lời.txt` lấy câu hỏi qua biểu thức tham chiếu node `When chat message received` và ngữ cảnh từ `$json.output`. Prompt yêu cầu chỉ trả lời nội dung được hỏi; hỏi sự kiện thì diễn biến chính, hỏi dư luận mới đưa số liệu; tránh Markdown, dùng văn xuôi và ngắt đoạn.

Báo cáo bổ sung giới hạn năm câu/150 từ và ràng buộc chỉ dựa ngữ cảnh, nhưng các giới hạn này không xuất hiện đầy đủ trong file Final LLM local. Website gửi `{message, userId}` qua webhook, không gửi `chatInput`; cần workflow trung gian ánh xạ hai cách nhận input, hiện chưa xác minh được trong export.

## 6. Fallback và mức độ kiểm chứng nguồn

Báo cáo mô tả khi Retrieval trả `Không tìm thấy dữ liệu`, node If chuyển Firecrawl tra web; các câu hỏi thiếu dữ liệu được ghi vào Sheets để nhóm bổ sung kho. Prompt Dispatcher local lại đưa sự kiện không khớp sang clarify, không có nhánh Firecrawl.

Chưa có cấu hình workflow chatbot để kiểm tra fallback này có còn chạy, điều kiện kích hoạt, giới hạn retry hoặc cơ chế dẫn nguồn. Việc crawler tin tức dùng Firecrawl trong export thu thập không chứng minh fallback chatbot đã được nối đúng.

Các quy tắc không bịa/không tự trả lời trong prompt là chỉ dẫn cho mô hình. Chưa có bằng chứng kiểm thử chứng minh loại bỏ hoàn toàn ảo giác, prompt injection, truy xuất sai hoặc sử dụng nguồn không phù hợp. Chưa xác minh câu trả lời luôn mang URL/trích dẫn hay score để người dùng truy ngược.

## 7. Hợp đồng chatbot website và phiên hội thoại

`serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx` gửi POST JSON trực tiếp tới webhook n8n `/webhook/nckh`, không qua backend FastAPI website.

| Thành phần | Hành vi client |
|---|---|
| Request | `message` là input người dùng, `userId` từ cookie |
| Response | Parse JSON; nếu là array lấy phần tử đầu; hiển thị `result.reply` hoặc thông báo không có phản hồi |
| Định danh | `crypto.randomUUID()` nếu chưa có cookie userId; cookie path `/`, thời hạn một năm |
| Lịch sử trên màn hình | State React trong component; không gửi toàn bộ messages trong request |
| Hiển thị | Bot text được render qua ReactMarkdown dù prompt yêu cầu văn xuôi |
| Lỗi mạng/parse | Tìm câu mẫu trong `datamock.js`; không khớp thì hiện lỗi kết nối |

Cookie userId không phải đăng nhập hay phân quyền. Client không cài memory server, không tự lưu lịch sử vào SQLite hoặc `history.json`. Khi reload, state hội thoại trở lại ban đầu; cookie có thể còn nhưng việc n8n nối lại Memory bằng userId chưa được kiểm tra.

Fetch chưa kiểm tra `res.ok`, chưa có timeout/abort hoặc retry mạng trong hàm gửi. Lỗi HTTP có JSON vẫn đi theo nhánh xử lý response; câu mẫu trong catch là fallback giao diện, không phải dữ liệu RAG đã truy xuất thành công. Không coi client chỉ hiện lời đáp là bằng chứng server có căn cứ.

## 8. Lịch sử và LLM trong dashboard

`history.json` tại gốc có 34 record, gồm `user_id`, `question`, `answer`, `source_type`, `the_loai`, `su_kien`, `timestamp`; cả 34 có source_type là database. `QA.json` là danh sách rỗng. Đây là artifact local, chưa chứng minh nhánh database đã truy xuất thành công trong mọi lần chạy hoặc loại trừ khả năng trả lời không có căn cứ. Chưa xác minh node nào ghi các file này, chính sách lưu/xóa hoặc ánh xạ giữa user_id trong lịch sử và userId cookie.

`InteractionView.tsx` tải lịch sử qua GitHub raw, lọc câu hỏi có giá trị, đảo thứ tự để hiển thị và làm mới mỗi 30 giây. Đây là dữ liệu đọc từ remote khi chạy, không mặc định trùng file local tại thời điểm khảo sát.

Dashboard còn có LLM độc lập: `analyzeTopEvents()` nối các câu hỏi thành prompt yêu cầu top 5 sự kiện/chủ đề được hỏi nhiều nhất, loại câu xã giao; gọi `gemini-2.5-flash` qua `@google/genai` ngay trong trình duyệt. Kết quả này không phải thống kê top bình luận trong insight và không dùng truy xuất vector.

Code tải danh sách key từ `/api.txt`, thử lần lượt từng key khi lỗi, rồi hiển thị lỗi nếu hết key. Vì gọi trực tiếp từ browser, key dùng trong request có thể được client đọc; đây là hiện trạng cài đặt, không ghi giá trị key trong tài liệu. `.env.example`/Vite cũng nhắc `GEMINI_API_KEY`, nhưng hàm này lấy key từ file public, không dùng biến đó làm nguồn trực tiếp.

Việc tự phân tích lại dùng điều kiện số dòng lịch sử thay đổi hoặc history trong closure còn rỗng; không có so sánh nội dung/hash chắc chắn. Chưa xác minh giới hạn token, ngân sách gọi, phân trang lịch sử hay độ chính xác của top 5 do LLM suy ra.

## 8b. Agent chatbot local `serving/chat_agent/` (thêm 2026-11-05)

Service FastAPI thay agent n8n cho chatbot website; Messenger sẽ nối qua workflow n8n mới → ngrok (domain tĩnh) → agent. `Chatbot.jsx` đã đổi sang gọi agent (mặc định `http://127.0.0.1:8010/chat`, đổi bằng `VITE_CHAT_API_URL`). Các mục 2–7 ở trên mô tả agent n8n cũ, giữ để tham chiếu.

| Bước | Cài đặt | Gọi mạng |
|---|---|---|
| 1. Luật | Chào / hỏi chức năng / tục tĩu → câu cố định (`intent_rules.py`) | Không |
| 2. Khớp sự kiện | Điểm từ vựng bỏ dấu (unigram + bigram, IDF; tiêu đề/nhân vật ×3) trên `data/raw/showbiz.json` + `education.json` nạp vào RAM; gom tối đa 3 sự kiện điểm gần nhau (một người nhiều vụ) | Không |
| 3. Insight | Hỏi top/thống kê mà không khớp mạnh sự kiện → lát cắt `data/analysis-output/insights.json`; hỏi dư luận → kèm `analyzed` của sự kiện | Không |
| 4. Nối tiếp | "vụ đó", "dư luận thế nào"… → dùng sự kiện gần nhất của phiên (RAM, 3 lượt, hết hạn 30 phút) | Không |
| 5. Trả lời | Đúng 1 lần LLM: Groq `qwen/qwen3.8-27b` (xoay vòng khoá, timeout 6s) → lỗi thì Gemini `gemini-3.5-flash-lite` | 1 |
| 6. Không khớp | Có từ khoá drama → hỏi lại; không → báo ngoài phạm vi | Không |

Không dùng Supabase, embedding, Cohere hay Firecrawl: mỗi sự kiện ở local ngắn (162–3.196 ký tự), báo cáo ghi chunk_size 7000 nên một sự kiện ≈ một chunk; tìm đúng sự kiện rồi đưa nguyên nội dung cho LLM. Lịch sử không còn ghi `history.json`.

Hợp đồng: `POST /chat` nhận `{message, userId | user_id, source?}` (message ≤ 2.000 ký tự), trả `{reply, intent, event_ids, timings_ms}`; `GET /health`. Request gọi thẳng từ 127.0.0.1 không cần khoá; request qua tunnel (có `X-Forwarded-For`) phải gửi header `X-Agent-Key` = `AGENT_API_KEY`. CORS chỉ cho origin web local. Khoá và model cấu hình trong `serving/chat_agent/.env` (mẫu `.env.example`, file thật bị gitignore).

Chạy: `cd serving/chat_agent && .venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8010`. Cài lần đầu: `uv venv .venv --python 3.11 && uv pip install --python .venv/Scripts/python.exe -r requirements.txt`. Test: `.venv/Scripts/python.exe -m pytest tests`.

Kiểm chứng 2026-11-05: 12 test không LLM đạt; 14 câu (phần lớn lấy từ câu hỏi thật trong history) chạy 3 lượt với LLM thật: nhánh có LLM trung vị 0,7–0,9s, chậm nhất 6,6s (Groq treo, đổi khoá); nhánh luật < 5ms. Giới hạn: khớp từ vựng chưa hiểu diễn đạt khác hẳn tên sự kiện; `showbiz_034` (Shark Bình) trong dữ liệu chỉ có câu giữ chỗ nên bot báo thiếu thông tin; Gemini đang hay trả 503.

### 8c. Nối Messenger qua n8n (thêm 2026-11-05, chưa chạy thật với Meta)

Checklist giao việc cho người khác (2026-11-07): [`huong-dan-noi-messenger-n8n.md`](huong-dan-noi-messenger-n8n.md).

Workflow import: [`serving/chat_agent/n8n/messenger-to-local-agent-workflow.json`](../serving/chat_agent/n8n/messenger-to-local-agent-workflow.json) (9 node, không chứa khoá). Webhook path `fb-messenger`, cùng URL cho GET và POST.

- **GET (Meta xác minh):** `hub.mode = subscribe` và `hub.verify_token` khớp chuỗi trong node `Dung verify token?` → trả `hub.challenge`; sai → 403.
- **POST (tin nhắn):** trả 200 ngay cho Meta → `Tach tin nhan` (chỉ giữ tin chữ của người dùng; bỏ echo, delivery/read, ảnh, sticker) → `Bao dang go` (typing_on, lỗi thì bỏ qua) → `Goi agent local` (`POST <ngrok>/chat`, body `{user_id: PSID, message, source: "messenger"}`, timeout 30s) → `Gui tra loi` (Send API v23, `messaging_type: RESPONSE`, cắt 2.000 ký tự). Agent lỗi/tắt → gửi câu "hệ thống đang bận".
- **Credential n8n (nhập lại mỗi lần đổi tài khoản):** `Header Auth` tên `X-Agent-Key`, giá trị = `AGENT_API_KEY` trong `.env` (gắn vào `Goi agent local`); `Query Auth` tên `access_token`, giá trị = Page Access Token (gắn vào `Bao dang go` và `Gui tra loi`). Token không còn nằm trong URL node.
- **Thay placeholder:** `DOI_THANH_VERIFY_TOKEN_CUA_BAN` (chuỗi tự đặt, dán giống hệt ở Meta). URL agent trong workflow đã trỏ sẵn Worker `https://drama-chat-agent.dev01-velrano.workers.dev/chat` (mục 8d; từ 2026-11-06 thay cho ngrok, vì 360 Total Security xoá `ngrok.exe` trên máy dev).
- **Agent:** Worker Cloudflare (mục 8d) chạy khi máy tắt. Nếu dùng lại agent Python local thì phải có tunnel riêng.
- **Meta:** Callback URL = production webhook URL của n8n (`.../webhook/fb-messenger`), Verify token như trên, subscribe field `messages` cho Page. Workflow phải bật (Active).

Kiểm chứng 2026-11-05 (không qua Meta/n8n thật): JSON hợp lệ, cạnh nối đúng tên node; code `Tach tin nhan` chạy bằng Node trên payload mẫu chỉ giữ 1/5 tin (bỏ echo, ảnh, delivery, tin trống); agent nhận request giả lập tunnel: thiếu/sai khoá → 401, đúng khoá → 200 sau 1,6s. Chưa kiểm: import vào n8n, xác minh webhook với Meta, gửi tin thật. Chưa xác thực chữ ký `X-Hub-Signature-256` của Meta ở webhook n8n (agent vẫn được bảo vệ bằng khoá).

### 8d. Bản Cloudflare Worker `serving/chat_agent_worker/` (thêm 2026-11-06, deploy 2026-11-06)

Port TypeScript của agent Python để có URL cố định `*.workers.dev`, không cần tunnel, máy tắt vẫn chạy. Python `serving/chat_agent/` giữ làm chuẩn tham chiếu. Plan: `plans/261106-2024-cloudflare-worker-chat-agent/plan.md`.

- **Khác biệt so với bản Python:** chỉ mục khớp sự kiện (IDF + danh sách sự kiện theo từ, 85 sự kiện, 14.705 từ, 805 KB) dựng sẵn bằng `scripts/build_agent_data.py` (dùng lại code Python) vào `src/generated/agent-data.json`, vì gói Workers miễn phí giới hạn CPU/request. Cập nhật dữ liệu sự kiện/insights → chạy lại `npm run build-data` rồi deploy. Bộ nhớ phiên: từ 2026-11-06 ở Durable Object `SessionStore` (SQLite, mỗi phiên `source:userId` một instance, ghi xong mới trả lời, alarm xoá sau 30 phút không hoạt động); trước đó dùng KV nhưng KV nhất quán sau nên câu hỏi dồn đọc phiên cũ. Xoay khoá LLM chọn ngẫu nhiên thay vì vòng tuần tự.
- **Xác thực:** `Origin` nằm trong `ALLOWED_ORIGINS` (web) gọi không cần khoá; còn lại (n8n) phải có `X-Agent-Key` = secret `AGENT_API_KEY`; không cấu hình khoá thì từ chối. Origin giả mạo được bằng curl, nên người ngoài biết URL vẫn gọi được và tiêu hao hạn mức LLM; chấp nhận ở giai đoạn nghiên cứu.
- **Secret:** `GROQ_API_KEYS`, `GEMINI_API_KEYS`, `AGENT_API_KEY` qua `wrangler secret put`; `.dev.vars` (local, đã ignore) cho `wrangler dev`.
- **Kiểm chứng:** local 2026-11-06: 13 test vitest đạt (nay 14), khớp Python 129/129 câu về sự kiện, điểm, cờ ý định; `wrangler dev` + Groq thật 0,6–1,3s. Sau deploy 2026-11-07 (bản Durable Object): `/health` 200 (85 sự kiện); thiếu khoá → 401; 3 lượt thật qua Internet: Groq 0,62–0,66s phía Worker, tổng 0,9–1,7s từ máy dev, lượt 2 nhận đúng `event_followup` nhờ Durable Object. Chưa kiểm: CPU/giới hạn gói miễn phí dưới tải, nối n8n và Messenger thật.
- **Triển khai (2026-11-06):** tài khoản Cloudflare `dev01.velrano@gmail.com`, Worker `drama-chat-agent`, URL `https://drama-chat-agent.dev01-velrano.workers.dev` (`POST /chat`, `GET /health`), Durable Object `SessionStore` (binding `SESSIONS`), 3 secret lấy từ `serving/chat_agent/.env`. Web đọc URL từ `VITE_CHAT_API_URL` (`serving/web_v2/frontend/.env.local`, mẫu ở `.env.example`). Deploy lại: `cd serving/chat_agent_worker && npx wrangler deploy`.
- **Kiểm chứng sau deploy (2026-11-06):** thiếu khoá → 401; preflight CORS từ `127.0.0.1:5173` → 204; Origin web không khoá → 200; chào → `greeting` 0,45s; "Shark Bình có drama gì?" → `showbiz_034`, LLM ~0,5s, tổng HTTP 0,6–0,9s. Gửi tiếng Việt bằng `curl -d "..."` trên Windows làm hỏng dấu (bị xếp `unrelated`); thử bằng file JSON UTF-8 (`--data-binary @file`).
- **Bộ nhớ phiên KV → Durable Object (2026-11-06):** với KV, câu nối tiếp gửi ngay sau câu trước đọc phiên cũ, khớp sai `showbiz_035`; chờ 70s mới đúng. Sau khi đổi sang DO: hỏi dồn không chờ → `event_followup` → `showbiz_034` (3/3 lượt qua n8n-key, 1/1 qua Origin web). Độ trễ HTTP đo từ máy dev: câu chào cùng người dùng 0,24–0,44s (ngang KV), phiên mới thêm ~0,3s tạo DO; câu có LLM 1,2–1,8s (bản KV 0,6–0,9s). Đọc phiên lỗi thì dùng phiên rỗng (một lần 500 ngay sau deploy đầu, chưa rõ nguyên nhân gốc); ghi lỗi thì tạo lại stub. Gọi không khoá (Origin web) luôn bị gán `source=web`, không chen được vào phiên Messenger.
- **Giới hạn đã biết:** hai tin cùng người dùng gửi song song có thể cùng đọc phiên cũ; người gọi không gửi `user_id` dùng chung phiên `anonymous`; Origin vẫn giả mạo được nên ai biết URL có thể gọi không khoá (chỉ vào phiên `web:*`).
- **Giới hạn:** DO gói miễn phí giới hạn request/ngày (mỗi lượt chat 2 lời gọi DO). Namespace KV `SESSIONS` (id `a9a4a97caca046cdb714e8b06d0b28df`) tạo trước đó nay không dùng.

## 9. Điểm còn thiếu thông tin

1. Bản export workflow chatbot đang dùng và model/config của từng node; prompt local nào đang được triển khai?
2. Tool binding cho data_Sukien/Get insight/Supabase, cách ánh xạ webhook message sang chatInput và cách giữ Memory theo userId.
3. Schema/RPC/quyền Supabase, model embedding, chunking và reranker chính xác; nguồn dữ liệu/lần nạp của mỗi lĩnh vực.
4. Nhánh Firecrawl/Data Loop còn hoạt động không, giới hạn retry và cơ chế kiểm chứng/dẫn nguồn của câu trả lời.
5. Nguồn ghi lịch sử, retention và khả năng tái lập kết quả; các câu trả lời lưu sẵn không thay kiểm thử end-to-end hiện tại.

## 10. Nguồn đối chiếu

- [Dispatcher](./prompts/agent%20đầu%20tien.md), [Insight Analyst](./prompts/insight.txt), [Retrieval Showbiz](./prompts/lllmsshowbiz.txt), [Final LLM](./prompts/llms%20trả%20lời.txt).
- [Bản trích báo cáo cũ](./reports/_report_extract.txt), mục 2.2 và 3.1 — nguồn tham chiếu, chưa xác minh cloud.
- [Chatbot website](../serving/web_v2/frontend/src/components/Chatbot/Chatbot.jsx), [fallback mẫu](../serving/web_v2/frontend/src/components/Chatbot/datamock.js).
- [Dashboard Interaction](../serving/dashboard/src/components/views/InteractionView.tsx), [Vite dashboard](../serving/dashboard/vite.config.ts), [cấu hình mẫu](../serving/dashboard/.env.example).
- [Lịch sử local](../history.json), [QA local](../QA.json), [tạo insight offline](../analysis/single/analyze_insights.py).
- [Chỉ mục sự kiện local](../data/raw/data_Sukien.json).
