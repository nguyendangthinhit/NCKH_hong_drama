"""
analyze_showbiz_async.py
-------------------------
Phân tích emotion + toxic cho showbiz data dùng Groq API async.

Improvements từ education version:
  - is_trash_rule() pre-filter trước LLM
  - valid_ids filter trong process_batch (tránh LLM hallucinate)
  - RunLogger ghi log session
  - Prompt cập nhật với few-shot examples

Nhãn: Phẫn nộ / Cà khịa / Đồng cảm / Ủng hộ / Trung lập + toxic detection

Cách dùng:
    python3 analyze_showbiz_async.py <input_dir> <output_dir>

Yêu cầu:
    pip install aiohttp aiofiles
"""

import json
import os
import sys
import re
import time
import asyncio
import aiohttp
import aiofiles
from collections import defaultdict
from datetime import datetime

# ──────────────────────────────────────────────
# Điền API keys
# ──────────────────────────────────────────────
API_KEYS = [

]

GROQ_MODEL       = "llama-3.3-70b-versatile"
GROQ_URL         = "https://api.groq.com/openai/v1/chat/completions"
EMOTION_LABELS   = ["Phẫn nộ", "Cà khịa", "Đồng cảm", "Ủng hộ", "Trung lập"]
BATCH_SIZE       = 10
MAX_CONCURRENT   = 3
MIN_KEY_INTERVAL = 1.0
MAX_RETRY_WAIT   = 30


# ──────────────────────────────────────────────
# Key Pool
# ──────────────────────────────────────────────

