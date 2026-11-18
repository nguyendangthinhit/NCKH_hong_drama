"""Bản PYSPARK: cùng luồng với bản đơn luồng, nhưng chạy song song trên Spark (local[N]).

    sự kiện ──flatMap(dựng cụm + gom request)──> request ──mapPartitions(gọi LLM)──> nhãn
      └──────────────── join theo event_id ─────────────────────────────────────────┘
                      └─mapPartitions(gộp nhãn, tổng hợp sự kiện)─> full + summary (driver ghi file)

Mỗi partition có một client riêng; N partition = N request đồng thời.
Mặc định chỉ đếm request qua Spark (không tốn tiền). Thêm --yes mới gọi API.
    .venv-ml/Scripts/python.exe -m analysis_new.spark.run_analysis_spark <input> <output> [--threads 4] [--yes]
Sự kiện có request lỗi/hết số dư thì không ghi file; chạy lại sẽ làm tiếp các sự kiện còn thiếu.
"""

import argparse
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Python worker của Spark cần import được analysis_new
os.environ["PYTHONPATH"] = os.pathsep.join(
    p for p in (str(PROJECT_ROOT), os.environ.get("PYTHONPATH", "")) if p)

from analysis_new import event_pipeline as ep  # noqa: E402
from analysis_new.config import DOMAINS  # noqa: E402
from analysis_new.mmo_client import LLMExhausted, MmoClient  # noqa: E402
from analysis_new.single.run_analysis_single import plan, print_estimate  # noqa: E402
from analysis_new.thread_loader import list_event_files  # noqa: E402


def _event_requests(job):
    """flatMap: một sự kiện -> các request (event_id, chỉ số, domain, event, nhóm cụm)."""
    event, domain = job
    _, batches = ep.prepare_event(event)
    meta = {k: event.get(k) for k in ("event_id", "name", "post_title")}
    return [(event["event_id"], i, domain, meta, b) for i, b in enumerate(batches)]


def _make_label_partition(client_factory, bad_dir=None):
    def label_partition(rows):
        client, exhausted = None, None
        for eid, idx, domain, meta, batch in rows:
            if exhausted:
                yield eid, {"idx": idx, "error": exhausted}
                continue
            try:
                client = client or client_factory()
                labels, summaries, model = ep.label_batch(client, domain, meta, batch, bad_dir=bad_dir)
                yield eid, {"idx": idx, "labels": labels, "summaries": summaries, "model": model}
            except LLMExhausted as e:
                exhausted = str(e)
                yield eid, {"idx": idx, "error": exhausted}
            except Exception as e:  # lỗi bất ngờ chỉ làm hỏng request này
                yield eid, {"idx": idx, "error": f"{type(e).__name__}: {e}"}
    return label_partition


def _make_finalize_partition(client_factory):
    def finalize_partition(rows):
        client = None
        for eid, ((event, domain), results) in rows:
            results = list(results or [])
            clusters, batches = ep.prepare_event(event)
            errors = [r["error"] for r in results if "error" in r]
            if errors or len({r["idx"] for r in results}) != len(batches):
                yield eid, None, None, errors[0] if errors else "thiếu kết quả request"
                continue
            labels, summaries = {}, {}
            for r in sorted(results, key=lambda r: r["idx"]):
                labels.update(r["labels"])
                summaries.update(r["summaries"])
            try:
                if domain == "education" and batches:
                    client = client or client_factory()
                full, summary = ep.finalize_event(client, domain, event, clusters, labels, summaries)
                yield eid, full, summary, None
            except LLMExhausted as e:
                yield eid, None, None, str(e)
    return finalize_partition


def run_spark(jobs, output_dir, n_threads, client_factory):
    """Chạy toàn bộ luồng trên Spark; trả (số sự kiện ghi được, danh sách lỗi)."""
    from preprocessing.spark.spark_session_factory import get_spark

    spark = get_spark(app_name="analysis-new-llm-clusters", n_threads=n_threads)
    try:
        sc = spark.sparkContext
        events = sc.parallelize([(j[0]["event_id"], (j[0], j[1])) for j in jobs], max(1, n_threads))
        requests = events.values().flatMap(_event_requests).repartition(max(1, n_threads))
        labeled = requests.mapPartitions(_make_label_partition(client_factory, output_dir)).groupByKey()
        finished = events.leftOuterJoin(labeled).mapPartitions(
            _make_finalize_partition(client_factory)).collect()
    finally:
        spark.stop()

    written, errors = 0, []
    for eid, full, summary, err in finished:
        if err:
            errors.append((eid, err))
        else:
            ep.write_outputs(output_dir, full, summary)
            written += 1
    return written, errors


def count_requests_spark(jobs, n_threads) -> int:
    """Dry-run: đếm request bằng chính bước flatMap của Spark (kiểm luồng, không gọi API)."""
    from preprocessing.spark.spark_session_factory import get_spark

    spark = get_spark(app_name="analysis-new-dry-run", n_threads=n_threads)
    try:
        rdd = spark.sparkContext.parallelize([(j[0], j[1]) for j in jobs], max(1, n_threads))
        return rdd.flatMap(_event_requests).count()
    finally:
        spark.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output_dir")
    ap.add_argument("--domain", choices=list(DOMAINS))
    ap.add_argument("--threads", type=int, default=4, help="Số partition = số request đồng thời")
    ap.add_argument("--yes", action="store_true", help="Gọi API thật (mặc định chỉ ước tính)")
    ap.add_argument("--max-requests", type=int, default=0)
    args = ap.parse_args()

    jobs = plan(list_event_files(args.input), args.output_dir, args.domain)
    total = print_estimate(jobs)
    if not jobs:
        return
    if not args.yes:
        n_label = count_requests_spark(jobs, args.threads)
        print(f"🔎 Spark đếm {n_label} request gán nhãn (chưa gồm request tổng hợp). Thêm --yes để chạy.")
        return
    if args.max_requests and total > args.max_requests:
        sys.exit(f"❌ Dự kiến {total} request > --max-requests {args.max_requests}; dừng.")

    t0 = time.time()
    written, errors = run_spark(jobs, args.output_dir, args.threads, MmoClient.from_files)
    print(f"\n💾 Ghi {written}/{len(jobs)} sự kiện trong {time.time() - t0:.1f}s")
    for eid, err in errors:
        print(f"  ❌ {eid}: {err}")


if __name__ == "__main__":
    main()
