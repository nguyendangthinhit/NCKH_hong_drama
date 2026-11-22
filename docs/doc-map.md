# DOC MAP

Bảng cho biết loại document nào nằm ở file nào. Agent tìm document qua bảng này, không tìm theo tên file.

## Nguyên tắc viết (user chốt 2026-10-29)

- **Document chỉ mô tả những gì đang có trong dự án** (code, dữ liệu, cấu hình thật). Không viết phần tương lai, không viết kế hoạch chưa cụ thể.
- Lý do: nhiều hạng mục mới mới ở mức ý tưởng, chưa có plan chi tiết. Document hiện tại để biết dự án cũ đã làm được gì và làm ra sao.
- Mục "việc làm sau" (bảng bên dưới) ghi lại hạng mục nào sẽ làm. **Khi bắt đầu một hạng mục, agent yêu cầu user viết lại (hoặc cùng viết lại) document bị ảnh hưởng**, vì lúc đó mới có plan cụ thể.
- Chỗ nào chưa có thông tin: ghi rõ "chưa có thông tin", không đoán.
- Nguồn viết document: đọc codebase, dữ liệu/cấu hình và tài liệu đã có, kết hợp thông tin user xác nhận. `drama-intelligence-du-an.md` là nguồn ý tưởng phát triển, không dùng làm căn cứ mô tả cài đặt hiện tại (user nhắc lại 2026-10-29).
- Giới hạn mỗi file: 800 dòng; vượt thì tách file con, file chính tham chiếu.

Xác nhận danh sách: user, 2026-10-29. Bộ kit gốc có 11 loại; dự án data/AI dùng 16 loại dưới đây, mỗi loại một file riêng. Triển khai hạ tầng và Hướng dẫn sử dụng hoãn.

## 16 loại document

| # | Loại | File | Trạng thái |
|---|---|---|---|
| 1 | Kiến trúc tổng thể (2 lớp: tổng thể + cụ thể) | `docs/kien-truc-tong-the.md` | Viết lại 2026-11-19; user duyệt 2026-11-20 |
| 2 | Data pipeline | `docs/data-pipeline.md` | Bản nháp, chờ user duyệt |
| 3 | Database và dữ liệu (theo từng kho) | `docs/database-va-du-lieu.md` | Bản nháp, chờ user duyệt (thiếu schema Supabase) |
| 4 | Thu thập dữ liệu | `docs/thu-thap-du-lieu.md` | Bản nháp, chờ user duyệt |
| 5 | Gán nhãn và tập dữ liệu | `docs/gan-nhan-va-tap-du-lieu.md` | User đã kiểm tra, 2026-10-29 |
| 6 | Mô hình ML và phân tích | `docs/mo-hinh-ml-va-phan-tich.md` | User đã duyệt, 2026-10-29 |
| 7 | LLM / Agent / RAG | `docs/llm-agent-rag.md` | User duyệt 2026-11-20. Đã cập nhật 2026-11-19: chatbot chuyển từ n8n sang agent code (`serving/chat_agent/`, Worker); phần agent n8n chỉ còn là lịch sử |
| 8 | Đánh giá và benchmark | `docs/danh-gia-va-benchmark.md` | User đã chốt, 2026-10-29 |
| 9 | Hợp đồng tích hợp | `docs/hop-dong-tich-hop.md` | Bản nháp, chờ user duyệt |
| 10 | Backend / serving | `docs/backend-serving.md` | User đã duyệt, 2026-10-29 |
| 11 | Thuộc tính chất lượng | `docs/thuoc-tinh-chat-luong.md` | Bản nháp, chờ user duyệt |
| 12 | Bảo mật, dữ liệu, pháp lý và đạo đức | `docs/bao-mat-va-phap-ly.md` | Bản nháp, chờ user duyệt |
| 13 | Testing và nghiệm thu | `docs/testing-va-nghiem-thu.md` | Bản nháp, chờ user duyệt |
| 14 | Maintenance | `docs/maintenance.md` | Bản nháp, chờ user duyệt |
| 15 | User workflow và chức năng | `docs/user-workflow-va-chuc-nang.md` | Bản nháp, chờ user duyệt |
| 16 | Tái lập thí nghiệm | `docs/tai-lap-thi-nghiem.md` | Bản nháp, chờ user duyệt |
| – | Hướng dẫn đọc code từng thư mục (phụ trợ, ngoài 16 loại) | `docs/huong-dan-doc-code-tung-thu-muc.md` | Bản nháp 2026-11-19; user duyệt 2026-11-20 |
| – | Triển khai và hạ tầng | – | Chưa có (hoãn) |
| – | Hướng dẫn sử dụng | `docs/huong-dan-team-cao-va-phan-tich.md` (chỉ phần cào Facebook theo bảng + phân tích `analysis_new`, kèm prompt cho trợ lý AI) | Bản nháp 2026-11-22, chờ user duyệt; phần web/dashboard chưa có |
| – | Cào Facebook từ Google Sheets (`orchestration/`) | `docs/facebook-sheet-wrapper.md` | Commit `06253ce` 2026-11-22; công cụ song song với `ingestion/` (bảng .xlsx) |

