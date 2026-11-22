"""Read pending Facebook Sheet rows and invoke the existing crawler unchanged.

Default is preview only. --run crawls sequentially in an already-open Google
Chrome CDP session. Sheet statuses are read-only; local state supports resume.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHEET = os.environ.get("FB_SHEET_URL", "")
DEFAULT_CRAWLER = ROOT / "FB_Crawl_skills/scripts/05_auto_scrape_cdp.py"
DEFAULT_OUTPUT = ROOT / "data/facebook-sheet-output"
BROWSER_DISCONNECT_EXIT_CODE = 75
HEADERS = {"id_content": "id_content", "ten su kien": "event_name",
           "event_name": "event_name", "links": "links", "url": "links",
           "status": "status"}


class BrowserUnavailable(RuntimeError):
    """The crawler lost its Chrome DevTools session."""


@dataclass
class Job:
    event_id: str
    event_name: str
    url: str
    sheet_rows: list[int]

    @property
    def key(self):
        return hashlib.sha256(f"{self.event_id}\n{self.url}".encode()).hexdigest()[:24]


def normalized(value):
    text = unicodedata.normalize("NFD", value.strip().casefold()).replace("đ", "d")
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def read_sheet(sheet_url, gid=None):
    """Download this tab on every invocation, not a cached/exported local file."""
    parsed = urlsplit(sheet_url)
    match = re.fullmatch(r"/spreadsheets/d/([\w-]+)(?:/.*)?", parsed.path)
    if parsed.hostname != "docs.google.com" or not match:
        raise ValueError("--sheet-url must be a docs.google.com/spreadsheets/d/... URL")
    tab = gid or (parse_qs(parsed.query).get("gid") or
                  parse_qs(parsed.fragment).get("gid") or [None])[0]
    if tab is None or not str(tab).isdigit():
        raise ValueError("Specify the tab gid in the URL or --gid")
    endpoint = f"https://docs.google.com/spreadsheets/d/{match[1]}/export?" + urlencode(
        {"format": "csv", "gid": tab})
    try:
        with urlopen(Request(endpoint, headers={"User-Agent": "FacebookSheetWrapper/1.0"}), timeout=30) as response:
            payload = response.read().decode("utf-8-sig")
            content_type = response.headers.get("Content-Type", "")
    except HTTPError as exc:
        raise RuntimeError(f"Sheet returned HTTP {exc.code}; check view permission and gid") from exc
    if "text/html" in content_type or payload.lstrip().lower().startswith(("<!doctype", "<html")):
        raise RuntimeError("Sheet returned a login/HTML page, not CSV; check view permission")
    return list(csv.reader(io.StringIO(payload)))


def facebook_url(value):
    parsed = urlsplit(value.rstrip(".,;"))
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (
        host in {"facebook.com", "fb.com", "fb.watch"} or host.endswith(".facebook.com")
    ) or parsed.username or parsed.password:
        raise ValueError("Links must contain Facebook/fb.watch URLs only")
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def pending_jobs(rows):
    """Exact pending status, explicit event ID per row; never infer/carry IDs."""
    if not rows:
        raise ValueError("Sheet is empty")
    columns = {}
    for index, name in enumerate(rows[0]):
        field = HEADERS.get(normalized(name))
        if field in columns:
            raise ValueError(f"Duplicate Sheet column: {field}")
        if field:
            columns[field] = index
    missing = {"id_content", "event_name", "links", "status"} - columns.keys()
    if missing:
        raise ValueError(f"Missing Sheet columns: {', '.join(sorted(missing))}")
    jobs, owners, names = {}, {}, {}
    for number, values in enumerate(rows[1:], 2):
        row = {k: values[i].strip() if i < len(values) else "" for k, i in columns.items()}
        if row["status"].casefold() != "pending":
            continue
        event_id, name = row["id_content"], row["event_name"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", event_id) or not name:
            raise ValueError(f"Row {number}: pending row needs valid id_content and event name")
        if event_id in names and names[event_id] != name:
            raise ValueError(f"Row {number}: conflicting names for {event_id}")
        names[event_id] = name
        urls = re.findall(r"https?://[^\s<>\"']+", row["links"])
        if not urls:
            raise ValueError(f"Row {number}: pending row has no URL")
        for value in urls:
            try:
                url = facebook_url(value)
            except ValueError as exc:
                raise ValueError(f"Row {number}: {exc}") from exc
            if url in owners and owners[url] != event_id:
                raise ValueError(f"Row {number}: URL assigned to both {owners[url]} and {event_id}")
            owners[url] = event_id
            key = (event_id, url)
            if key in jobs:
                if number not in jobs[key].sheet_rows:
                    jobs[key].sheet_rows.append(number)
            else:
                jobs[key] = Job(event_id, name, url, [number])
    return list(jobs.values())


def read_retry_plan(path):
    payload = path.read_bytes()
    document = json.loads(payload)
    entries = document.get("jobs") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise ValueError("Retry plan must contain a jobs list")
    selected = {}
    for entry in entries:
        if (not isinstance(entry, dict)
                or not all(isinstance(entry.get(field), str) for field in ("event_id", "event_name", "url"))
                or not isinstance(entry.get("sheet_rows"), list)):
            raise ValueError("Retry plan contains an invalid job")
        job = Job(entry["event_id"], entry["event_name"].strip(),
                  facebook_url(entry["url"]), entry["sheet_rows"])
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", job.event_id)
                or not job.event_name or not job.sheet_rows
                or any(type(row) is not int or row < 2 for row in job.sheet_rows)):
            raise ValueError("Retry plan contains an invalid event or sheet row")
        if job.key in selected:
            raise ValueError(f"Duplicate job in retry plan: {job.event_id} {job.url}")
        selected[job.key] = job
    return hashlib.sha256(payload).hexdigest(), list(selected.values())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def chrome_preflight(cdp_url, *, verbose=True):
    with urlopen(cdp_url.rstrip("/") + "/json/version", timeout=5) as response:
        version = json.load(response)
    browser = version.get("Browser", "")
    if not browser.startswith("Chrome/"):
        raise RuntimeError(f"CDP is {browser!r}, not Google Chrome; refusing to crawl")
    if verbose:
        print(f"Verified Google {browser} at {cdp_url}", flush=True)


def crawler_folder(crawler, url):
    # Reuse the crawler's own path helper; do not duplicate or change its logic.
    import importlib.util
    spec = importlib.util.spec_from_file_location("sheet_wrapper_data_paths", crawler.parent / "_data_paths.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.POSTS_DIR / module.sanitize_url(url)


def command_for(job, args):
    return [sys.executable, str(args.crawler), job.url, "--event-id", job.event_id,
            "--target", str(args.target), "--max-rounds", str(args.max_rounds),
            "--click-pause", str(args.click_pause), "--no-relaunch", "--crash-retries", "0"]


def validate_common(path, event_id):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or any(r.get("event_id") != event_id or r.get("platform") != "facebook" or
                       not r.get("comment_id") for r in rows):
        raise ValueError("Missing/invalid common output or wrong event_id/platform")
    return rows


def crawl_job(job, args, *, retry=False, previous=None):
    folder = crawler_folder(args.crawler, job.url)
    attempt = uuid4().hex if retry else None
    suffix = f"-retry-{attempt}" if retry else ""
    checkpoint = folder / "checkpoint.json"
    if retry and checkpoint.is_file():
        checkpoint.rename(folder / f"checkpoint{suffix}.json")
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in folder.glob("common*.jsonl")}
    log_path = args.output / "logs" / f"{job.key}{suffix}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, FB_CDP_HTTP=args.cdp_url, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(command_for(job, args), cwd=ROOT, env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
    if result.returncode == BROWSER_DISCONNECT_EXIT_CODE:
        raise BrowserUnavailable(f"Chrome CDP session stopped responding; log: {log_path}")
    if result.returncode:
        raise RuntimeError(f"Crawler exit {result.returncode}; log: {log_path}")
    fresh = [p for p in folder.glob("common*.jsonl") if before.get(p) !=
             (p.stat().st_mtime_ns, p.stat().st_size)]
    if len(fresh) != 1:
        # The crawler may exit 0 with zero comments: that is NOT a completed job.
        raise RuntimeError(f"Expected one new common output, got {len(fresh)}; log: {log_path}")
    source = fresh[0]
    rows = validate_common(source, job.event_id)
    attempt_count = len(rows)
    if retry and reusable(previous or {}, job.event_id):
        saved = validate_common(Path(previous["common_file"]), job.event_id)
        merged = {(row.get("post_id"), row["comment_id"]): row for row in saved}
        for row in rows:
            merged.setdefault((row.get("post_id"), row["comment_id"]), row)
        rows = list(merged.values())
    snapshot = args.output / "posts" / f"{job.key}{suffix}.jsonl"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    if retry:
        with snapshot.open("x", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    else:
        snapshot.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    record = {"status": "success", "event_id": job.event_id, "event_name": job.event_name,
              "url": job.url, "sheet_rows": job.sheet_rows, "count": len(rows),
              "common_file": str(snapshot), "crawler_common_file": str(source),
              "log_file": str(log_path), "finished_at": datetime.now(timezone.utc).isoformat()}
    if retry:
        record["last_retry_count"] = attempt_count
    return record


def reusable(record, event_id):
    if record.get("status") != "success":
        return False
    try:
        validate_common(Path(record["common_file"]), event_id)
        return True
    except (KeyError, OSError, ValueError):
        return False


def export_events(state, output):
    events = {}
    for record in state["jobs"].values():
        if not reusable(record, record.get("event_id")):
            continue
        event = events.setdefault(record["event_id"], {
            "id_content": record["event_id"], "event_name": record["event_name"],
            "platform": "facebook", "posts": [], "comments": {}})
        event["posts"].append({k: record[k] for k in ("url", "sheet_rows", "count", "common_file")})
        for row in validate_common(Path(record["common_file"]), record["event_id"]):
            event["comments"][(row.get("post_id"), row["comment_id"])] = row
    for event_id, event in events.items():
        event["comments"] = list(event["comments"].values())
        event["comments_count"] = len(event["comments"])
        atomic_json(output / "events" / f"{event_id}.json", event)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-url", default=DEFAULT_SHEET, help="Google Sheets tab URL (or FB_SHEET_URL)")
    parser.add_argument("--gid", help="Override tab gid")
    parser.add_argument("--event-id", help="Only select this event from pending rows")
    parser.add_argument("--limit", type=int, default=0, help="Max links this run; 0 = all pending")
    parser.add_argument("--run", action="store_true", help="Actually crawl; default only previews jobs")
    parser.add_argument("--force", action="store_true", help="Re-crawl locally completed jobs")
    parser.add_argument("--retry-plan", type=Path, help="Retry jobs selected in a local JSON plan")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--crawler", type=Path, default=DEFAULT_CRAWLER)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9333")
    parser.add_argument("--target", type=int, default=0)
    parser.add_argument("--max-rounds", type=int, default=50)
    parser.add_argument("--click-pause", type=float, default=4.0)
    parser.add_argument("--between-posts", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=1800, help="Timeout seconds per URL")
    args = parser.parse_args(argv)
    if not args.retry_plan and not args.sheet_url:
        parser.error("Provide --sheet-url or set FB_SHEET_URL when reading Google Sheets")
    if min(args.limit, args.target, args.between_posts) < 0 or min(args.max_rounds, args.timeout) < 1 or args.click_pause < 3.5:
        parser.error("Counts must be nonnegative; rounds/timeout positive; click pause >= 3.5")
    args.output, args.crawler = args.output.resolve(), args.crawler.resolve()
    state_path = args.output / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"jobs": {}}
    plan_id, jobs = (read_retry_plan(args.retry_plan) if args.retry_plan
                     else (None, pending_jobs(read_sheet(args.sheet_url, args.gid))))
    if args.event_id:
        jobs = [j for j in jobs if j.event_id == args.event_id]
    pending_count = len(jobs)
    if plan_id:
        jobs = [j for j in jobs if state["jobs"].get(j.key, {}).get("last_retry_plan") != plan_id]
    else:
        jobs = [j for j in jobs if args.force or not reusable(state["jobs"].get(j.key, {}), j.event_id)]
    remaining_count = len(jobs)
    if args.limit:
        jobs = jobs[:args.limit]
    label = "Retry links" if plan_id else "Pending links"
    remaining_label = "remaining" if plan_id else "not completed locally"
    print(f"{label}: {pending_count}; {remaining_label}: {remaining_count}; selected: {len(jobs)}")
    print(f"Selected events: {len({j.event_id for j in jobs})}; mode: {'RUN' if args.run else 'PREVIEW'}")
    for job in jobs:
        print(f"  rows {','.join(map(str, job.sheet_rows))} | {job.event_id} | {job.url}")
    plan_name = "retry-preview.json" if plan_id else "pending-plan.json"
    atomic_json(args.output / plan_name, {
        "sheet_url": args.sheet_url, "gid_override": args.gid,
        "read_at": datetime.now(timezone.utc).isoformat(), "jobs": [asdict(j) for j in jobs]})
    if not args.run or not jobs:
        return 0
    if not args.crawler.is_file():
        raise ValueError(f"Crawler not found: {args.crawler}")
    chrome_preflight(args.cdp_url)
    # One local runner per output state. Never crawl two posts in one tab concurrently.
    lock = args.output / ".running.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another run may be active; inspect {lock} before removing a stale lock") from exc
    os.close(descriptor)
    failures = 0
    try:
        for index, job in enumerate(jobs):
            if index:
                time.sleep(args.between_posts)
            print(f"[{index + 1}/{len(jobs)}] {job.event_id}: {job.url}", flush=True)
            previous = state["jobs"].get(job.key, {})
            try:
                chrome_preflight(args.cdp_url, verbose=False)
            except (OSError, ValueError, RuntimeError) as exc:
                raise RuntimeError(f"Paused before {job.url}: Chrome CDP unavailable: {exc}") from exc
            try:
                record = (crawl_job(job, args, retry=True, previous=previous)
                          if plan_id else crawl_job(job, args))
                result_message = f"  OK: {record['count']} records"
            except BrowserUnavailable as exc:
                raise RuntimeError(f"Paused on {job.url}: {exc}") from exc
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
                try:
                    chrome_preflight(args.cdp_url, verbose=False)
                except (OSError, ValueError, RuntimeError) as browser_error:
                    raise RuntimeError(f"Paused on {job.url}: Chrome CDP unavailable: {browser_error}") from exc
                failures += 1
                record = {**asdict(job), "status": "failed", "error": str(exc)}
                result_message = f"  FAILED: {exc}"
                # Preserve the last good snapshot if a forced refresh fails.
                if reusable(previous, job.event_id):
                    record = {**previous, "last_refresh_error": str(exc)}
            if plan_id:
                record["last_retry_plan"] = plan_id
            state["jobs"][job.key] = record
            atomic_json(state_path, state)
            export_events(state, args.output)
            print(result_message, flush=True)
    finally:
        lock.unlink(missing_ok=True)
    print(f"Finished: {len(jobs) - failures} succeeded, {failures} failed. Sheet unchanged.")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, URLError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
