# Facebook Skills Suite

> Bộ công cụ thu thập, làm sạch và phân tích dữ liệu Facebook — dành cho người không biết code cũng dùng được.

[![CI Status](https://github.com/Enzosama/FB_Crawl_skills/actions/workflows/ci.yml/badge.svg)](https://github.com/Enzosama/FB_Crawl_skills/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Skills: 5](https://img.shields.io/badge/Skills-5-green.svg)](skills/)

## 📌 Repo này làm gì?

**Ví dụ thực tế**: Bạn thấy một bài post Facebook có nhiều bình luận hay về "Deepseek rẻ thế này dùng cả tháng 10$ chưa hết". Bạn muốn:

1. ✅ Lấy hết tất cả bình luận về chủ đề đó (kể cả trả lời lồng nhau)
2. ✅ Lưu lại gọn gàng vào máy để đọc offline
3. ✅ Tìm ra khách hàng tiềm năng từ những người bình luận
4. ✅ Phân loại họ theo nhóm 

**Repo này giúp bạn làm 4 việc đó** tự động, chỉ với vài lệnh đơn giản.

---

## 🚀 Bắt đầu nhanh (5 phút)

### Cách 1: Cài qua `npx skills` (khuyến nghị, 30 giây)

Nếu bạn dùng AI agent hỗ trợ Skills (Claude Code, Hermes Agent, Cursor, Aider...), cách nhanh nhất là:

```bash
# Cài TẤT CẢ 5 skills vào agent
npx skills add github:Enzosama/FB_Crawl_skills -g -y

# Hoặc chỉ cài 1 skill cụ thể
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y
npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y
```

Sau khi cài, mở lại AI agent — nó sẽ **tự động biết** cách dùng từng skill khi bạn hỏi.

Nếu bạn fork repo này lên GitHub cá nhân, thay `username` bằng tên GitHub của bạn. Nếu dùng local:

```bash
# Cài từ thư mục local
npx skills add /home/enzo/Documents/Facebook -g -y

# Hoặc chỉ 1 skill
npx skills add /home/enzo/Documents/Facebook --skill facebook-crawl -g -y
```

### Cách 2: Chạy thủ công (nếu không dùng AI agent)

### Bước 1: Mở trình duyệt Facebook

Mở Terminal/Command Prompt và chạy:

```bash
bash scripts/01_open_chromium.sh
```

Trình duyệt Chromium sẽ mở. Bạn **đăng nhập Facebook bằng tay** (dùng tài khoản phụ, không phải tài khoản chính — để an toàn).

### Bước 2: Lấy bình luận từ một bài post

Mở bài post bạn muốn trong trình duyệt, copy URL rồi chạy:

```bash
# Lấy tất cả bình luận (kể cả trả lời lồng nhau) từ một post
python3 scripts/fb_cli.py crawl deep "https://www.facebook.com/share/p/1ABCxyz/" --target 100
```

Kết quả sẽ được lưu vào `data/posts/<tên_post>/raw.json`.

### Bước 3: Làm sạch dữ liệu

```bash
# Tự động lọc bỏ trùng lặp, spam, thông tin cá nhân
python3 scripts/04_clean_data.py data/posts/<tên_post>/raw.json
```

Kết quả: `clean.jsonl`, `quarantine.jsonl` (spam), `stats.json`.

### Bước 4: Xem dữ liệu

```bash
# Xem tất cả các post đã crawl
python3 scripts/fb_cli.py list
```

Hoặc mở file `data/posts/<tên_post>/compact.json` bằng trình soạn thảo để xem.

### Bước 5: Nâng cao — page timeline, profile, bulk, export

**Crawl timeline fanpage** (ví dụ `/Nintendo`):
```bash
python3 scripts/fb_cli.py crawl timeline "https://www.facebook.com/<page-slug>" 30
# → data/posts/<page-slug>/raw.json (posts kèm reactions/comments/shares + flag pinned)
```

**Crawl trang cá nhân** (⚠️ chỉ dùng cho profile public, có authorization):
```bash
python3 scripts/fb_cli.py crawl profile "https://www.facebook.com/<username>" --with-about --with-photos
# 3 giai đoạn: About (bio/work/education) + Posts (timeline) + Photos
```

**Bulk crawl từ danh sách URL** (50+ posts cùng lúc):
```bash
# urls.txt: 1 URL / dòng
python3 scripts/fb_cli.py bulk urls.txt --count 50
# → data/tests/<n>posts_<ts>/{full, compact, jsonl, manifest}.json
```

**Export sang CSV / Parquet cho analytics**:
```bash
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl csv
python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl parquet
# Flat schema 15 cột (record_id, post_url, author, text, time_iso, n_images, ...)
```

**Audit các lần chạy trước**:
```bash
python3 scripts/fb_cli.py audit             # tổng quan tất cả lần crawl
python3 scripts/fb_cli.py audit --since 7d  # 7 ngày gần nhất
```

**Xong!** Bạn đã có dữ liệu sạch sẽ để đọc hoặc phân tích tiếp.

---

## ⚡ Cài nhanh bằng 1 lệnh (`npx skills`)

Nếu bạn dùng AI agent hỗ trợ Skills (Claude Code, Hermes Agent, Cursor, Aider...), copy 1 lệnh bất kỳ dưới đây:

```bash
# Cài TẤT CẢ 5 skills toàn cục (khuyến nghị cho người mới)
npx skills add Enzosama/FB_Crawl_skills -g -y

# Cài từng skill riêng lẻ
npx skills add Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y
npx skills add Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y

# Gỡ skill
npx skills remove facebook-crawl

# Cập nhật lên bản mới
npx skills update
```

Mở lại AI agent sau khi cài — nó sẽ **tự động biết** cách dùng từng skill khi bạn hỏi về Facebook data.

---

## 🎯 Các tính năng chính

### 1. Lấy bình luận (Crawl)

| Lệnh | Mục đích |
|------|----------|
| `python3 scripts/fb_cli.py crawl post <URL>` | Lấy ~30 bình luận đầu |
| `python3 scripts/fb_cli.py crawl deep <URL> --target N` | Lấy đến N bình luận (tối đa ~60-100) |
| `python3 scripts/fb_cli.py crawl group <URL> [N]` | Lấy N bài post trong một group |
| `python3 scripts/fb_cli.py crawl page <URL> [N]` | Lấy N bài post từ fanpage |

### 2. Làm sạch dữ liệu (Clean)

| Tác vụ | Lệnh |
|--------|------|
| Lọc trùng lặp | Tự động trong `04_clean_data.py` |
| Lọc spam (link rác, giới thiệu nhóm) | Tự động |
| Ẩn email, số điện thoại | Tự động |
| Chuẩn hóa Unicode (Tiếng Việt) | Tự động |

### 3. Phân tích (AI Skills)

Nếu bạn dùng AI agent (như Hermes), nó sẽ tự động đọc các file trong `skills/` để biết cách phân tích:

- `skills/facebook-customer-segment/` — Phân nhóm khách hàng (VIP, mới, lâu năm)
- `skills/facebook-info-enrichment/` — Ghép profile khách hàng từ nhiều nguồn
- `skills/facebook-anti-bot/` — Mẹo tránh bị Facebook phát hiện (chỉ dành cho dev)

### 4. Cài từng skill riêng lẻ

Bạn không cần cài hết 5 skills. Mỗi skill độc lập:

| Skill | Khi nào cần | Lệnh cài |
|-------|-------------|----------|
| `facebook-crawl` | Bạn muốn lấy dữ liệu mới từ FB | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-crawl -g -y` |
| `facebook-data-clean` | Bạn có data thô cần làm sạch | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-data-clean -g -y` |
| `facebook-customer-segment` | Bạn muốn phân nhóm khách hàng | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-customer-segment -g -y` |
| `facebook-info-enrichment` | Bạn muốn ghép profile từ nhiều nguồn | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-info-enrichment -g -y` |
| `facebook-anti-bot` | Bạn là dev, muốn tránh bị FB phát hiện | `npx skills add github:Enzosama/FB_Crawl_skills --skill facebook-anti-bot -g -y` |

**Gỡ skill đã cài**:

```bash
npx skills remove facebook-crawl
# hoặc gỡ nhiều cái cùng lúc
npx skills remove facebook-crawl facebook-data-clean
```

**Cập nhật skills lên phiên bản mới**:

```bash
npx skills update
```

**Xem skills đã cài**:

```bash
npx skills list
```

---

## 📂 Cấu trúc thư mục (đơn giản)

```
Facebook/
├── data/
│   ├── posts/                          ← Dữ liệu của từng post
│   │   ├── share_p_1AxneTWsfv/         ← Mỗi post = 1 folder
│   │   │   ├── raw.json                ← Dữ liệu thô vừa lấy
│   │   │   ├── clean.jsonl             ← Dữ liệu sạch
│   │   │   ├── compact.json            ← File gọn để đọc/AI
│   │   │   └── stats.json              ← Thống kê
│   │   └── ...
│   ├── tests/                          ← Kết quả test tự động
│   └── README.md                       ← Hướng dẫn cấu trúc data
├── scripts/                            ← Các lệnh chính
│   ├── 01_open_chromium.sh             ← Mở trình duyệt
│   ├── 04_clean_data.py                ← Làm sạch dữ liệu
│   ├── 05_auto_scrape_cdp.py           ← Lấy bình luận tự động
│   └── fb_cli.py                       ← Lệnh gọn cho người dùng
├── skills/                             ← Hướng dẫn cho AI agent
│   ├── facebook-crawl/                 ← Cách lấy data
│   ├── facebook-data-clean/            ← Cách làm sạch
│   ├── facebook-customer-segment/      ← Cách phân nhóm KH
│   ├── facebook-info-enrichment/       ← Cách ghép profile
│   └── facebook-anti-bot/              ← Cách tránh bị FB phát hiện
└── README.md                           ← File bạn đang đọc
```

**Giải thích đơn giản**:

- `data/posts/<tên>/` — Mỗi post Facebook = 1 folder. Trong folder có các file dữ liệu khác nhau.
- `scripts/` — Các lệnh để chạy. Thường chỉ cần `01_open_chromium.sh` + `fb_cli.py crawl` + `04_clean_data.py`.
- `skills/` — Cho AI agent đọc. Bạn không cần đọc trực tiếp.

---

## 📚 Hướng dẫn chi tiết theo tình huống

### Tình huống 1: Tôi muốn lấy bình luận từ 1 post

```bash
# 1. Mở trình duyệt
bash scripts/01_open_chromium.sh

# 2. Trong trình duyệt, mở bài post bạn muốn, copy URL

# 3. Quay lại Terminal, chạy:
python3 scripts/fb_cli.py crawl deep "URL_CỦA_BẠN" --target 100

# 4. Đợi 1-2 phút. Kết quả ở data/posts/<tên_post>/raw.json

# 5. Làm sạch:
python3 scripts/04_clean_data.py data/posts/<tên_post>/raw.json

# 6. Mở file compact.json để xem:
cat data/posts/<tên_post>/compact.json
```

### Tình huống 2: Tôi muốn lấy bài post từ 1 group Facebook

```bash
# Lấy 20 bài post mới nhất từ group
python3 scripts/fb_cli.py crawl group "https://www.facebook.com/groups/your-group" 20
```

Kết quả lưu vào `data/posts/groups_<group_id>/`.

### Tình huống 3: Tôi muốn gửi dữ liệu cho AI phân tích

Mở file `data/posts/<tên_post>/compact.json` (khoảng 3.000 tokens cho 60 bình luận) và gửi cho AI kèm câu hỏi:

```
Đây là bình luận từ post Facebook về [chủ đề]. Hãy:
1. Tóm tắt các ý kiến chính
2. Phân loại sentiment (tích cực/tiêu cực)
3. Tìm các khách hàng tiềm năng đang quan tâm
```

### Tình huống 4: Tôi muốn biết có bao nhiêu dữ liệu

```bash
python3 scripts/fb_cli.py list
```

Output:
```
=== Posts (6) ===
  share_p_1AxneTWsfv             60 comments, 6 files
  share_p_1DLJccgZNY              5 comments, 3 files
  groups_852586990732832_...     60 comments, 12 files
```

---

## ⚠️ Lưu ý quan trọng

### 🛡️ An toàn tài khoản

1. **LUÔN dùng tài khoản phụ**, không dùng tài khoản chính của bạn
2. Không crawl quá nhiều (tối đa vài chục post mỗi ngày)
3. Đợi vài giây giữa các lần lấy dữ liệu
4. Nếu Facebook yêu cầu xác minh (captcha, OTP), đăng nhập lại bằng tay

### ⚖️ Tuân thủ pháp luật

1. **Không crawl dữ liệu riêng tư** (bạn bè, người lạ, profile khóa)
2. **Không bán dữ liệu cá nhân** — vi phạm luật bảo vệ dữ liệu (PDPA Việt Nam, GDPR EU)
3. **Không spam** hoặc dùng dữ liệu để quảng cáo trái phép
4. **Tôn trọng quyền riêng tư**: nếu dùng dữ liệu người khác, hãy ẩn danh họ

### 🔧 Kỹ thuật

1. Tool hoạt động với **trình duyệt Chromium** đã cài sẵn
2. Cần **Python 3.10+**
3. Trình duyệt phải đăng nhập Facebook rồi mới chạy lệnh
4. Nếu gặp lỗi, xem file `data/posts/<tên>/stats.json` để biết chi tiết

---

## 🆘 Xử lý lỗi thường gặp

### "Không tìm thấy tab Facebook"

**Nguyên nhân**: Trình duyệt chưa mở hoặc chưa đăng nhập.
**Cách fix**: Chạy `bash scripts/01_open_chromium.sh` rồi đăng nhập Facebook.

### "Got 0 comments"

**Nguyên nhân**: Post không có bình luận công khai, hoặc Facebook đã đổi giao diện.
**Cách fix**: Thử với post khác. Nếu vẫn lỗi, báo cho dev.

### "Permission denied"

**Nguyên nhân**: Trình duyệt snap Chromium không có quyền ghi.
**Cách fix**: Không cần fix, tool đã tự dùng đường dẫn `/home/enzo/snap/chromium/common/`.

### File "compact.json" quá lớn để gửi AI

**Nguyên nhân**: Post có hơn 100 bình luận.
**Cách fix**: Chia nhỏ file, hoặc chỉ gửi 30-50 bình luận đầu (bỏ replies).

---

## 📖 Thuật ngữ

| Từ | Nghĩa |
|----|-------|
| **Crawl** | Thu thập dữ liệu từ trang web tự động |
| **Scrape** | Tương tự crawl |
| **Post** | Bài viết trên Facebook |
| **Comment** | Bình luận |
| **Reply** | Trả lời cho một bình luận |
| **Group** | Nhóm Facebook |
| **Page** | Trang/Fanpage |
| **CDP** | Chrome DevTools Protocol — cách tool giao tiếp với trình duyệt |
| **JSON** | Định dạng file dữ liệu (giống bảng tính) |
| **JSONL** | Mỗi dòng 1 bản ghi JSON |

---

## 🛠️ Cho người phát triển (developers)

Nếu bạn biết code và muốn mở rộng:

```bash
# Test nhanh
python3 scripts/05_auto_scrape_cdp.py --help

# Debug
python3 scripts/fb_cli.py status  # Check browser connection

# Xem cấu trúc data
python3 scripts/_data_paths.py  # Test path helpers
```

Xem các file trong `skills/` để hiểu chi tiết cách tool hoạt động.

---

## 📜 Giấy phép

MIT License — Tự do sử dụng, sửa đổi, phân phối. Miễn là tuân thủ luật pháp và ToS của Facebook.

---

## 🤝 Đóng góp

Có ý tưởng cải tiến? Tạo issue hoặc pull request. Đặc biệt cần:

- Hỗ trợ thêm ngôn ngữ (đang có sẵn Tiếng Việt + Tiếng Anh)
- Tối ưu tốc độ crawl
- Thêm tính năng phân tích

Xem `README_ENG.md` để biết thêm chi tiết bằng tiếng Anh.