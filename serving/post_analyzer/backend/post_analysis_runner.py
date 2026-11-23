"""Phân tích 1 bài bằng analysis_new (giống run_analysis_single.run_event) nhưng báo tiến độ từng request.

Khác bản đơn luồng: request trả nhãn hỏng được thử lại (client đã xoay sang model khác) thay vì bỏ cả sự kiện.
"""

import settings  # noqa: F401  (thêm gốc repo vào sys.path)
from analysis_new import event_pipeline as ep  # noqa: E402


def plan(event: dict, domain: str) -> tuple:
    """(clusters, batches, n_requests) — n_requests gồm request tổng hợp của Giáo dục."""
    clusters, batches = ep.prepare_event(event)
    return clusters, batches, ep.count_requests(domain, batches)


def label_with_retry(client, domain, event, batch, bad_dir, retries: int) -> tuple:
    for attempt in range(retries + 1):
        try:
            return ep.label_batch(client, domain, event, batch, bad_dir=bad_dir)
        except ep.BadLabelResponse:
            if attempt == retries:
                raise


def analyze(client, event: dict, domain: str, out_dir, on_progress=None, retries: int = settings.LABEL_RETRIES):
    """Chạy hết các request, ghi full/ + summary/ vào out_dir; trả (full, summary).

    on_progress(done, total) gọi sau mỗi request (kể cả request tổng hợp)."""
    clusters, batches, total = plan(event, domain)
    labels, summaries = {}, {}
    report = on_progress or (lambda done, total: None)
    report(0, total)
    for i, batch in enumerate(batches, 1):
        lab, summ, _ = label_with_retry(client, domain, event, batch, out_dir, retries)
        labels.update(lab)
        summaries.update(summ)
        report(i, total)
    full, summary = ep.finalize_event(client, domain, event, clusters, labels, summaries)
    ep.write_outputs(out_dir, full, summary)
    report(total, total)
    return full, summary
