"""Gộp dữ liệu đã cào (common.jsonl của các link "done") thành file sự kiện định dạng chính thức
cho analysis_new (cây comment -> replies lồng nhau, 1 file / mã sự kiện).

    python ingestion/crawled_posts_to_analysis_events.py [--sheet FB_Crawl_skills/data/cao.xlsx] [--out data/crawled-events]

Đầu vào mỗi link: FB_Crawl_skills/data/posts/<slug>/common.jsonl (+ post.json nếu có), các dòng:
    {comment_id, event_id, post_id, platform, author_id, reply_to_id, ts, text}
Đầu ra <out>/<event_id>.json:
    {id_content, event_name, sort_mode, post_content,
     comments: [{comment_id, order, text, likes, reply_count, reply_to_id, post_id, ts, replies: [...]}]}
Crawler không lấy số like -> likes = 0; reply_count = số reply trực tiếp lấy được.
reply_to_id trỏ tới comment không có trong dữ liệu -> coi là comment cấp 1.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crawl_links_from_sheet import DEFAULT_SHEET, ROOT, latest_common, post_folder  # noqa: E402
from crawl_sheet_io import DONE, CrawlSheet  # noqa: E402

SORT_MODE = "all_comments"  # crawler chuyển bộ lọc sang "Tất cả bình luận"


def read_jsonl(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_tree(rows: list) -> list:
    """Danh sách phẳng (có reply_to_id) -> cây lồng nhau; giữ thứ tự xuất hiện, bỏ comment_id trùng."""
    nodes, order = {}, []
    for r in rows:
        cid = str(r.get("comment_id") or "")
        if not cid or cid in nodes:
            continue
        nodes[cid] = {"comment_id": cid, "text": r.get("text") or "", "likes": 0,
                      "reply_to_id": r.get("reply_to_id"), "post_id": r.get("post_id"),
                      "author_id": r.get("author_id"), "ts": r.get("ts"), "replies": []}
        order.append(cid)

    children, roots = defaultdict(list), []
    for cid in order:
        pid = nodes[cid]["reply_to_id"]
        pid = str(pid) if pid else None
        if pid and pid in nodes and pid != cid:
            children[pid].append(cid)
        else:
            roots.append(cid)

    def attach(cid, seen):
        n = nodes[cid]
        kids = [k for k in children[cid] if k not in seen]
        seen.update(kids)
        n["replies"] = [attach(k, seen) for k in kids]
        for i, child in enumerate(n["replies"], 1):
            child["order"] = i
        n["reply_count"] = len(n["replies"])
        return n

    seen = set(roots)
    tree = [attach(cid, seen) for cid in roots]
    for i, c in enumerate(tree, 1):
        c["order"] = i
        c["reply_to_id"] = None
    return tree


def post_text(folder: Path, page: str) -> str:
    p = folder / "post.json"
    if not p.exists():
        return ""
    try:
        text = (json.loads(p.read_text(encoding="utf-8")).get("text") or "").strip()
    except (OSError, ValueError):
        return ""
    return f"[{page}] {text}" if text else ""


def build_events(rows: list) -> dict:
    """{event_id: dữ liệu sự kiện} từ các dòng done; in cảnh báo link done mà thiếu file."""
    by_event = defaultdict(list)
    for r in rows:
        if r["status"] == DONE:
            by_event[r["event_id"]].append(r)
    events = {}
    for eid, links in by_event.items():
        flat, posts = [], []
        for r in links:
            folder = post_folder(r["url"])
            f = latest_common(folder)
            if f is None:
                print(f"⚠️  {eid}: link done nhưng thiếu common*.jsonl trong {folder}")
                continue
            flat.extend(read_jsonl(f))
            posts.append(post_text(folder, r["page"]))
        tree = build_tree(flat)
        events[eid] = {"id_content": eid, "event_name": links[0]["event_name"], "sort_mode": SORT_MODE,
                       "post_content": "\n\n".join(p for p in posts if p), "comments": tree}
    return events


def count_nodes(comments: list) -> int:
    return sum(1 + count_nodes(c["replies"]) for c in comments)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", default=str(DEFAULT_SHEET))
    ap.add_argument("--out", default=str(ROOT / "data" / "crawled-events"))
    args = ap.parse_args()

    rows = CrawlSheet.load(args.sheet).rows()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for eid, ev in build_events(rows).items():
        n_pending = sum(r["event_id"] == eid and r["status"] != DONE for r in rows)
        path = out / f"{eid}.json"
        path.write_text(json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
        note = f" (còn {n_pending} link pending)" if n_pending else ""
        print(f"💾 {path}: {count_nodes(ev['comments'])} comment, {len(ev['comments'])} cụm{note}")


if __name__ == "__main__":
    main()
