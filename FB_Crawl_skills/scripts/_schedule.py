"""
Schedule runner for FB crawl jobs.

Reads `data/schedule.yaml` (list of jobs) and runs them on demand.
Use system cron / systemd timer to invoke `python3 scripts/_schedule.py run <job>`.

Why YAML + external cron (not internal scheduler):
  - Cross-platform (works on any host with python3 + cron)
  - User can review/version-control the schedule file
  - No daemon = no resource leak; clear start/stop semantics
  - Each run writes its own manifest under `data/schedule_runs/`

YAML format (minimal — no PyYAML dependency, parse manually):
  jobs:
    - name: mypage_daily
      kind: timeline
      url: https://www.facebook.com/<page-slug>
      count: 30
      schedule_hint: daily 9am  # human-readable, ignored by runner
    - name: mygroup_weekly
      kind: group
      url: https://www.facebook.com/groups/<group-slug>
      count: 50

CLI:
  python3 scripts/_schedule.py list                              # list jobs
  python3 scripts/_schedule.py show <name>                       # show one job
  python3 scripts/_schedule.py run <name>                        # run one job (via fb_cli.py)
  python3 scripts/_schedule.py validate                          # validate schedule.yaml syntax
  python3 scripts/_schedule.py add <name> <kind> <url> [count]  # append a new job
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
SCHEDULE_PATH = DATA_DIR / "schedule.yaml"
RUNS_DIR = DATA_DIR / "schedule_runs"
FB_CLI = SCRIPT_DIR / "fb_cli.py"


# -----------------------------------------------------------------------
# Tiny YAML parser (no PyYAML dep) — handles our minimal subset:
#   key: value
#   - item
#   nested keys under parent
# -----------------------------------------------------------------------

def parse_minimal_yaml(text: str) -> dict:
    """Parse minimal YAML for schedule.yaml.

    Supports:
      - Top-level: `key: value`
      - Lists: `key:\n  - item1\n  - item2`
      - Nested dicts in lists: `  - name: foo\n    url: bar`
    """
    lines = text.splitlines()
    result: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        # Top-level key
        m = re.match(r"^([\w-]+):\s*(.*)$", stripped)
        if not m:
            print(f"⚠ Skipping unparseable line: {line!r}")
            i += 1
            continue
        key, value = m.group(1), m.group(2).strip()
        if value:
            # Inline value
            result[key] = _coerce(value)
            i += 1
        else:
            # Block: list or dict
            block, i = _parse_block(lines, i + 1, indent=2)
            result[key] = block
    return result


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    """Parse a YAML block (list or dict) starting at `start`."""
    items: list = []
    i = start
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        leading = len(line) - len(line.lstrip(" "))
        if leading < indent:
            return items, i
        if stripped.startswith("- "):
            # List item
            item_content = stripped[2:].strip()
            if ":" in item_content:
                # Inline dict inside list item
                m = re.match(r"^([\w-]+):\s*(.*)$", item_content)
                d = {}
                if m and m.group(2):
                    d[m.group(1)] = _coerce(m.group(2))
                    k = m.group(1)
                else:
                    k = m.group(1) if m else None
                # Continue with same indent to gather more keys
                j = i + 1
                while j < len(lines):
                    nxt = lines[j]
                    nxt_stripped = nxt.strip()
                    if not nxt_stripped or nxt_stripped.startswith("#"):
                        j += 1
                        continue
                    nxt_leading = len(nxt) - len(nxt.lstrip(" "))
                    if nxt_leading <= leading:
                        break
                    m2 = re.match(r"^([\w-]+):\s*(.*)$", nxt_stripped)
                    if m2:
                        v2 = m2.group(2).strip()
                        d[m2.group(1)] = _coerce(v2) if v2 else None
                    j += 1
                items.append(d)
                i = j
            else:
                items.append(_coerce(item_content))
                i += 1
        else:
            i += 1
    return items, i


def _coerce(value: str) -> Any:
    """Coerce string value to int/float/bool/str."""
    if value in ("true", "True", "yes"):
        return True
    if value in ("false", "False", "no"):
        return False
    if re.match(r"^-?\d+$", value):
        return int(value)
    if re.match(r"^-?\d+\.\d+$", value):
        return float(value)
    # Strip surrounding quotes
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


# -----------------------------------------------------------------------
# Schedule I/O
# -----------------------------------------------------------------------

def load_schedule(path: Path = SCHEDULE_PATH) -> dict:
    if not path.exists():
        return {"jobs": []}
    return parse_minimal_yaml(path.read_text(encoding="utf-8"))


def save_schedule(schedule: dict, path: Path = SCHEDULE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["jobs:"]
    for job in schedule.get("jobs", []):
        lines.append(f"  - name: {job.get('name', '')}")
        for k, v in job.items():
            if k == "name":
                continue
            if isinstance(v, str):
                lines.append(f"    {k}: {v}")
            else:
                lines.append(f"    {k}: {v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def find_job(schedule: dict, name: str) -> dict | None:
    for job in schedule.get("jobs", []):
        if job.get("name") == name:
            return job
    return None


# -----------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------

def run_job(job: dict) -> int:
    """Execute a job via fb_cli.py. Returns process exit code."""
    name = job.get("name")
    kind = job.get("kind")
    url = job.get("url")
    count = job.get("count", 10)

    if not all([name, kind, url]):
        print(f"❌ Job thiếu trường bắt buộc (name, kind, url): {job}")
        return 1

    # Per-run folder: data/schedule_runs/<name>_<ts>/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"{name}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"📅 SCHEDULED RUN: {name}")
    print(f"   kind: {kind}  url: {url}  count: {count}")
    print(f"   run_dir: {run_dir}")
    print("=" * 60)

    # Build fb_cli args
    argv = [str(FB_CLI), "crawl", kind, url, str(count)]
    if kind == "profile":
        argv.append("--with-about")
    if kind == "deep":
        argv.extend(["--target", str(count)])

    # Log file
    log_path = run_dir / "log.txt"
    manifest_dest = run_dir / "manifest.json"
    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"Started at {datetime.now().isoformat()}\n")
        logf.write(f"Job: {json.dumps(job, ensure_ascii=False)}\n")
        logf.write(f"Command: {' '.join(argv)}\n\n")
        logf.flush()
        proc = subprocess.run(argv, stdout=logf, stderr=subprocess.STDOUT)
        logf.write(f"\n\nExited with code {proc.returncode}\n")
        logf.write(f"Finished at {datetime.now().isoformat()}\n")

    print(f"📋 Log: {log_path}")

    # Copy most recent manifest (if any) from crawl target folder to run_dir
    try:
        from _data_paths import post_dir
        target_post_dir = post_dir(url)
        source_manifest = target_post_dir / "manifest.json"
        if source_manifest.exists():
            import shutil
            shutil.copy(source_manifest, manifest_dest)
            print(f"📋 Manifest copied: {manifest_dest}")
    except Exception as e:
        print(f"⚠ Could not copy manifest: {e}")

    return proc.returncode


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="FB crawl schedule runner (YAML config + on-demand runs).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List all jobs in schedule.yaml")
    sub.add_parser("validate", help="Validate schedule.yaml syntax")

    p_show = sub.add_parser("show", help="Show one job")
    p_show.add_argument("name")

    p_run = sub.add_parser("run", help="Run a job once")
    p_run.add_argument("name")

    p_add = sub.add_parser("add", help="Add a new job")
    p_add.add_argument("name", help="Unique job name")
    p_add.add_argument("kind", choices=["group", "post", "page", "deep",
                                          "timeline", "profile"])
    p_add.add_argument("url", help="Group/Post/Page/Profile URL")
    p_add.add_argument("count", type=int, nargs="?", default=10)

    args = parser.parse_args()

    if args.cmd == "list":
        s = load_schedule()
        jobs = s.get("jobs", [])
        if not jobs:
            print("(no jobs defined — use `add` to create one)")
            return
        print(f"{len(jobs)} job(s):")
        for j in jobs:
            print(f"  • {j.get('name'):24s} {j.get('kind'):10s} {j.get('url')}")

    elif args.cmd == "show":
        s = load_schedule()
        j = find_job(s, args.name)
        if not j:
            print(f"❌ Job not found: {args.name}")
            sys.exit(1)
        print(json.dumps(j, indent=2, ensure_ascii=False))

    elif args.cmd == "validate":
        s = load_schedule()
        jobs = s.get("jobs", [])
        print(f"✓ Valid YAML, {len(jobs)} job(s)")
        for j in jobs:
            missing = [k for k in ("name", "kind", "url") if not j.get(k)]
            if missing:
                print(f"  ❌ Job '{j.get('name', '?')}' missing: {missing}")
                sys.exit(1)
        print("✓ All jobs have required fields (name, kind, url)")

    elif args.cmd == "run":
        s = load_schedule()
        j = find_job(s, args.name)
        if not j:
            print(f"❌ Job not found: {args.name}")
            sys.exit(1)
        rc = run_job(j)
        sys.exit(rc)

    elif args.cmd == "add":
        s = load_schedule()
        if find_job(s, args.name):
            print(f"❌ Job đã tồn tại: {args.name}")
            sys.exit(1)
        new_job = {
            "name": args.name,
            "kind": args.kind,
            "url": args.url,
            "count": args.count,
        }
        s.setdefault("jobs", []).append(new_job)
        save_schedule(s)
        print(f"✓ Added job '{args.name}' to {SCHEDULE_PATH}")


if __name__ == "__main__":
    main()