## Document cũ (giữ nguyên, không sửa, không dời)

| File | Nhãn rà soát | Ghi chú |
|---|---|---|
| `docs/reports/báo cáo nghiệm thu.docx` | Cũ | Báo cáo NCKH nộp trường. Nguồn tham chiếu; lệch code ở backend (Apps Script) và dữ liệu web. |
| `docs/reports/thông tin về dự án.docx` | Cũ | Ghi backend Node.js/Express + MongoDB, code thật là FastAPI + SQLite. |
| `docs/reports/_report_extract.txt` | – | Bản trích văn bản của báo cáo (24/05). |
| `README.md` | Cũ | Ghi `serving/code_web/` (thật là `serving/web_v2`) và `ingestion/cao_fb/` (đã xóa khỏi working tree). |
| `sampling_labeling/data_sampling_process.md` | Cũ | Đường dẫn script và dữ liệu lệch. |
| `sampling_labeling/data_labels/labeling-guide.md` | Cũ | Cấu trúc thư mục và script mô tả chưa tồn tại; phần bộ nhãn vẫn dùng được. |
| `ml/gnn/README.md` | Chưa đối chiếu hết | |
| `serving/dashboard/README.md`, `serving/web_v2/README.md`, `serving/web_v2/backend/README.md`, `serving/web_v2/frontend/README.md` | Đạt (hướng dẫn chạy) | |
| `docs/prompts/*` | Không phải document | Prompt của agent n8n cũ (không còn dùng từ 2026-11-05). |
| `drama-intelligence-du-an.md` (thư mục gốc) | Nguồn ý tưởng | Đánh giá và lộ trình cải tiến, mới ở mức ý tưởng. Nguồn cho bảng "việc làm sau". |

Đã xóa theo yêu cầu user: `docs/reports/thinh sưa.docx`.

## Việc làm sau (chưa có plan cụ thể, chưa viết vào document)

Nguồn: `drama-intelligence-du-an.md`. Khi user bắt đầu một giai đoạn: tạo plan cụ thể trước, rồi **yêu cầu user viết lại các document ở cột phải** cho khớp.

| Giai đoạn | Nội dung (tóm tắt) | Document cần viết lại khi bắt đầu |
|---|---|---|
| GĐ1 | Tăng sự kiện (85 → 200+), thêm YouTube/TikTok, schema chung đa nền tảng, gán nhãn gold, bảng `jobs` tối thiểu + worker. **Tiến độ (user báo 2026-11-19):** gán nhãn gold 10k ✅ xong, team đã verify; sự kiện hiện 140 (lưu trên Drive, chưa kéo về repo); YouTube đã có dữ liệu lấy về (chi tiết tăng gì, bao nhiêu: user sẽ làm rõ 2026-11-20); TikTok, schema chung, `jobs`+worker chưa làm | 3, 4, 5, 8, 12 |
| GĐ2 | Fine-tune PhoBERT, BERTopic, suy luận ONNX | 5, 6, 8, 11, 14, 16 |
| GĐ3 | Dữ liệu đồ thị Neo4j, PageRank/Louvain (user: chưa chắc làm sớm) | 3, 6, 9, 13 |
| GĐ4 | Quét sự kiện mới theo yêu cầu, micro-batch, cảnh báo Telegram | 1, 2, 4, 15 |
| GĐ5 | Drama Score | 6, 8, 13, 15 |
| GĐ6 | Phân tích qua link dán (on-demand), tài khoản clone | 1, 7, 9, 10, 12, 13, 15 |
| GĐ7 | Kiến trúc phân tán (Spark lên cụm, RAPIDS), thí nghiệm scaling | 1, 2, 8, 16 |
| GĐ8 | n8n chỉ lo trigger, hàng đợi `jobs`, cờ `mode: single\|distributed` | 1, 3, 9, 10, 14 |
| Ngoài GĐ | Làm lại luồng cào Facebook (luồng hiện tại ở `FB_Crawl_skills/`) | 4, 2 |
| Ngoài GĐ | Chức năng mới nhóm E–H (timeline, KOL, bot detection, fact vs opinion...) | 15 |
