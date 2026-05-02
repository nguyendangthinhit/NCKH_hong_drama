"""
py .\analyze_education_async.py ./cleaned_data_input ./analyzed_dataa
Patch logging cho analyze_education_async.py
--------------------------------------------
Thêm vào cuối file analyze_education_async.py, thay thế hàm run() cũ.

Ghi log ra: <output_dir>/run_log.jsonl
Mỗi dòng = 1 session chạy, format:
{
  "session_id": "20260419_143000",
  "started_at": "2026-04-19 14:30:00",
  "finished_at": "2026-04-19 15:20:00",
  "elapsed_seconds": 3000,
  "total_files": 20,
  "processed": 17,
  "skipped": 0,
  "remaining": 3,
  "stop_reason": "quota_exhausted" | "completed" | "interrupted",
  "files_done": ["education_001", ...],
  "files_remaining": ["education_018", ...]
}
    python3 analyze_education_async.py ./input_clean_data ./analyzed_data
Xem log:
    python3 show_log.py <output_dir>
"""

import json
import os
import sys
import re
import time
import asyncio
import aiohttp
from collections import defaultdict
from datetime import datetime
from collections import Counter

# ──────────────────────────────────────────────
# Điền API keys từ các account KHÁC NHAU
# ──────────────────────────────────────────────
GROQ_ACCOUNTS = [
    
]


GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_URL        = "https://api.groq.com/openai/v1/chat/completions"
BATCH_SIZE      = 10
MAX_CONCURRENT  = 5

STANCE_LABELS   = ["tích cực", "tiêu cực", "trung lập", "ý kiến riêng"]
ALL_LABELS      = STANCE_LABELS + ["rác"]


# ──────────────────────────────────────────────
# Account Manager
# ──────────────────────────────────────────────

class AccountManager:
    def __init__(self, keys):
        self.keys      = [k for k in keys if not k.startswith("YOUR_")]
        self.current   = 0
        self.exhausted = set()
        self._lock     = asyncio.Lock()

    def get_key(self):
        return self.keys[self.current] if self.current < len(self.keys) else None

    async def rotate(self, reason=""):
        async with self._lock:
            self.exhausted.add(self.current)
            for i in range(len(self.keys)):
                if i not in self.exhausted:
                    self.current = i
                    print(f"\n  🔄 Rotate sang account #{i+1} ({reason})")
                    return True
            print(f"\n  ❌ Tất cả account đã hết quota!")
            return False

    def all_exhausted(self):
        return len(self.exhausted) >= len(self.keys)


account_mgr: AccountManager = None


# ──────────────────────────────────────────────
# Logger
# ──────────────────────────────────────────────

class RunLogger:
    def __init__(self, output_dir):
        self.log_path   = os.path.join(output_dir, "run_log.jsonl")
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.started_at = datetime.now()
        self.files_done = []
        self.all_files  = []

    def set_all_files(self, files):
        self.all_files = files

    def mark_done(self, id_content, elapsed):
        self.files_done.append({
            "id_content": id_content,
            "elapsed_s":  round(elapsed, 1)
        })

    def save(self, stop_reason="completed"):
        finished_at    = datetime.now()
        elapsed        = (finished_at - self.started_at).total_seconds()
        done_ids       = [f["id_content"] for f in self.files_done]
        remaining_ids  = [f for f in self.all_files if f not in done_ids]

        entry = {
            "session_id":       self.session_id,
            "started_at":       self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at":      finished_at.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds":  round(elapsed, 1),
            "elapsed_human":    _fmt_duration(elapsed),
            "total_files":      len(self.all_files),
            "processed":        len(self.files_done),
            "remaining":        len(remaining_ids),
            "stop_reason":      stop_reason,
            "files_done":       self.files_done,
            "files_remaining":  remaining_ids,
            "avg_per_file_s":   round(elapsed / len(self.files_done), 1) if self.files_done else 0,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"\n💾 Log đã lưu → {self.log_path}")
        return entry
