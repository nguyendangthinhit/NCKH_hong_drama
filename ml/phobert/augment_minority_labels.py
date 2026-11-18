"""Làm giàu dữ liệu: sinh thêm bình luận cho nhãn thiểu số bằng LLM (few-shot từ bình luận thật cùng sự kiện).

- Key đọc từ `api.txt` ở gốc repo (đã .gitignore), dùng LẦN LƯỢT từ trên xuống; key hết hạn mức/bị từ chối
  (429/401/403) thì bỏ, sang key kế tiếp; hết key thì dừng và báo. Không in key.
  Sinh và kiểm nhãn đều dùng Gemini (mục GEMINI, 2 prompt riêng). Key Groq trong file hiện trả 403 nên không dùng.
- Mỗi lô = 2 request (sinh BATCH câu + kiểm nhãn gộp cả lô), theo quyết định 2026-11-13 (tối ưu số request).
  Câu sinh kế thừa `event_id` của mẫu nên chia train/val/test theo sự kiện không rò rỉ.
- Kết quả ghi `labeling data/augmented_<domain>.csv` (is_synthetic=True), KHÔNG trộn vào 2 file xlsx gốc.
Chạy: py -3.14 ml/phobert/augment_minority_labels.py --domain education [--limit-batches 1]
"""

import argparse, csv, json, math, random, re, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
GEN_MODEL = "gemini-3.5-flash-lite"
DATA = ROOT / "labeling data"
FILES = {"education": "verify_education_5k_dedup.xlsx", "showbiz": "verify_showbiz_5k_dedup.xlsx"}
# Số câu cần thêm mỗi nhãn (kéo nhãn nhỏ lên gần nhãn lớn)
TARGETS = {
    "showbiz": {"Đồng cảm": 400, "Ủng hộ": 350},
    "education": {"tích cực": 500, "ý kiến riêng": 400},
}
BATCH, N_EXAMPLES, KEEP_RATE = 40, 12, 0.5  # câu sinh/lô, mẫu thật làm ví dụ, tỉ lệ giữ ước tính


class Exhausted(Exception):
    """Hết key dùng được cho một provider."""


class KeyPool:
    """Key theo thứ tự trong api.txt. Key lỗi quota/xác thực bị loại, chuyển key kế tiếp."""

    def __init__(self, path):
        self.keys, section = {"gemini": []}, None
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if "=====" in s:
                section = "gemini" if "GEMINI" in s.upper() else None
            elif s and section:
                self.keys[section].append(s)
        self.used = Counter()

    def call(self, provider, prompt):
        ks = self.keys[provider]
        while ks:
            try:
                self.used[provider] += 1
                return gemini(ks[0], prompt)
            except urllib.error.HTTPError as e:
                if e.code not in (429, 401, 403):
                    raise RuntimeError(f"{provider} HTTP {e.code}")
                print(f"  {provider}: key #{self.used_key(provider)} bị {e.code}, sang key kế tiếp", flush=True)
                ks.pop(0)  # KHÔNG thử lại key này
            except (urllib.error.URLError, TimeoutError) as e:
                raise RuntimeError(f"{provider} mạng: {str(e)[:80]}")
        raise Exhausted(provider)

    def used_key(self, provider):
        return f"còn {len(self.keys[provider]) - 1} key sau key này"


