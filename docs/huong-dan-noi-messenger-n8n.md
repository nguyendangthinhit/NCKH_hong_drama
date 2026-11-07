# Việc giao người khác: nối Messenger với agent (n8n + Meta)

Ngày ghi: 2026-11-07. Agent đã chạy trên Cloudflare, chỉ còn phần n8n và Meta. Mô tả kỹ thuật: `llm-agent-rag.md` mục 8c, 8d.

## Đã xong (không cần làm lại)
- Agent: `https://drama-chat-agent.dev01-velrano.workers.dev` (tài khoản Cloudflare dev01). `GET /health` trả 200; `POST /chat` cần header `X-Agent-Key`.
- Web chatbot đã trỏ vào agent (`serving/web_v2/frontend/.env.local`).
- File workflow n8n đã sửa sẵn: `serving/chat_agent/n8n/messenger-to-local-agent-workflow.json`.

## Người làm cần có
1. Tài khoản n8n cloud: `https://dacn00.app.n8n.cloud`.
2. Quyền admin app Meta + Facebook Page dùng cho bot (Meta for Developers).
3. Giá trị `AGENT_API_KEY` trong `serving/chat_agent/.env` (hỏi chủ dự án; **không dán vào chat/commit**).

## Các bước
1. **Import workflow:** n8n → Workflows → Import from file → chọn file JSON ở trên.
2. **Sửa 2 placeholder trong workflow:**
   - Node `Goi agent local`, ô URL: thay `DOI_THANH_URL_WORKER.workers.dev` thành `drama-chat-agent.dev01-velrano.workers.dev` (giữ `https://` và đuôi `/chat`).
   - Node `Dung verify token?`: thay `DOI_THANH_VERIFY_TOKEN_CUA_BAN` bằng một chuỗi tự đặt (ghi lại, dùng ở bước 5).
3. **Tạo 2 credential rồi gắn vào node** (n8n → Credentials → Create):
   - **Header Auth**: Name = `X-Agent-Key`, Value = `AGENT_API_KEY`. Gắn vào node `Goi agent local` (Authentication: Generic → Header Auth).
   - **Query Auth**: Name = `access_token`, Value = Page Access Token (Meta → app → Messenger → API Settings → Generate token cho Page). Gắn vào node `Bao dang go` và `Gui tra loi`.
4. **Bật Active** cho workflow (công tắc góc trên phải).
5. **Cấu hình Meta** (Webhooks → Messenger → Edit callback URL):
   - Callback URL: `https://dacn00.app.n8n.cloud/webhook/fb-messenger` (phải là `/webhook/`, **không** phải `/webhook-test/`).
   - Verify token: đúng chuỗi ở bước 2. Bấm Verify and save.
   - Subscribe field `messages` cho Page.
6. **Nhắn thử** vào Page. Bot trả lời trong vài giây.

## Kiểm tra từng bước
- Xác minh webhook (không cần Meta): mở trình duyệt `https://dacn00.app.n8n.cloud/webhook/fb-messenger?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=123`. Thấy `123` là đúng; 403 là sai token; 404 là workflow chưa Active.
- Agent sống: mở `https://drama-chat-agent.dev01-velrano.workers.dev/health`, thấy `{"status":"ok","events":85}`.
- Lỗi khi nhắn thử: n8n → Executions của workflow → node đỏ. Agent trả 401 = sai giá trị `X-Agent-Key`; bot trả "hệ thống đang bận" = agent lỗi hoặc hết hạn mức LLM.

## Lưu ý
- Workflow `NCKH` cũ cũng dùng webhook `.../nckh`; Meta chỉ gửi vào một Callback URL, nên sau khi chuyển thì workflow cũ không còn nhận tin Messenger.
- n8n bản free đổi tài khoản mỗi 14 ngày: khi đó import lại workflow, nhập lại 2 credential, cập nhật Callback URL ở Meta (agent không phải sửa).
- Khi Page ở chế độ Development, chỉ admin/tester của app nhắn được; muốn người ngoài nhắn phải đưa app lên Live (cần Meta duyệt quyền `pages_messaging`).
- Báo lại cho chủ dự án: bước nào lỗi + ảnh/thông báo lỗi. Chưa chạy thử thật với Meta nên có thể còn lỗi cấu hình.