def looks_like_name_word(w):
    """Từ viết hoa chữ đầu, còn lại thường, không có số — Unicode aware."""
    if not w:
        return False
    if not w[0].isupper():
        return False
    if len(w) > 1 and not w[1:].islower():
        return False
    if any(c.isdigit() for c in w):
        return False
    return True

def looks_like_name(s):
    """2-5 từ liên tiếp đều là name_word → nhiều khả năng là tên người."""
    words = s.strip().split()
    if len(words) < 2 or len(words) > 5:
        return False
    return all(looks_like_name_word(w) for w in words)
def is_trash_rule(text: str) -> bool:
    raw = text.strip()
    t   = raw.lower()
    
    # # TEMP DEBUG
    # if "thiếu tôn chỉ" in t:
    #     print(f"DEBUG HIT: '{text[:50]}'")
    #     import traceback
    #     traceback.print_stack()
    

    # 1. Quá ngắn hoặc rỗng
    if len(t.replace(" ", "")) < 4:
        return True

    # 2. Không có chữ cái thật (chỉ emoji/ký tự đặc biệt)
    if not re.search(r'[a-zàáâãèéêìíòóôõùúăđĩũơ]', t):
        return True

    # 3. Vô nghĩa: lặp ký tự (hhh, kkk, haha, lol,...)
    if re.fullmatch(r'(h+|k+|ok+e*|lol+|haha+|he+|hi+|uh+|ah+|ew+|hehe+)', t):
        return True

    # 4. Chứa URL bất kỳ
    if re.search(r'https?://', t):
        return True

        # Rule 5 - bỏ "trường" ra khỏi pattern đơn, chỉ giữ các từ đặc thù hơn
    if re.search(r'\b(thpt|thcs|hocmai|fanpage)\b', t):
        return True

    # "trường" chỉ là rác khi đi kèm tên riêng (THPT, THCS, tên trường cụ thể)
    if re.search(r'\b(trường thpt|trường thcs|trường đh|trường đại học)\b', t):
        return True

    # ".vn" chỉ bắt khi có dấu chấm thật (domain)
    if re.search(r'[a-z]+\.vn\b', t):
        return True

    # 6. Tag bằng @ + ít chữ
    if "@" in t and len(raw.split()) <= 4:
        return True

    # 7. Spam / kêu share
    spam_keywords = ["lụm về share", "lụm", "share", "quảng cáo",
                     "inbox mình", "inbox em", "tag ", "bit.ly"]
    if any(k in t for k in spam_keywords):
        return True

    # 8. Helper: kiểm tra từ có phải thành phần tên người không


    words = raw.split()

    # 9. Chỉ có tên người thuần túy (không có gì thêm)
    if looks_like_name(raw):
        return True

    # 10. Bắt đầu bằng tên người (2-4 từ) + phần còn lại ngắn/vô nghĩa
    for name_len in range(4, 1, -1):  # thử từ 4 từ xuống 2 từ
        if len(words) >= name_len and looks_like_name(" ".join(words[:name_len])):
            remaining = " ".join(words[name_len:]).strip()
            if not remaining:
                return True
            if len(remaining) < 30:
                return True
            if re.fullmatch(r'[=:;<>()\-\/\\🫨😂😭😅😆🥲👍👎❤️🔥💀🙄😑😐🤣\s]+', remaining):
                return True
            break  # tìm được tên rồi, không thử tiếp

    return False

def _fmt_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


# ──────────────────────────────────────────────
# Async API call
# ──────────────────────────────────────────────