class KeyPool:
    def __init__(self, keys):
        self._keys      = [k for k in keys if not k.startswith("YOUR_")]
        self._idx       = 0
        self._lock      = asyncio.Lock()
        self._last_used = {k: 0.0 for k in self._keys}

    def current(self):
        return self._keys[self._idx] if self._idx < len(self._keys) else None

    async def rotate(self, reason=""):
        async with self._lock:
            if self._idx < len(self._keys) - 1:
                self._idx += 1
                print(f"  ⚠️  Rotate → key #{self._idx + 1} ({reason})")
                return True
            print("  ❌ Đã hết API key dự phòng!")
            return False

    def all_exhausted(self):
        return self._idx >= len(self._keys) - 1 and self._last_used.get(self.current(), 0) < 0

    async def wait_for_slot(self):
        key  = self.current()
        if not key:
            return
        wait = MIN_KEY_INTERVAL - (time.monotonic() - self._last_used.get(key, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_used[key] = time.monotonic()


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
        self.files_done.append({"id_content": id_content, "elapsed_s": round(elapsed, 1)})

    def save(self, stop_reason="completed"):
        finished_at   = datetime.now()
        elapsed       = (finished_at - self.started_at).total_seconds()
        done_ids      = [f["id_content"] for f in self.files_done]
        remaining_ids = [f for f in self.all_files if f not in done_ids]

        entry = {
            "session_id":      self.session_id,
            "started_at":      self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at":     finished_at.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_human":   _fmt_duration(elapsed),
            "total_files":     len(self.all_files),
            "processed":       len(self.files_done),
            "remaining":       len(remaining_ids),
            "stop_reason":     stop_reason,
            "files_done":      self.files_done,
            "files_remaining": remaining_ids,
            "avg_per_file_s":  round(elapsed / len(self.files_done), 1) if self.files_done else 0,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"\n💾 Log đã lưu → {self.log_path}")
        return entry


def _fmt_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:   return f"{h}h {m}m {s}s"
    elif m > 0: return f"{m}m {s}s"
    return f"{s}s"


# ──────────────────────────────────────────────
# Trash rule (từ education version)
# ──────────────────────────────────────────────

def looks_like_name_word(w):
    if not w:                                    return False
    if not w[0].isupper():                       return False
    if len(w) > 1 and not w[1:].islower():       return False
    if any(c.isdigit() for c in w):              return False
    return True


def looks_like_name(s):
    words = s.strip().split()
    if len(words) < 2 or len(words) > 5:
        return False
    return all(looks_like_name_word(w) for w in words)


def is_trash_rule(text: str) -> bool:
    raw = text.strip()
    t   = raw.lower()

    if len(t.replace(" ", "")) < 4:
        return True
    if not re.search(r'[a-zàáâãèéêìíòóôõùúăđĩũơ]', t):
        return True
    if re.fullmatch(r'(h+|k+|ok+e*|lol+|haha+|he+|hi+|uh+|ah+|ew+|hehe+)', t):
        return True
    if re.search(r'https?://', t):
        return True
    if re.search(r'\b(thpt|thcs|hocmai|fanpage)\b', t):
        return True
    if re.search(r'\b(trường thpt|trường thcs|trường đh|trường đại học)\b', t):
        return True
    if re.search(r'[a-z]+\.vn\b', t):
        return True
    if "@" in t and len(raw.split()) <= 4:
        return True
    spam_keywords = ["lụm về share", "lụm", "share", "quảng cáo",
                     "inbox mình", "inbox em", "tag ", "bit.ly"]
    if any(k in t for k in spam_keywords):
        return True

    words = raw.split()

    if looks_like_name(raw):
        return True

    for name_len in range(4, 1, -1):
        if len(words) >= name_len and looks_like_name(" ".join(words[:name_len])):
            remaining = " ".join(words[name_len:]).strip()
            if not remaining:
                return True
            if len(remaining) < 30:
                return True
            if re.fullmatch(r'[=:;<>()\-\/\\🫨😂😭😅😆🥲👍👎❤️🔥💀🙄😑😐🤣\s]+', remaining):
                return True
            break

    return False


# ──────────────────────────────────────────────
# Async API caller
# ──────────────────────────────────────────────

async def call_groq_async(session, key_pool, prompt, retries=5):
    for attempt in range(retries):
        await key_pool.wait_for_slot()
        key = key_pool.current()
        if not key:
            return None

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body    = {
            "model":       GROQ_MODEL,
            "messages":    [{"role": "user", "content": prompt}],
            "max_tokens":  8192,
            "temperature": 0.1,
        }
        try:
            async with session.post(GROQ_URL, headers=headers, json=body,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()

                elif resp.status == 503:
                    wait = (2 ** attempt) * 5
                    print(f"  ⚠️  503, chờ {wait}s...")
                    await asyncio.sleep(wait)

                elif resp.status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    raw_wait    = int(retry_after) if retry_after else (2 ** attempt) * 5
                    wait        = min(raw_wait, MAX_RETRY_WAIT)
                    print(f"  ⏳ 429, chờ {wait}s...")
                    await asyncio.sleep(wait)
                    await key_pool.rotate("rate limit 429")

                elif resp.status == 401:
                    if not await key_pool.rotate("unauthorized 401"):
                        return None

                elif resp.status == 413:
                    print("  ⚠️  413 prompt quá dài, bỏ batch")
                    return None

                else:
                    text = await resp.text()
                    print(f"  ⚠️  HTTP {resp.status}: {text[:200]}")
                    await asyncio.sleep(3)

        except asyncio.TimeoutError:
            print(f"  ⚠️  Timeout lần {attempt + 1}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"  ⚠️  {e}")
            await asyncio.sleep(3)

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

    # Recover từ JSON bị cắt
    last_valid = None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text):
        if esc:          esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"':    in_str = not in_str; continue
        if in_str:       continue
        if ch == '[':    depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                last_valid = i; break
    if last_valid:
        try:
            return json.loads(text[:last_valid + 1])
        except:
            pass

    objects, depth, in_str, esc, start = [], 0, False, False, None
    for i, ch in enumerate(text):
        if esc:          esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"':    in_str = not in_str; continue
        if in_str:       continue
        if ch == '{':
            if depth == 0: start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:    objects.append(json.loads(text[start:i+1]))
                except: pass
                start = None
    return objects if objects else None


# ──────────────────────────────────────────────
# Flatten + Prompt
# ──────────────────────────────────────────────

def flatten_comments(comments):
    flat = []
    for c in comments:
        flat.append({
            "comment_id":  c["comment_id"],
            "text":        c.get("text", ""),
            "parent_text": None,
            "rule_trash":  is_trash_rule(c.get("text", ""))
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
    return {"comment_id": comment_id, "is_trash": False,
            "emotion": "Trung lập", "toxic": False, "toxic_type": None}


def build_batch_prompt(post_content, batch, event_name):
    items_str = ""
    for i, item in enumerate(batch):
        items_str += f"\n[{i}] comment_id: {item['comment_id']}\n"
        if item.get("parent_text"):
            items_str += f"    (reply của: \"{item['parent_text'][:80]}\")\n"
        items_str += f"    text: \"{item['text'][:150]}\"\n"

    return f"""Bạn là chuyên gia phân tích dư luận mạng xã hội Việt Nam (showbiz/giải trí).

Sự kiện: {event_name}
Nội dung bài đăng: {post_content[:500]}

Phân tích {len(batch)} comment. Trả về JSON array {len(batch)} phần tử theo đúng thứ tự.

COMMENTS:{items_str}

=== QUY TẮC BẮT BUỘC ===

Bước 1: Kiểm tra is_trash=true nếu:
   - Chỉ là tên người: "Nguyễn Văn A", "Minh Dương"
   - Tag tên + emoji/reaction ngắn: "Trúc Phương bạn xem đi 😂", "Nam ơi :))"
   - Chỉ emoji hoặc ký tự lặp: "😂😂", "Hhh", "=))"
   - Chứa link/quảng cáo: "https://...", "inbox mình nha"
   - Dưới 8 ký tự vô nghĩa

Bước 2: Nếu is_trash=false thì xét emotion + toxic:
   - emotion: "Phẫn nộ"=tức giận/bức xúc | "Cà khịa"=mỉa mai/châm biếm
              "Đồng cảm"=thương/chia sẻ | "Ủng hộ"=đồng ý/khen
              "Trung lập"=thông tin/hỏi/không rõ cảm xúc
   - toxic=true nếu chửi bới/công kích dù ngắn ("đm", "ngu", "con chó",...)
   - toxic_type: "chửi bới" / "công kích cá nhân" / "công kích người thân"

LƯU Ý QUAN TRỌNG:
   - ":)))" hoặc 🌝 trong tiếng Việt thường = mỉa mai → Cà khịa
   - Chê ngoại hình/hành động → Cà khịa hoặc Phẫn nộ, KHÔNG phải Trung lập
   - "May là mình chưa dùng 😁" trong bối cảnh hàng giả → Cà khịa
   - Comment ngắn có chửi ("đm", "nghiện") → toxic=true dù ngắn

=== FEW-SHOT EXAMPLES ===
"Trần Trọng Tín 🫨"              → is_trash: true
"Lê Thành Đạt =)) buồn không"   → is_trash: true
"Sao nó xấu kinh dị vậy trời"   → is_trash: false, emotion: "Cà khịa", toxic: false
"May là mình chưa dùng sp 😁"    → is_trash: false, emotion: "Cà khịa", toxic: false
"2700 tỷ viết ngắn gọn thôi"    → is_trash: false, emotion: "Cà khịa", toxic: false
"Ủng hộ chị 100%"               → is_trash: false, emotion: "Ủng hộ", toxic: false
"Đm thằng này láo"              → is_trash: false, emotion: "Phẫn nộ", toxic: true, toxic_type: "chửi bới"
"Tội nghiệp quá"                → is_trash: false, emotion: "Đồng cảm", toxic: false

Chỉ trả về JSON array, KHÔNG giải thích:
[{{"comment_id":"...","is_trash":false,"emotion":"Cà khịa","toxic":false,"toxic_type":null}}]"""


# ──────────────────────────────────────────────
# Batch analysis
# ──────────────────────────────────────────────

async def analyze_batch_async(session, key_pool, semaphore, post_content, batch, event_name, batch_idx, total_batches):
    async with semaphore:
        prompt    = build_batch_prompt(post_content, batch, event_name)
        raw       = await call_groq_async(session, key_pool, prompt)
        valid_ids = {item["comment_id"] for item in batch}  # fix từ education

        if not raw:
            print(f"  ❌ Batch {batch_idx}/{total_batches} fallback")
            return {item["comment_id"]: _fallback(item["comment_id"]) for item in batch}

        result = parse_json_response(raw)
        if not isinstance(result, list):
            print(f"  ❌ Batch {batch_idx}/{total_batches} parse lỗi → fallback")
            return {item["comment_id"]: _fallback(item["comment_id"]) for item in batch}

        analysis_map = {}
        for item in result:
            cid = item.get("comment_id")
            if cid and cid in valid_ids:  # chỉ accept id hợp lệ
                analysis_map[cid] = item

        missing = [item["comment_id"] for item in batch if item["comment_id"] not in analysis_map]
        if missing:
            print(f"  ⚠️  Batch {batch_idx}/{total_batches} miss {len(missing)} → fallback")
            for cid in missing:
                analysis_map[cid] = _fallback(cid)
        else:
            print(f"  ✅ Batch {batch_idx}/{total_batches}")

        return analysis_map


async def analyze_all_comments(session, key_pool, post_content, event_name, flat):
    """Tách rule_trash → song song với asyncio.gather."""
    rule_trashed = [item for item in flat if item.get("rule_trash")]
    llm_batch    = [item for item in flat if not item.get("rule_trash")]

    print(f"     Rule filter: {len(rule_trashed)} rác | LLM: {len(llm_batch)} comments")

    # Mark rule_trash ngay
    analysis_map = {}
    for item in rule_trashed:
        analysis_map[item["comment_id"]] = {
            "comment_id": item["comment_id"],
            "is_trash":   True,
            "emotion":    None,
            "toxic":      None,
            "toxic_type": None
        }

    if not llm_batch:
        return analysis_map

    batches   = [llm_batch[i:i+BATCH_SIZE] for i in range(0, len(llm_batch), BATCH_SIZE)]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    total_b   = len(batches)

    tasks = [
        analyze_batch_async(session, key_pool, semaphore,
                            post_content, batch, event_name, idx+1, total_b)
        for idx, batch in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks)
    for r in results:
        analysis_map.update(r)

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
                "likes":       r.get("likes", 0),
                "is_trash":    ra.get("is_trash", False),
                "emotion":     ra.get("emotion"),
                "toxic":       ra.get("toxic"),
                "toxic_type":  ra.get("toxic_type"),
            })

        all_in_thread  = [ca] + [analysis_map.get(r["comment_id"], _fallback(r["comment_id"]))
                                  for r in c.get("replies", [])]
        valid          = [x for x in all_in_thread if not x.get("is_trash")]
        emotion_counts = defaultdict(int)
        toxic_count    = 0
        for item in valid:
            if item.get("emotion"): emotion_counts[item["emotion"]] += 1
            if item.get("toxic"):   toxic_count += 1

        total_valid   = len(valid)
        top_count     = max(emotion_counts.values()) if emotion_counts else 0
        controversial = (total_valid > 1 and top_count / total_valid < 0.7) if total_valid > 0 else False

        comments_out.append({
            "comment_id":  cid, "order": c.get("order"), "text": c.get("text", ""),
            "likes":       c.get("likes", 0), "reply_count": c.get("reply_count", 0),
            "is_trash":    ca.get("is_trash", False),
            "emotion":     ca.get("emotion"),
            "toxic":       ca.get("toxic"), "toxic_type": ca.get("toxic_type"),
            "thread_stats": {
                "total":        total_valid,
                "emotions":     dict(emotion_counts),
                "toxic_count":  toxic_count,
                "controversial": controversial
            },
            "replies": tagged_replies
        })

    return {"id_content":   data["id_content"],
            "event_name":   data.get("event_name", ""),
            "post_content": data.get("post_content", ""),
            "comments":     comments_out}


def build_summary(full_data):
    comments      = full_data["comments"]
    all_valid     = [c for c in comments if not c.get("is_trash")]
    for c in comments:
        all_valid += [r for r in c.get("replies", []) if not r.get("is_trash")]

    emotion_stats = {label: 0 for label in EMOTION_LABELS}
    for item in all_valid:
        e = item.get("emotion")
        if e in emotion_stats:
            emotion_stats[e] += 1

    toxic_stats = {"total_toxic": 0, "chửi bới": 0,
                   "công kích cá nhân": 0, "công kích người thân": 0}
    for item in all_valid:
        if item.get("toxic"):
            toxic_stats["total_toxic"] += 1
            tt = item.get("toxic_type")
            if tt in toxic_stats:
                toxic_stats[tt] += 1

    top_level_valid = [c for c in comments if not c.get("is_trash")]
    sorted_score    = sorted(top_level_valid,
                             key=lambda x: x.get("likes", 0) + x.get("reply_count", 0),
                             reverse=True)
    most_popular = [{
        "comment_id":  c["comment_id"], "text": c["text"],
        "likes":       c.get("likes", 0), "reply_count": c.get("reply_count", 0),
        "score":       c.get("likes", 0) + c.get("reply_count", 0),
        "emotion":     c.get("emotion")
    } for c in sorted_score[:3]]

    by_emotion = {}
    for label in EMOTION_LABELS:
        candidates = [c for c in top_level_valid if c.get("emotion") == label]
        if candidates:
            top = max(candidates, key=lambda x: x.get("likes", 0) + x.get("reply_count", 0))
            by_emotion[label] = {
                "comment_id": top["comment_id"], "text": top["text"],
                "score": top.get("likes", 0) + top.get("reply_count", 0)
            }

    controversial_threads = [
        {"comment_id": c["comment_id"], "text": c["text"],
         "thread_stats": c.get("thread_stats", {})}
        for c in top_level_valid
        if c.get("thread_stats", {}).get("controversial", False)
    ]

    return {
        "id_content":   full_data["id_content"],
        "event_name":   full_data.get("event_name", ""),
        "total_comments": len(all_valid),
        "emotion_stats":  emotion_stats,
        "toxic_stats":    toxic_stats,
        "top_comments": {
            "most_popular":     most_popular,
            "by_emotion":       by_emotion,
            "notable_opinions": []
        },
        "controversial_threads": controversial_threads
    }


# ──────────────────────────────────────────────
# Process 1 file
# ──────────────────────────────────────────────

async def process_file(session, key_pool, data, full_dir, summary_dir, logger):
    id_content   = data.get("id_content", "unknown")
    full_path    = os.path.join(full_dir,    f"{id_content}.json")
    summary_path = os.path.join(summary_dir, f"{id_content}.json")

    if os.path.exists(full_path) and os.path.exists(summary_path):
        print(f"⏭️  Bỏ qua (đã có): {id_content}")
        return True  # skip

    print(f"\n{'='*50}")
    print(f"🔄 {id_content}")

    comments = data.get("comments", [])
    if not comments:
        print("  ⚠️  Không có comments, bỏ qua")
        return True

    t0           = time.time()
    post_content = data.get("post_content", "")
    event_name   = data.get("event_name", id_content)

    flat         = flatten_comments(comments)
    total_b      = (len([x for x in flat if not x.get("rule_trash")]) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"  📊 {len(flat)} comments | ~{total_b} batches LLM")

    analysis_map = await analyze_all_comments(session, key_pool, post_content, event_name, flat)

    full_data    = build_full_analyzed(data, analysis_map)
    summary_data = build_summary(full_data)

    async with aiofiles.open(full_path,    "w", encoding="utf-8") as f:
        await f.write(json.dumps(full_data,    ensure_ascii=False, indent=2))
    async with aiofiles.open(summary_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(summary_data, ensure_ascii=False, indent=2))

    elapsed = time.time() - t0
    logger.mark_done(id_content, elapsed)
    print(f"  ✅ Xong ({_fmt_duration(elapsed)})")
    return False  # not skip


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def run(input_path, output_dir):
    if not API_KEYS or API_KEYS[0].startswith("YOUR_"):
        print("❌ Chưa điền API keys vào API_KEYS!")
        return

    full_dir    = os.path.join(output_dir, "full")
    summary_dir = os.path.join(output_dir, "summary")
    os.makedirs(full_dir,    exist_ok=True)
    os.makedirs(summary_dir, exist_ok=True)

    # Đọc file input
    if os.path.isfile(input_path):
        file_list = [(input_path, os.path.basename(input_path))]
    else:
        file_list = [(os.path.join(input_path, f), f)
                     for f in sorted(os.listdir(input_path)) if f.endswith(".json")]

    all_data = []
    for filepath, filename in file_list:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
        entries = raw if isinstance(raw, list) else [raw]
        all_data.extend(entries)

    logger = RunLogger(output_dir)
    logger.set_all_files([d.get("id_content", "unknown") for d in all_data])

    total     = len(all_data)
    start_time = time.time()
    print(f"\n📂 Tổng {total} file")
    print(f"🕐 Bắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    key_pool    = KeyPool(API_KEYS)
    stop_reason = "completed"
    processed   = 0

    async with aiohttp.ClientSession() as session:
        for data in all_data:
            skipped = await process_file(session, key_pool, data, full_dir, summary_dir, logger)
            if not skipped:
                processed += 1
                elapsed   = time.time() - start_time
                remaining = total - processed
                avg       = elapsed / processed
                print(f"  ⏱ Total: {_fmt_duration(elapsed)} | ETA: ~{_fmt_duration(avg * remaining)}")

    entry = logger.save(stop_reason)
    print(f"\n{'='*50}")
    print(f"📊 TỔNG KẾT  {entry['session_id']}")
    print(f"   Thời gian : {entry['elapsed_human']}")
    print(f"   Đã xử lý : {entry['processed']}/{entry['total_files']} file")
    print(f"   Còn lại   : {entry['remaining']} file")
    if processed == total:
        print(f"\n🎉 Hoàn tất!")


def main():
    if len(sys.argv) < 3:
        print("Dùng: python3 analyze_showbiz_async.py <input_dir> <output_dir>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()