"""Các bước dùng chung cho bản đơn luồng và bản PySpark.

  prepare_event   -> cụm + danh sách request (chưa gọi API)
  label_batch     -> 1 request LLM cho 1 nhóm cụm
  finalize_event  -> gộp nhãn, (Giáo dục) 1 request tổng hợp sự kiện, dựng full + summary
"""

import json
from datetime import datetime
from pathlib import Path

from analysis_new import prompts
from analysis_new.config import DOMAINS
from analysis_new.request_planner import parse_json_loose, parse_label_response, plan_requests, trash_label
from analysis_new.result_builder import build_full, build_summary, education_counts_examples
from analysis_new.thread_loader import build_clusters

BAD_LABEL_WARN_RATIO = 0.2
BAD_LABEL_FAIL_RATIO = 0.5  # quá ngưỡng này: coi request là lỗi, không ghi file sự kiện


class BadLabelResponse(RuntimeError):
    """Response của LLM có quá nhiều nhãn hỏng/thiếu: sự kiện không được ghi, chạy lại sẽ làm tiếp."""


def detect_domain(event: dict, override=None) -> str:
    """--domain nếu có; không thì đoán từ tiền tố event_id (showbiz_/education_)."""
    if override:
        return override
    eid = str(event.get("event_id", ""))
    for d in DOMAINS:
        if eid.startswith(d):
            return d
    raise ValueError(f"Không đoán được lĩnh vực từ event_id '{eid}'; truyền --domain")


def prepare_event(event: dict) -> tuple:
    """Trả (clusters, batches). batches = list các nhóm cụm, mỗi nhóm là 1 request."""
    clusters = build_clusters(event)
    return clusters, plan_requests(clusters)


def count_requests(domain: str, batches) -> int:
    """Số request dự kiến của một sự kiện (Giáo dục thêm 1 request tổng hợp)."""
    return len(batches) + (1 if domain == "education" and batches else 0)


def label_batch(client, domain: str, event: dict, batch, bad_dir=None) -> tuple:
    """Gửi 1 request; trả (labels, summaries, model). LLMExhausted được ném tiếp lên.

    >50% nhãn hỏng/thiếu -> lưu nguyên văn response vào bad_dir, báo model hỏng cho client
    (lần sau dùng model kế) rồi raise BadLabelResponse.
    """
    prompt, id_map, cluster_map = prompts.build_label_prompt(domain, event, batch)
    text, model = client.complete(prompt)
    labels, summaries = parse_label_response(domain, text, batch, id_map, cluster_map)
    # Đo thật 2026-11-17: model đôi khi trả nhãn méo chữ -> fallback hàng loạt.
    bad = sum(1 for v in labels.values() if v["label_source"].startswith("fallback"))
    asked = sum(1 for c in batch for n in c["nodes"] if not n["rule_trash"])
    ratio = bad / asked if asked else 0
    if ratio > BAD_LABEL_FAIL_RATIO:
        saved = _save_bad_response(bad_dir, event.get("event_id"), model, text)
        if hasattr(client, "report_bad_output"):
            client.report_bad_output(f"{bad}/{asked} nhãn hỏng/thiếu")
        raise BadLabelResponse(f"{event.get('event_id')}: {bad}/{asked} nhãn hỏng/thiếu ({model})"
                               + (f"; response lưu tại {saved}" if saved else ""))
    if ratio > BAD_LABEL_WARN_RATIO:
        print(f"  ⚠️  {event.get('event_id')}: {bad}/{asked} nhãn hỏng/thiếu ({model})", flush=True)
    return labels, summaries, model


def _save_bad_response(bad_dir, event_id, model, text):
    """Lưu nguyên văn response hỏng để soi; lỗi ghi file không được che lỗi gốc."""
    if not bad_dir:
        return None
    try:
        path = Path(bad_dir) / "_bad_responses" / (
            f"{event_id}-{datetime.now():%Y%m%d-%H%M%S}-{model.replace('/', '_')}.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path
    except OSError:
        return None


def finalize_event(client, domain: str, event: dict, clusters, labels: dict, summaries: dict) -> tuple:
    """Trả (full, summary). Cụm không cần LLM (toàn rác) được gán nhãn rule ở đây."""
    for cl in clusters:
        for n in cl["nodes"]:
            labels.setdefault(n["id"], trash_label(domain, "rule"))
    full = build_full(domain, event, clusters, labels, summaries)
    digest = None
    if domain == "education" and client is not None and any(
            c["label_source"] == "llm" for c in full["comments"]):
        counts, examples = education_counts_examples(full)
        prompt = prompts.build_event_summary_prompt(
            event, counts, examples, [s for s in summaries.values() if s])
        text, _ = client.complete(prompt)
        digest = parse_json_loose(text) if text else None
        digest = digest if isinstance(digest, dict) else None
    return full, build_summary(domain, full, digest)


def output_paths(output_dir, event_id) -> tuple:
    out = Path(output_dir)
    return out / "full" / f"{event_id}.json", out / "summary" / f"{event_id}.json"


def is_done(output_dir, event_id) -> bool:
    return all(p.exists() for p in output_paths(output_dir, event_id))


def write_outputs(output_dir, full: dict, summary: dict) -> None:
    """Ghi full trước, summary sau; summary có mặt nghĩa là sự kiện đã xong (dùng để resume)."""
    full_path, summary_path = output_paths(output_dir, full["event_id"])
    for path, data in ((full_path, full), (summary_path, summary)):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def write_dry_run_prompt(output_dir, domain: str, event: dict, batches) -> Path:
    """Ghi prompt của request đầu tiên ra file để xem trước, không gọi API."""
    path = Path(output_dir) / "_dry_run" / f"{event['event_id']}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    prompt = prompts.build_label_prompt(domain, event, batches[0])[0] if batches else "(không có request)"
    path.write_text(prompt, encoding="utf-8")
    return path