def post(url, headers, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    return json.load(urllib.request.urlopen(req, timeout=120))


def gemini(key, prompt):
    out = post(GEMINI_URL.format(GEN_MODEL), {"x-goog-api-key": key}, {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": 8192}})
    return "".join(p.get("text", "") for p in out["candidates"][0]["content"]["parts"])


def parse_json(text):
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def jaccard(a, b):
    a, b = set(a.split()), set(b.split())
    return len(a & b) / max(1, len(a | b))


def load(domain):
    ws = openpyxl.load_workbook(DATA / FILES[domain], read_only=True)["Sheet1"]
    return [r for r in ws.iter_rows(min_row=2, values_only=True) if r[2] and r[3]]  # cột: id,event,text,label,...


def make_batch(pool, event, label, examples, labels):
    ex = "\n".join(f"- {t[:300]}" for t in examples)
    gen = pool.call("gemini", (
        f"Dưới đây là bình luận mạng xã hội THẬT của người Việt về cùng một sự kiện, đều có nhãn \"{label}\":\n{ex}\n\n"
        f"Viết {BATCH} bình luận MỚI cùng nhãn \"{label}\", cùng chủ đề sự kiện, văn phong đời thường (viết tắt, lóng, "
        "có thể sai chính tả nhẹ), độ dài đa dạng, không lặp ý, không chép lại ví dụ. "
        f"Chỉ trả về JSON array gồm {BATCH} chuỗi."))
    cands = [c for c in parse_json(gen) if isinstance(c, str) and c.strip()]
    if not cands:
        return []
    chk = pool.call("gemini", (
        f"Ví dụ bình luận thật nhãn \"{label}\":\n{ex}\n\nCác nhãn có thể: {', '.join(labels)}.\n"
        "Gán nhãn cho từng bình luận sau, trả về JSON array nhãn cùng thứ tự, không giải thích:\n"
        + json.dumps(cands, ensure_ascii=False)))
    got = parse_json(chk)
    return [c for c, g in zip(cands, got) if str(g).strip().lower() == label.lower()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True, choices=FILES)
    ap.add_argument("--limit-batches", type=int, default=0, help="chỉ chạy thử N lô")
    a = ap.parse_args()
    random.seed(7)
    pool = KeyPool(ROOT / "api.txt")
    rows = load(a.domain)
    labels = sorted({r[3] for r in rows})
    by = defaultdict(list)
    for r in rows:
        by[(r[1], r[3])].append(r[2])
    out_path = DATA / f"augmented_{a.domain}.csv"
    done, seen = Counter(), {norm(r[2]) for r in rows}
    if out_path.exists():  # chạy tiếp
        for r in csv.DictReader(out_path.open(encoding="utf-8-sig")):
            done[r["label"]] += 1
            seen.add(norm(r["text"]))
    jobs = []
    for label, n in TARGETS[a.domain].items():
        evs = [(e, len(v)) for (e, l), v in by.items() if l == label and len(v) >= 3]
        if not evs:
            continue
        # chọn sự kiện theo tỷ lệ số mẫu thật của nhãn đó
        for _ in range(math.ceil(max(0, n - done[label]) / (BATCH * KEEP_RATE))):
            e = random.choices([x[0] for x in evs], [x[1] for x in evs])[0]
            jobs.append((e, label, random.sample(by[(e, label)], min(N_EXAMPLES, len(by[(e, label)])))))
    if a.limit_batches:
        jobs = jobs[: a.limit_batches]
    print(f"{a.domain}: đã có {dict(done)}; {len(jobs)} lô = {2 * len(jobs)} request "
          f"(key gemini: {len(pool.keys['gemini'])})", flush=True)
    if not jobs:
        return
    new = not out_path.exists()
    kept = Counter()
    with out_path.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["comment_id", "event_id", "text", "label", "is_synthetic", "generator"])
        for e, label, examples in jobs:
            if done[label] + kept[label] >= TARGETS[a.domain][label]:
                continue
            try:
                res = make_batch(pool, e, label, examples, labels)
            except Exhausted as ex:
                print(f"DỪNG: hết key {ex}. Chạy lại sau để làm tiếp.", flush=True)
                break
            except Exception as err:  # lỗi lô (mạng/JSON): bỏ lô này, không retry mù
                print("lỗi lô:", err, flush=True)
                continue
            for t in res:
                n = norm(t)
                if n in seen or any(jaccard(n, s) > 0.8 for s in list(seen)[-3000:]):
                    continue
                if done[label] + kept[label] >= TARGETS[a.domain][label]:
                    break
                seen.add(n)
                kept[label] += 1
                w.writerow([f"syn_{a.domain}_{label}_{done[label] + kept[label]:04d}", e, t.strip(), label, True, GEN_MODEL])
            f.flush()
            print(f"  lô: sinh/giữ {len(res)}; tổng đã giữ {dict(kept)}", flush=True)
    print(f"xong. request đã gọi: {dict(pool.used)}; còn thiếu: "
          f"{ {l: max(0, n - done[l] - kept[l]) for l, n in TARGETS[a.domain].items()} }", flush=True)


if __name__ == "__main__":
    main()
