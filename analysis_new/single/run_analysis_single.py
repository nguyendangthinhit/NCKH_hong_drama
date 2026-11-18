"""Bản ĐƠN LUỒNG: phân tích bình luận theo cụm bằng LLM (mmodiary), từng request một.

Mặc định chỉ ước tính số request + ghi prompt mẫu (không tốn tiền). Thêm --yes mới gọi API.
    python -m analysis_new.single.run_analysis_single <input_file_or_dir> <output_dir> [--domain showbiz]
    python -m analysis_new.single.run_analysis_single <input> <output> --yes [--max-requests 50]

Đầu ra: <output>/full/<event_id>.json, <output>/summary/<event_id>.json, <output>/run_log.jsonl.
Sự kiện đã có summary thì bỏ qua (chạy lại để tiếp tục khi bị dừng giữa chừng).
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis_new import event_pipeline as ep  # noqa: E402
from analysis_new.config import DOMAINS  # noqa: E402
from analysis_new.mmo_client import LLMExhausted, MmoClient  # noqa: E402
from analysis_new.thread_loader import list_event_files, load_event  # noqa: E402


def plan(files, output_dir, domain_override):
    """Đọc mọi sự kiện chưa xong; trả list (event, domain, clusters, batches)."""
    jobs = []
    for f in files:
        event = load_event(f)
        if ep.is_done(output_dir, event["event_id"]):
            print(f"⏭️  Bỏ qua (đã có): {event['event_id']}")
            continue
        domain = ep.detect_domain(event, domain_override)
        clusters, batches = ep.prepare_event(event)
        jobs.append((event, domain, clusters, batches))
    return jobs


def print_estimate(jobs) -> int:
    total = 0
    for event, domain, clusters, batches in jobs:
        n_req = ep.count_requests(domain, batches)
        n_cmt = sum(len(c["nodes"]) for c in clusters)
        n_trash = sum(n["rule_trash"] for c in clusters for n in c["nodes"])
        print(f"  {event['event_id']} [{domain}]: {n_cmt} comment, {len(clusters)} cụm, "
              f"{n_trash} rác rule → {n_req} request")
        total += n_req
    print(f"📊 Tổng dự kiến: {total} request cho {len(jobs)} sự kiện")
    return total


def run_event(client, output_dir, event, domain, clusters, batches) -> None:
    """Gửi lần lượt các request; BadLabelResponse làm sự kiện dừng, không ghi file."""
    labels, summaries = {}, {}
    for i, batch in enumerate(batches, 1):
        lab, summ, model = ep.label_batch(client, domain, event, batch, bad_dir=output_dir)
        labels.update(lab)
        summaries.update(summ)
        print(f"  ✅ request {i}/{len(batches)} ({model})", flush=True)
    full, summary = ep.finalize_event(client, domain, event, clusters, labels, summaries)
    ep.write_outputs(output_dir, full, summary)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output_dir")
    ap.add_argument("--domain", choices=list(DOMAINS))
    ap.add_argument("--yes", action="store_true", help="Gọi API thật (mặc định chỉ ước tính)")
    ap.add_argument("--max-requests", type=int, default=0,
                    help="Từ chối chạy nếu dự kiến vượt số này (0 = không giới hạn)")
    args = ap.parse_args()

    jobs = plan(list_event_files(args.input), args.output_dir, args.domain)
    total = print_estimate(jobs)
    if not args.yes:
        for event, domain, _, batches in jobs:
            ep.write_dry_run_prompt(args.output_dir, domain, event, batches)
        print(f"🔎 Chưa gọi API. Prompt mẫu: {Path(args.output_dir) / '_dry_run'}. Thêm --yes để chạy.")
        return
    if args.max_requests and total > args.max_requests:
        sys.exit(f"❌ Dự kiến {total} request > --max-requests {args.max_requests}; dừng.")

    client = MmoClient.from_files()
    started, done, failed, stop_reason = time.time(), [], [], "completed"
    try:
        for event, domain, clusters, batches in jobs:
            print(f"\n🔄 {event['event_id']} ({len(batches)} request)")
            try:
                run_event(client, args.output_dir, event, domain, clusters, batches)
                done.append(event["event_id"])
            except ep.BadLabelResponse as e:  # sự kiện không ghi file; chạy lại sẽ làm tiếp
                failed.append(event["event_id"])
                print(f"  ❌ Không ghi file: {e}")
    except LLMExhausted as e:
        stop_reason = f"llm_exhausted: {e}"
        print(f"\n❌ {e}")
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    finally:
        log = {"mode": "single", "finished_at": datetime.now().isoformat(timespec="seconds"),
               "elapsed_s": round(time.time() - started, 1), "requests_sent": client.requests_sent,
               "events_done": done, "events_failed": failed, "events_planned": len(jobs), "stop_reason": stop_reason}
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(args.output_dir) / "run_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log, ensure_ascii=False) + "\n")
        print(f"\n💾 {len(done)}/{len(jobs)} sự kiện, {client.requests_sent} request đã gửi ({stop_reason})")


if __name__ == "__main__":
    main()
