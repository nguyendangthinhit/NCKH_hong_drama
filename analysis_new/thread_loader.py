"""Đọc dữ liệu sự kiện và dựng cụm.

Định dạng CHÍNH THỨC (từ 2026-11-17, ví dụ data/sample/showbiz_068 (1).json) — cây lồng nhau:
    {"id_content", "event_name", "sort_mode", "post_content",
     "comments": [{"comment_id", "order", "text", "likes", "reply_count",
                   "replies": [{"comment_id", "reply_to_id", ..., "replies": [...]}]}]}
(Định dạng B phẳng cũ không còn được đọc — user chốt 2026-11-17.)

Chuẩn hoá về dạng nội bộ: event_id/name/post_title + comments phẳng có id/parent_id.
Cụm = một comment cấp 1 + toàn bộ reply con cháu (duyệt theo chiều sâu, giữ cấp bậc).
"""

import json
from collections import defaultdict
from pathlib import Path

from analysis_new.trash_rule import is_trash_rule

_NULLS = (None, "", "None", "none", "null")


def _is_null(v) -> bool:
    return v in _NULLS


def to_int(v) -> int:
    """likes/reply_count trong định dạng B là chuỗi ('145'); đổi an toàn sang int."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def flatten_nested(comments) -> list:
    """Duỗi cây `replies` lồng nhau thành danh sách phẳng (thứ tự DFS) có id/parent_id.

    parent_id lấy theo vị trí trong cây (đáng tin hơn reply_to_id nếu hai giá trị lệch nhau).
    Giữ nguyên các trường gốc trừ `replies`.
    """
    flat, stack = [], [(c, None) for c in reversed(comments)]
    while stack:
        c, parent = stack.pop()
        if not isinstance(c, dict):
            continue
        cid = str(c.get("comment_id"))
        flat.append({**{k: v for k, v in c.items() if k != "replies"},
                     "id": cid, "parent_id": parent})
        stack.extend((r, cid) for r in reversed(c.get("replies") or []))
    return flat


def normalize_event(data: dict, fallback_id: str) -> dict:
    """Đưa định dạng chính thức (cây lồng nhau) về dạng nội bộ; định dạng khác thì báo lỗi."""
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list) or (comments and "comment_id" not in comments[0]):
        raise ValueError(f"{fallback_id}: không đúng định dạng chính thức "
                         "(cần id_content/event_name/post_content + comments[] có comment_id/replies)")
    return {"event_id": data.get("id_content") or fallback_id,
            "name": data.get("event_name", ""), "post_title": data.get("post_content", ""),
            "sort_mode": data.get("sort_mode"), "comments": flatten_nested(comments)}


def load_event(path) -> dict:
    """Đọc một file sự kiện định dạng chính thức và chuẩn hoá về dạng nội bộ."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return normalize_event(data, Path(path).stem)


def list_event_files(input_path) -> list:
    """Một file .json hoặc mọi file .json trong thư mục (sắp theo tên)."""
    p = Path(input_path)
    if p.is_file():
        return [p]
    return sorted(x for x in p.glob("*.json") if x.is_file())


def build_clusters(event: dict) -> list:
    """Trả danh sách cụm; mỗi cụm {"root_id", "nodes": [...]} với node theo thứ tự duyệt DFS.

    Comment có parent_id không tìm thấy (hoặc nằm trong vòng lặp) được coi là cấp 1, gắn cờ orphan.
    id trùng: giữ bản đầu tiên.
    """
    by_id, order = {}, []
    for c in event.get("comments", []):
        cid = str(c.get("id"))
        if cid not in by_id:
            by_id[cid] = c
            order.append(cid)

    children = defaultdict(list)
    roots = []
    for cid in order:
        pid = by_id[cid].get("parent_id")
        pid = None if _is_null(pid) else str(pid)
        if pid is None or pid not in by_id or pid == cid:
            roots.append((cid, pid is not None))
        else:
            children[pid].append(cid)

    visited, clusters = set(), []

    def walk(root_id, orphan):
        nodes, stack = [], [(root_id, 1, None)]
        while stack:
            cid, level, parent = stack.pop()
            if cid in visited:
                continue
            visited.add(cid)
            c = by_id[cid]
            nodes.append({
                "id": cid, "parent_id": parent, "level": level,
                "text": c.get("text") or "", "likes": to_int(c.get("likes")),
                "reply_count": to_int(c.get("reply_count")),
                "rule_trash": is_trash_rule(c.get("text")),
                "orphan": orphan and level == 1,
            })
            # đảo ngược để pop ra đúng thứ tự gốc
            stack.extend((k, level + 1, cid) for k in reversed(children.get(cid, [])))
        clusters.append({"root_id": root_id, "nodes": nodes})

    for cid, orphan in roots:
        walk(cid, orphan)
    for cid in order:  # comment kẹt trong vòng lặp parent_id
        if cid not in visited:
            walk(cid, True)
    return clusters
