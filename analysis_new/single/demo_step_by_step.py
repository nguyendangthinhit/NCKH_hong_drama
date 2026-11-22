"""Demo TỪNG BƯỚC luồng phân tích đơn luồng trên vài cụm comment của 1 sự kiện (in ra màn hình).

Chỉ đọc, không ghi file kết quả. Gọi API thật: 1 request (thêm 1 request tổng hợp nếu là Giáo dục).
    python -X utf8 -m analysis_new.single.demo_step_by_step "data/sample/showbiz_068 (1).json" --orders 9 39
    python -X utf8 -m analysis_new.single.demo_step_by_step <file.json> --first 3 [--domain education]
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analysis_new import event_pipeline as ep, prompts  # noqa: E402
from analysis_new.config import DOMAINS  # noqa: E402
from analysis_new.mmo_client import LLMExhausted, MmoClient  # noqa: E402
from analysis_new.request_planner import parse_label_response  # noqa: E402
from analysis_new.thread_loader import normalize_event  # noqa: E402


def pick_comments(raw: dict, orders, first: int) -> None:
    """Giữ lại các comment cấp 1 theo `order` (hoặc N comment đầu) cùng toàn bộ reply của chúng."""
    comments = raw.get("comments") or []
    raw["comments"] = [c for c in comments if c.get("order") in set(orders)] if orders else comments[:first]
    if not raw["comments"]:
        sys.exit("❌ Không có comment nào khớp --orders/--first")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="File sự kiện định dạng chính thức (.json)")
    ap.add_argument("--orders", type=int, nargs="+", help="order của các comment cấp 1 muốn thử")
    ap.add_argument("--first", type=int, default=2, help="Không có --orders: lấy N comment cấp 1 đầu")
    ap.add_argument("--domain", choices=list(DOMAINS))
    args = ap.parse_args()

    try:
        raw = json.loads(Path(args.input).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"❌ Không đọc được {args.input}: {e}")
    pick_comments(raw, args.orders, args.first)

    print("=== B1. Đọc file + duỗi cây replies thành danh sách phẳng (id/parent_id) ===")
    event = normalize_event(raw, Path(args.input).stem)
    for c in event["comments"]:
        print(f"  id=...{c['id'][-12:]}  parent=...{str(c['parent_id'])[-12:]}  text={c['text'][:70]!r}")

    domain = ep.detect_domain(event, args.domain)
    print(f"\n=== B2. Lĩnh vực: {domain} ===")

    print("\n=== B3. Dựng cụm (comment cấp 1 + reply) + lọc rác bằng rule ===")
    clusters, batches = ep.prepare_event(event)
    for cl in clusters:
        for n in cl["nodes"]:
            print(f"  {'  ' * (n['level'] - 1)}cấp {n['level']} rule_trash={n['rule_trash']}: {n['text'][:70]!r}")
    print(f"  -> {len(clusters)} cụm, gom thành {len(batches)} request")
    if not batches:
        print("Toàn bộ là rác theo rule, không cần gọi LLM.")
        return

    print("\n=== B4. Prompt gửi LLM (phần cụm; chỉ demo request đầu) ===")
    batch = batches[0]
    prompt, id_map, cluster_map = prompts.build_label_prompt(domain, event, batch)
    print(prompt[prompt.index("### Cụm"):prompt.index("=== QUY TẮC")])

    print("=== B5. Gọi API mmodiary ===")
    client = MmoClient.from_files()
    try:
        text, model = client.complete(prompt)
    except LLMExhausted as e:
        sys.exit(f"❌ {e}")
    print(f"  model={model}\n  raw response:\n{text}\n")

    print("=== B6. Parse + chuẩn hoá nhãn (mã -> tiếng Việt) ===")
    labels, summaries = parse_label_response(domain, text, batch, id_map, cluster_map)
    for cl in batch:
        print(f"  Cụm ...{cl['root_id'][-12:]}  summary: {summaries.get(cl['root_id'], '')}")
        for n in cl["nodes"]:
            print(f"    {'  ' * (n['level'] - 1)}{n['text'][:60]!r} -> {labels[n['id']]}")

    print("\n=== B7. Dựng summary sự kiện (khoá dùng cho insights) ===")
    batch_ids = {cl["root_id"] for cl in batch}
    clusters = [cl for cl in clusters if cl["root_id"] in batch_ids or not any(
        not n["rule_trash"] for n in cl["nodes"])]
    _, summary = ep.finalize_event(client, domain, event, clusters, labels, summaries)
    keys = [k for k in summary if k not in ("id_content", "event_name", "top_comments", "controversial_threads")]
    print(json.dumps({k: summary[k] for k in keys}, ensure_ascii=False, indent=2))
    print(f"\nRequests đã gửi: {client.requests_sent}")


if __name__ == "__main__":
    main()