async def call_groq(session, prompt, semaphore, retries=3):
    async with semaphore:
        for attempt in range(retries):
            key = account_mgr.get_key()
            if not key:
                return None

            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json"
            }
            body = {
                "model":       GROQ_MODEL,
                "messages":    [{"role": "user", "content": prompt}],
                "max_tokens":  8192,
                "temperature": 0.1
            }

            try:
                async with session.post(
                    GROQ_URL, headers=headers, json=body,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:

                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"].strip()

                    elif resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", 60))
                        if retry_after > 300:
                            ok = await account_mgr.rotate(f"daily quota, retry-after={retry_after}s")
                            if not ok:
                                return None
                            continue
                        else:
                            print(f"  ⏳ Rate limit, chờ {retry_after}s...")
                            await asyncio.sleep(retry_after)
                            continue

                    elif resp.status == 503:
                        wait = (2 ** attempt) * 3
                        await asyncio.sleep(wait)
                        continue

                    else:
                        text = await resp.text()
                        print(f"  ⚠️  HTTP {resp.status}: {text[:150]}")
                        await asyncio.sleep(2)

            except asyncio.TimeoutError:
                await asyncio.sleep(3)
            except Exception as e:
                print(f"  ⚠️  {e}")
                await asyncio.sleep(2)

        return None


# ──────────────────────────────────────────────
# JSON parser
# ──────────────────────────────────────────────

def parse_json_response(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text  = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    objects, depth, in_str, esc, start = [], 0, False, False, None
    for i, ch in enumerate(text):
        if esc:               esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"':         in_str = not in_str; continue
        if in_str:            continue
        if ch == '{':
            if depth == 0:    start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:    objects.append(json.loads(text[start:i+1]))
                except: pass
                start = None
    return objects if objects else None


# ──────────────────────────────────────────────
# Flatten + Prompts
# ──────────────────────────────────────────────

def flatten_comments(comments):
    """
    Flatten comments + replies.
    Comment bị rule filter → đánh dấu is_trash=True ngay, không đưa vào LLM.
    """
    flat = []
    for c in comments:
        flat.append({
            "comment_id":      c["comment_id"],
            "text":            c.get("text", ""),
            "parent_text":     None,
            "rule_trash":      is_trash_rule(c.get("text", ""))
        })
        for r in c.get("replies", []):
            flat.append({
                "comment_id":  r["comment_id"],
                "text":        r.get("text", ""),
                "parent_text": c.get("text", ""),
                "rule_trash":  is_trash_rule(r.get("text", ""))
            })
    return flat


def _fallback(comment_id):
    return {"comment_id": comment_id, "is_trash": False, "stance": "trung lập"}

def build_prompt_step1(post_content, batch, event_name):
    items_str = ""
    for i, item in enumerate(batch):
        items_str += f"\n[{i}] comment_id: {item['comment_id']}\n"
        if item.get("parent_text"):
            items_str += f"    (reply của: \"{item['parent_text'][:80]}\")\n"
        items_str += f"    text: \"{item['text'][:150]}\"\n"
 
    return f"""Sự kiện: {event_name}
Nội dung bài đăng: {post_content[:600]}
 
Phân tích {len(batch)} comment. Trả về JSON array đúng thứ tự.
 
COMMENTS:{items_str}
 
=== QUY TẮC BẮT BUỘC (ưu tiên kiểm tra theo thứ tự) ===
 
Bước 1: Kiểm tra is_trash=true nếu thuộc 1 trong các trường hợp:
   - Chỉ là tên người đơn thuần (ví dụ: "Nguyễn Vanh", "Huỳnh Phương Ngọc", "Minh Dương")
   - Tag tên + emoji/reaction ngắn (ví dụ: "Trúc Phương bạn hiểu ý mình trứ 😌", "Lê Thành Đạt =)) buồn không anh")
   - Chỉ emoji hoặc ký tự lặp ("Hhh", "🫨", "=))")
   - Chứa link, nguồn, quảng cáo (moet.gov.vn, hocmai.vn, ".vn THPT", "Nguồn: https...")
   - Dưới 8 ký tự và vô nghĩa
 
Bước 2: Nếu is_trash=false thì mới xét stance:
   - "tích cực": đồng ý, ủng hộ, khen
   - "tiêu cực": phản đối, chỉ trích, lo ngại
   - "trung lập": thờ ơ, "kệ", không quan tâm
   - "cần xem xét": có ý kiến 2 chiều, đề xuất giải pháp, ủng hộ có điều kiện
 
LƯU Ý:
   - "trung lập" = KHÔNG có bất kỳ ý kiến nào
   - "cần xem xét" = PHẢI có nội dung suy nghĩ/sửa chữa
   - Comment ngắn "Đúng rồi" / "Sai hoàn toàn" → tích cực/tiêu cực
 
=== FEW-SHOT EXAMPLES ===
"Nguồn: https://moet.gov.vn/..." → is_trash: true, stance: "rác"
"Hocmai.vn THPT Thảo Su"        → is_trash: true, stance: "rác"
"Nguyễn Vanh"                   → is_trash: true, stance: "rác"
"Minh Dương"                    → is_trash: true, stance: "rác"
"Hhh"                           → is_trash: true, stance: "rác"
"Trúc Phương bạn hiểu ý mình trứ 😌" → is_trash: true, stance: "rác"
"Lê Thành Đạt =)) buồn không anh"    → is_trash: true, stance: "rác"
"Truy cứu trách nhiệm những người liên quan" → is_trash: false, stance: "tiêu cực"
"Hay quá, ủng hộ mạnh mẽ!"      → is_trash: false, stance: "tích cực"
 
Phân tích theo thứ tự Bước 1 → Bước 2.
Chỉ trả về JSON array, KHÔNG giải thích gì thêm:
[{{"comment_id":"...","is_trash":true,"stance":"rác"}}]"""


def build_prompt_step2(post_content, batch, event_name):
    items_str = ""
    for i, item in enumerate(batch):
        items_str += f"\n[{i}] comment_id: {item['comment_id']}\n"
        if item.get("parent_text"):
            items_str += f"    (reply của: \"{item['parent_text'][:80]}\")\n"
        items_str += f"    text: \"{item['text'][:300]}\"\n"

    return f"""Bạn là chuyên gia phân tích dư luận về chính sách giáo dục Việt Nam.

Sự kiện: {event_name}
Nội dung bài đăng: {post_content[:400]}

Phân loại chính xác các comment sau: "trung lập" hay "ý kiến riêng"?

COMMENTS:{items_str}

PHÂN BIỆT:
"trung lập": thờ ơ, không quan tâm, chỉ hỏi han, chờ xem
"ý kiến riêng": ủng hộ một phần + phê phán phần khác, đề xuất giải pháp, phân tích 2 chiều

Chỉ trả về JSON array, không giải thích:
[{{"comment_id":"...","is_trash":false,"stance":"ý kiến riêng"}}]"""


# ──────────────────────────────────────────────
# Analyze
# ──────────────────────────────────────────────

async def run_step1(session, semaphore, post_content, event_name, flat):
    """
    Bước 1: rule filter trước, chỉ đưa comment sạch vào LLM.
    """
    rule_trashed = [item for item in flat if item.get("rule_trash")]
    llm_batch    = [item for item in flat if not item.get("rule_trash")]

    print(f"     Rule filter: {len(rule_trashed)} rác | LLM: {len(llm_batch)} comments")

    analysis_map = {}
    for item in rule_trashed:
        analysis_map[item["comment_id"]] = {
            "comment_id": item["comment_id"],
            "is_trash":   True,
            "stance":     "rác"
        }

    if not llm_batch:
        return analysis_map

    batches = [llm_batch[i:i+BATCH_SIZE] for i in range(0, len(llm_batch), BATCH_SIZE)]

    async def process_batch(batch):
        if account_mgr.all_exhausted():
            return {item["comment_id"]: _fallback(item["comment_id"]) for item in batch}

        prompt    = build_prompt_step1(post_content, batch, event_name)
        raw       = await call_groq(session, prompt, semaphore)
        valid_ids = {item["comment_id"] for item in batch}
        result_map = {}

        if raw:
            parsed = parse_json_response(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    cid = item.get("comment_id")
                    if cid and cid in valid_ids:
                        result_map[cid] = item

        for x in batch:
            if x["comment_id"] not in result_map:
                result_map[x["comment_id"]] = _fallback(x["comment_id"])

        return result_map

    results = []
    for b in batches:
        r = await process_batch(b)
        results.append(r)

    for r in results:
        analysis_map.update(r)

    return analysis_map




async def run_step2(session, semaphore, post_content, event_name, candidates, flat_map):
    if not candidates:
        return {}
    batches = [candidates[i:i+BATCH_SIZE] for i in range(0, len(candidates), BATCH_SIZE)]

    async def process_batch(batch):
        if account_mgr.all_exhausted():
            return {item["comment_id"]: {**item, "stance": "trung lập"} for item in batch}
        enriched = [{"comment_id": item["comment_id"], "text": item["text"],
                     "parent_text": flat_map.get(item["comment_id"], {}).get("parent_text")}
                    for item in batch]
        prompt     = build_prompt_step2(post_content, enriched, event_name)
        raw        = await call_groq(session, prompt, semaphore)
        result_map = {}
        if raw:
            parsed = parse_json_response(raw)
            if isinstance(parsed, list):
                for p in parsed:
                    if "comment_id" in p:
                        result_map[p["comment_id"]] = p
        for x in batch:
            if x["comment_id"] not in result_map:
                result_map[x["comment_id"]] = {**x, "stance": "trung lập"}
        return result_map

    results = await asyncio.gather(*[process_batch(b) for b in batches])
    merged = {}
    for r in results:
        merged.update(r)
    return merged




async def analyze_file(session, semaphore, data):
    post_content = data.get("post_content", "")
    event_name   = data.get("event_name", data["id_content"])
    flat         = flatten_comments(data.get("comments", []))
    if not flat:
        return {}

    flat_map     = {item["comment_id"]: item for item in flat}
    total_batches = (len(flat) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  📊 {len(flat)} comments | {total_batches} batches | Bước 1...")

    analysis_map = await run_step1(session, semaphore, post_content, event_name, flat)

    candidates = [
        {"comment_id": cid, "text": flat_map[cid]["text"]}
        for cid, result in analysis_map.items()
        if result.get("stance") == "cần xem xét" and cid in flat_map
    ]
    if candidates:
        print(f"  🔍 Bước 2: {len(candidates)} comments 'cần xem xét'...")
        step2_map = await run_step2(session, semaphore, post_content, event_name, candidates, flat_map)
        analysis_map.update(step2_map)

    for cid, result in analysis_map.items():
        if result.get("stance") == "cần xem xét":
            result["stance"] = "trung lập"

    return analysis_map


# ──────────────────────────────────────────────
# Build outputs
# ──────────────────────────────────────────────

def build_full_analyzed(data, analysis_map):
    comments_out = []
    for c in data["comments"]:
        cid = c["comment_id"]
        ca  = analysis_map.get(cid, _fallback(cid))

        tagged_replies = []
        for r in c.get("replies", []):
            rid = r["comment_id"]
            ra  = analysis_map.get(rid, _fallback(rid))
            tagged_replies.append({
                "comment_id":  rid, "order": r.get("order"),
                "reply_to_id": r.get("reply_to_id"), "text": r.get("text", ""),
                "likes":       r.get("likes", 0), "is_trash": ra.get("is_trash", False),
                "stance":      ra.get("stance"),
            })

        all_in_thread = [ca] + [analysis_map.get(r["comment_id"], _fallback(r["comment_id"]))
                                for r in c.get("replies", [])]
        valid         = [x for x in all_in_thread if not x.get("is_trash")]
        stance_counts = defaultdict(int)
        for item in valid:
            if item.get("stance"):
                stance_counts[item["stance"]] += 1

        total_valid   = len(valid)
        top_count     = max(stance_counts.values()) if stance_counts else 0
        controversial = (total_valid > 1 and top_count / total_valid < 0.7) if total_valid > 0 else False

        comments_out.append({
            "comment_id": cid, "order": c.get("order"), "text": c.get("text", ""),
            "likes": c.get("likes", 0), "reply_count": c.get("reply_count", 0),
            "is_trash": ca.get("is_trash", False), "stance": ca.get("stance"),
            "thread_stats": {"total": total_valid, "stances": dict(stance_counts),
                             "controversial": controversial},
            "replies": tagged_replies
        })

    return {"id_content": data["id_content"], "event_name": data.get("event_name", ""),
            "post_content": data.get("post_content", ""), "comments": comments_out}


async def build_summary(session, semaphore, full_data):
    comments     = full_data["comments"]
    all_comments = list(comments)
    for c in comments:
        all_comments += c.get("replies", [])

    counts = {"tích cực": 0, "tiêu cực": 0, "trung lập": 0, "ý kiến riêng": 0, "rác": 0}
    for item in all_comments:
        if item.get("is_trash"):
            counts["rác"] += 1
        else:
            s = item.get("stance", "trung lập")
            if s in counts:
                counts[s] += 1

    total_valid = sum(v for k, v in counts.items() if k != "rác")

    def pct(n):
        return f"{n/total_valid*100:.1f}%" if total_valid > 0 else "0%"

    def get_examples(stance):
        candidates = [c for c in comments if not c.get("is_trash") and c.get("stance") == stance]
        top = sorted(candidates, key=lambda x: x.get("likes", 0), reverse=True)[:3]
        return [c["text"][:150] for c in top]

    examples = {s: get_examples(s) for s in STANCE_LABELS}

    async def summarize_stance(stance, ex_list):
        if not ex_list:
            return ""
        examples_str = "\n".join([f"- \"{e}\"" for e in ex_list])
        prompt = f"""Sự kiện giáo dục: {full_data.get('event_name', '')}

Các comment tiêu biểu nhóm "{stance}":
{examples_str}

Tổng hợp xu thế chung thành 2-3 câu ngắn gọn. Chỉ trả về đoạn tổng hợp:"""
        return await call_groq(session, prompt, semaphore) or ""

    print(f"  📝 LLM tổng hợp từng nhóm...")
    summaries = {}
    for stance in STANCE_LABELS:
        summaries[stance] = await summarize_stance(stance, examples[stance]) if counts[stance] > 0 else ""
        await asyncio.sleep(0.5)

    print(f"  📝 LLM viết kết luận...")
    summaries_str = "\n".join([
        f"- {s.capitalize()} ({counts[s]}, {pct(counts[s])}): {summaries[s]}"
        for s in STANCE_LABELS if counts[s] > 0
    ])
    conclusion_prompt = f"""Sự kiện: {full_data.get('event_name', '')}

Tổng hợp dư luận:
{summaries_str}

Viết 2 câu:
focus: <Dư luận quan tâm nhất về...>
trend: <Xu hướng dư luận...>

Chỉ trả về 2 dòng format trên:"""

    conclusion_raw = await call_groq(session, conclusion_prompt, semaphore) or ""
    focus = trend = ""
    for line in conclusion_raw.split("\n"):
        if line.startswith("focus:"):
            focus = line.replace("focus:", "").strip()
        elif line.startswith("trend:"):
            trend = line.replace("trend:", "").strip()

    analysis = {
        stance: {"count": counts[stance], "percent": pct(counts[stance]),
                 "summary": summaries[stance], "examples": examples[stance]}
        for stance in STANCE_LABELS
    }

    return {
        "id_content":  full_data["id_content"],
        "event_name":  full_data.get("event_name", ""),
        "comment_counts": {
            "total": total_valid + counts["rác"],
            "tích_cực": counts["tích cực"], "tiêu_cực": counts["tiêu cực"],
            "trung_lập": counts["trung lập"], "ý_kiến_riêng": counts["ý kiến riêng"],
            "rác": counts["rác"]
        },
        "analysis":   analysis,
        "conclusion": {"focus": focus, "trend": trend}
    }


# ──────────────────────────────────────────────
# Main với logging
# ──────────────────────────────────────────────

async def run(input_dir, output_dir):
    global account_mgr
    account_mgr = AccountManager(GROQ_ACCOUNTS)

    if account_mgr.get_key() is None:
        print("❌ Chưa điền API keys vào GROQ_ACCOUNTS!")
        return

    full_dir    = os.path.join(output_dir, "full")
    summary_dir = os.path.join(output_dir, "summary")
    os.makedirs(full_dir,    exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    # Đọc file input
    if os.path.isfile(input_dir):
        file_list = [(input_dir, os.path.basename(input_dir))]
    else:
        file_list = [(os.path.join(input_dir, f), f)
                     for f in sorted(os.listdir(input_dir)) if f.endswith(".json")]

    all_data = []
    for filepath, filename in file_list:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        entries = raw if isinstance(raw, list) else [raw]
        all_data.extend(entries)

    # Logger
    logger = RunLogger(output_dir)
    logger.set_all_files([d.get("id_content", "unknown") for d in all_data])

    # Lọc pending
    pending = []
    for data in all_data:
        id_content   = data.get("id_content", "unknown")
        full_path    = os.path.join(full_dir,    f"{id_content}.json")
        summary_path = os.path.join(summary_dir, f"{id_content}.json")
        if os.path.exists(full_path) and os.path.exists(summary_path):
            print(f"⏭️  Bỏ qua (đã có): {id_content}")
        else:
            pending.append(data)

    skipped   = len(all_data) - len(pending)
    total     = len(pending)
    print(f"\n📂 Tổng {len(all_data)} | ✅ Đã có: {skipped} | ⏳ Cần xử lý: {total}")
    print(f"🕐 Bắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    if total == 0:
        print("🎉 Tất cả đã xử lý xong!")
        logger.save("completed")
        return

    semaphore  = asyncio.Semaphore(MAX_CONCURRENT)
    processed  = 0
    start_time = time.time()
    stop_reason = "completed"

    connector = aiohttp.TCPConnector(limit=20)
    async with aiohttp.ClientSession(connector=connector) as session:
        for data in pending:
            if account_mgr.all_exhausted():
                remaining = total - processed
                print(f"\n{'='*50}")
                print(f"⛔ Tất cả account đã hết quota!")
                print(f"   Đã xử lý: {processed}/{total} | Còn lại: {remaining}")
                print(f"   ➡️  Quota reset 00:00 UTC. Chạy lại ngày mai.")
                stop_reason = "quota_exhausted"
                break

            id_content  = data.get("id_content", "unknown")
            file_start  = time.time()
            print(f"\n{'='*50}")
            print(f"🔄 [{processed+1}/{total}] {id_content} | Account #{account_mgr.current+1}")

            analysis_map = await analyze_file(session, semaphore, data)

            full_data    = build_full_analyzed(data, analysis_map)
            summary_data = await build_summary(session, semaphore, full_data)

            with open(os.path.join(full_dir,    f"{id_content}.json"), "w", encoding="utf-8") as f:
                json.dump(full_data,    f, ensure_ascii=False, indent=2)
            with open(os.path.join(summary_dir, f"{id_content}.json"), "w", encoding="utf-8") as f:
                json.dump(summary_data, f, ensure_ascii=False, indent=2)

            file_elapsed = time.time() - file_start
            processed   += 1
            logger.mark_done(id_content, file_elapsed)

            total_elapsed = time.time() - start_time
            avg = total_elapsed / processed
            eta = avg * (total - processed)
            print(f"  ✅ Xong ({_fmt_duration(file_elapsed)}) | "
                  f"Total: {_fmt_duration(total_elapsed)} | ETA: ~{_fmt_duration(eta)}")

    # Lưu log
    entry = logger.save(stop_reason)
    print(f"\n{'='*50}")
    print(f"📊 TỔNG KẾT SESSION {entry['session_id']}")
    print(f"   Thời gian chạy : {entry['elapsed_human']}")
    print(f"   Đã xử lý      : {entry['processed']}/{entry['total_files']} file")
    print(f"   Còn lại        : {entry['remaining']} file")
    print(f"   Trung bình     : {entry['avg_per_file_s']}s/file")
    print(f"   Lý do dừng     : {entry['stop_reason']}")

    if processed == total:
        print(f"\n🎉 Hoàn tất tất cả {total} file!")


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 analyze_education_async.py <input_dir> <output_dir>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()