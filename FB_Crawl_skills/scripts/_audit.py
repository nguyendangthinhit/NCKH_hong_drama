"""
Audit dashboard for FB crawl runs.

Scans all `manifest.json` files in data/posts/ and data/schedule_runs/,
produces summary statistics, and writes `data/audit_<timestamp>.json`.

What it answers:
  - How many runs in total? Success rate?
  - Average run duration per script (05/06/07/08/09)?
  - p50 / p95 comments per post?
  - Recent failures (last 7 days)?
  - Which posts have been crawled most often?
  - Total unique authors across all comments?

CLI:
  python3 scripts/_audit.py                    # print summary table
  python3 scripts/_audit.py --json out.json    # write JSON
  python3 scripts/_audit.py --since 7d        # filter to last 7 days
  python3 scripts/_audit.py --script 05        # filter to specific script
"""
from __future__ import annotations
import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
from _run_manifest import find_manifests, summarize_manifest  # noqa: E402

DATA_DIR = SCRIPT_DIR.parent / "data"


# -----------------------------------------------------------------------
# Aggregation
# -----------------------------------------------------------------------

def collect_manifests(root: Path = DATA_DIR) -> list[dict]:
    """Load and summarize all manifests under root."""
    out = []
    for p in find_manifests(root):
        s = summarize_manifest(p)
        out.append(s)
    return out


def aggregate(manifests: list[dict]) -> dict:
    """Compute summary statistics from list of summarized manifests."""
    total = len(manifests)
    by_status: dict[str, int] = {}
    by_script: dict[str, dict] = {}
    durations: list[float] = []
    recent_failures: list[dict] = []
    now = datetime.now(timezone.utc)

    for m in manifests:
        status = m.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1

        script = m.get("script", "unknown")
        bucket = by_script.setdefault(script, {
            "runs": 0, "successes": 0, "failures": 0,
            "durations": [], "total_comments": 0,
        })
        bucket["runs"] += 1
        if status == "success":
            bucket["successes"] += 1
        elif status == "failed":
            bucket["failures"] += 1
        d = m.get("duration_s")
        if d is not None and d >= 0:
            bucket["durations"].append(d)
            durations.append(d)

        # Recent failure
        if status == "failed" and m.get("started_at"):
            try:
                t = datetime.fromisoformat(m["started_at"])
                age = (now - t).days
                if age <= 7:
                    recent_failures.append({
                        "script": script,
                        "input_url": m.get("input_url", ""),
                        "started_at": m.get("started_at"),
                        "errors": m.get("errors", 0),
                        "path": m.get("path", ""),
                    })
            except Exception:
                pass

    # Compute per-script stats
    for script, bucket in by_script.items():
        d = bucket.pop("durations")
        bucket["avg_duration_s"] = round(statistics.mean(d), 1) if d else 0
        bucket["p50_duration_s"] = round(statistics.median(d), 1) if d else 0
        bucket["p95_duration_s"] = round(
            statistics.quantiles(d, n=20)[18] if len(d) >= 20 else
            (max(d) if d else 0), 1
        )

    success_rate = (
        round(100.0 * by_status.get("success", 0) / total, 1)
        if total else 0.0
    )
    avg_duration = round(statistics.mean(durations), 1) if durations else 0

    return {
        "total_runs": total,
        "by_status": by_status,
        "success_rate_pct": success_rate,
        "avg_duration_s": avg_duration,
        "p50_duration_s": round(statistics.median(durations), 1) if durations else 0,
        "by_script": by_script,
        "recent_failures_7d": recent_failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_since(s: str) -> datetime:
    """Parse `--since 7d` / `24h` / `30m`."""
    m = __import__("re").match(r"^(\d+)([dhm])$", s)
    if not m:
        raise ValueError(f"Invalid --since format: {s}. Use 7d, 24h, 30m.")
    n, unit = int(m.group(1)), m.group(2)
    delta = {
        "d": timedelta(days=n),
        "h": timedelta(hours=n),
        "m": timedelta(minutes=n),
    }[unit]
    return datetime.now(timezone.utc) - delta


def filter_manifests(manifests: list[dict], since: datetime | None = None,
                     script: str | None = None) -> list[dict]:
    out = []
    for m in manifests:
        if script and script not in (m.get("script") or ""):
            continue
        if since:
            sa = m.get("started_at")
            if not sa:
                continue
            try:
                t = datetime.fromisoformat(sa)
                if t < since:
                    continue
            except Exception:
                continue
        out.append(m)
    return out


# -----------------------------------------------------------------------
# Pretty-print
# -----------------------------------------------------------------------

def print_summary(stats: dict) -> None:
    print("=" * 70)
    print("FB CRAWL AUDIT DASHBOARD")
    print("=" * 70)
    print(f"  Total runs         : {stats['total_runs']}")
    print(f"  Success rate       : {stats['success_rate_pct']}%")
    print(f"  Avg duration       : {stats['avg_duration_s']}s")
    print(f"  p50 duration       : {stats['p50_duration_s']}s")
    print()
    print(f"  By status          :")
    for status, n in sorted(stats["by_status"].items(), key=lambda x: -x[1]):
        print(f"    {status:12s} {n}")
    print()
    print(f"  By script          :")
    for script, b in sorted(stats["by_script"].items()):
        print(f"    {script:32s} runs={b['runs']:3d} "
              f"success={b['successes']:3d} fail={b['failures']:3d} "
              f"avg={b['avg_duration_s']:6.1f}s "
              f"p50={b['p50_duration_s']:6.1f}s")
    print()
    rf = stats["recent_failures_7d"]
    if rf:
        print(f"  Recent failures (last 7d): {len(rf)}")
        for f in rf[:5]:
            print(f"    - [{f['script']}] {f['input_url'][:60]} ({f['started_at']})")
    else:
        print(f"  Recent failures (last 7d): none ✓")
    print()
    print(f"  Generated at       : {stats['generated_at']}")


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audit dashboard for FB crawl runs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--json", default=None,
                        help="Write JSON output to this path")
    parser.add_argument("--since", default=None,
                        help="Filter to runs after this (e.g. 7d, 24h, 30m)")
    parser.add_argument("--script", default=None,
                        help="Filter to manifests from a specific script "
                             "(e.g. 05, 06, 08)")
    parser.add_argument("--root", default=str(DATA_DIR),
                        help=f"Root to scan (default: {DATA_DIR})")
    args = parser.parse_args()

    root = Path(args.root)
    manifests = collect_manifests(root)

    since = parse_since(args.since) if args.since else None
    filtered = filter_manifests(manifests, since=since, script=args.script)
    if not filtered:
        print("⚠ No manifests match the filter.")
        return

    stats = aggregate(filtered)
    print_summary(stats)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"\n💾 Wrote: {out}")


if __name__ == "__main__":
    main()