"""
show_log.py
-----------
Xem lịch sử các lần chạy analyze script.

Cách dùng:
    python3 show_log.py <output_dir>
    python3 show_log.py <output_dir> --last     # chỉ xem session cuối
    python3 show_log.py <output_dir> --files    # xem chi tiết từng file

Ví dụ:
    python3 show_log.py .data\process_showbiz\analyzed_data
"""

import json
import os
import sys


def fmt_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def load_logs(output_dir):
    log_path = os.path.join(output_dir, "run_log.jsonl")
    if not os.path.exists(log_path):
        print(f"❌ Không tìm thấy log tại: {log_path}")
        sys.exit(1)

    sessions = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sessions.append(json.loads(line))
                except:
                    pass
    return sessions


def print_session(s, show_files=False):
    stop_icon = {
        "completed":       "🎉",
        "quota_exhausted": "⛔",
        "interrupted":     "⚠️"
    }.get(s.get("stop_reason", ""), "❓")

    print(f"\n{'─'*55}")
    print(f"Session : {s['session_id']}")
    print(f"Bắt đầu : {s['started_at']}")
    print(f"Kết thúc: {s['finished_at']}")
    print(f"Thời gian: {s.get('elapsed_human', fmt_duration(s.get('elapsed_seconds', 0)))}")
    print(f"Tiến độ : {s['processed']}/{s['total_files']} file "
          f"({s['processed']/s['total_files']*100:.1f}%)")
    print(f"Còn lại : {s['remaining']} file")
    print(f"Tốc độ  : ~{s.get('avg_per_file_s', 0)}s/file")
    print(f"Dừng    : {stop_icon} {s.get('stop_reason', 'unknown')}")

    if show_files:
        if s.get("files_done"):
            print(f"\n✅ Đã xử lý ({len(s['files_done'])}):")
            for f in s["files_done"]:
                if isinstance(f, dict):
                    print(f"   {f['id_content']} ({fmt_duration(f.get('elapsed_s', 0))})")
                else:
                    print(f"   {f}")

        if s.get("files_remaining"):
            print(f"\n⏳ Còn lại ({len(s['files_remaining'])}):")
            for f in s["files_remaining"]:
                print(f"   {f}")


def main():
    if len(sys.argv) < 2:
        print("Dùng: python3 show_log.py <output_dir> [--last] [--files]")
        sys.exit(1)

    output_dir  = sys.argv[1]
    show_last   = "--last"  in sys.argv
    show_files  = "--files" in sys.argv

    sessions = load_logs(output_dir)

    if not sessions:
        print("⚠️  Chưa có session nào được ghi log.")
        return

    print(f"📋 Tìm thấy {len(sessions)} session trong log")

    if show_last:
        print_session(sessions[-1], show_files)
    else:
        for s in sessions:
            print_session(s, show_files)

    # Tổng kết
    total_processed = sum(s["processed"] for s in sessions)
    total_time      = sum(s.get("elapsed_seconds", 0) for s in sessions)
    print(f"\n{'='*55}")
    print(f"📊 TỔNG CỘC {len(sessions)} sessions")
    print(f"   Tổng file đã xử lý : {total_processed}")
    print(f"   Tổng thời gian chạy: {fmt_duration(total_time)}")
    last = sessions[-1]
    status_str = "hoàn tất" if last["stop_reason"] == "completed" else f"còn {last['remaining']} file"
    print(f"   Trạng thái hiện tại: {last['processed']}/{last['total_files']} ({status_str})")


if __name__ == "__main__":
    main()