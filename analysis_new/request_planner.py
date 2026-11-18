"""Gom cụm thành request (tối đa MAX_COMMENTS_PER_REQUEST comment/request) và đọc kết quả LLM."""

import json
import re

from analysis_new import config


def needs_llm(cluster) -> bool:
    """Cụm toàn rác (theo rule) thì không cần gọi LLM."""
    return any(not n["rule_trash"] for n in cluster["nodes"])


def plan_requests(clusters, max_comments=None) -> list:
    """Gom tham lam theo thứ tự; cụm lớn hơn giới hạn đi riêng một request (không cắt cụm)."""
    max_comments = max_comments or config.MAX_COMMENTS_PER_REQUEST
    batches, cur, size = [], [], 0
    for cl in filter(needs_llm, clusters):
        n = len(cl["nodes"])
        if cur and size + n > max_comments:
            batches.append(cur)
            cur, size = [], 0
        cur.append(cl)
        size += n
    if cur:
        batches.append(cur)
    return batches


def parse_json_loose(text):
    """Đọc JSON từ trả lời LLM: bỏ <think>, bỏ ```json, lấy khối {...} ngoài cùng."""
    if not text:
        return None
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


_ITEM_RE = re.compile(r'\{"id"\s*:\s*"(K\d+\.\d+)"[^{}]*\}')
_SUMMARY_RE = re.compile(r'"cluster"\s*:\s*"(K\d+)"\s*,\s*"summary"\s*:\s*"(.*?)"\s*[,}]', re.S)


def salvage_groups(text) -> list:
    """Vớt dữ liệu từ JSON hỏng (đo thật 2026-11-17: summary chứa dấu " chưa escape làm cả response
    parse lỗi dù nhãn vẫn đủ). Comment item chỉ gồm mã nên đọc từng item bằng regex là an toàn."""
    if not text:
        return []
    groups = []
    for cid, summary in _SUMMARY_RE.findall(text):
        groups.append({"cluster": cid, "summary": summary})
    items = []
    for m in _ITEM_RE.finditer(text):
        try:
            items.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            continue
    if items:  # parse_label_response chỉ cần comments, không cần gắn cụm
        groups.append({"cluster": "", "comments": items})
    return groups


def fallback_label(domain, source="fallback") -> dict:
    cfg = config.domain_cfg(domain)
    out = {"is_trash": False, cfg["label_field"]: cfg["fallback"], "label_source": source}
    if cfg["toxic"]:
        out.update(toxic=False, toxic_type=None)
    return out


def trash_label(domain, source) -> dict:
    cfg = config.domain_cfg(domain)
    out = {"is_trash": True, cfg["label_field"]: None, "label_source": source}
    if cfg["toxic"]:
        out.update(toxic=None, toxic_type=None)
    return out


def _clean_item(domain, item) -> dict:
    """Chuẩn hoá một nhãn LLM; nhãn ngoài bộ nhãn thì về fallback (ghi nguồn)."""
    cfg = config.domain_cfg(domain)
    if item.get("is_trash") is True:
        return trash_label(domain, "llm")
    label = config.decode(item.get(cfg["label_field"]), cfg["codes"])
    if label is None:
        return fallback_label(domain, "fallback_invalid_label")
    out = {"is_trash": False, cfg["label_field"]: label, "label_source": "llm"}
    if cfg["toxic"]:
        toxic = item.get("toxic") is True
        tt = config.decode(item.get("toxic_type"), config.TOXIC_CODES)
        out.update(toxic=toxic, toxic_type=tt if toxic else None)
    return out


def parse_label_response(domain, text, batch, id_map, cluster_map) -> tuple:
    """Trả (labels {comment_id: nhãn}, summaries {root_id: str}) cho mọi comment trong batch.

    Comment rác theo rule giữ nhãn rule; comment LLM bỏ sót hoặc trả sai thì về fallback.
    """
    labels, summaries = {}, {}
    data = parse_json_loose(text)
    groups = data.get("clusters") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        groups = salvage_groups(text)
    for g in groups if isinstance(groups, list) else []:
        if not isinstance(g, dict):
            continue
        root = cluster_map.get(str(g.get("cluster", "")).strip())
        if root and isinstance(g.get("summary"), str):
            summaries[root] = g["summary"].strip()
        for item in g.get("comments") or []:
            cid = id_map.get(str(item.get("id", "")).strip()) if isinstance(item, dict) else None
            if cid:
                labels[cid] = _clean_item(domain, item)

    for cl in batch:
        for n in cl["nodes"]:
            if n["rule_trash"]:
                labels[n["id"]] = trash_label(domain, "rule")
            elif n["id"] not in labels:
                labels[n["id"]] = fallback_label(domain, "fallback_missing")
    return labels, summaries
