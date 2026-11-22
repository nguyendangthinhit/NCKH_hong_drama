"""Drain remaining Facebook jobs and preserve partial data on browser failure."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "facebook_sheet_wrapper", Path(__file__).with_name("crawl-facebook-pending-sheet.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


wrapper = load_wrapper()
sys.path.insert(0, str(wrapper.DEFAULT_CRAWLER.parent))
from _common_schema import to_common_rows, write_common_jsonl

def chrome_request(args, path, method="GET"):
    with urlopen(Request(args.cdp_url + path, method=method), timeout=5) as response:
        return response.read()


def ensure_chrome(args, stale_url=None):
    for _ in range(3):
        try:
            wrapper.chrome_preflight(args.cdp_url, verbose=False)
            break
        except OSError:
            subprocess.Popen([str(args.chrome), f"--user-data-dir={args.profile}",
                              "--remote-debugging-port=9333",
                              "--remote-debugging-address=127.0.0.1", "https://www.facebook.com/"])
            for _ in range(15):
                time.sleep(2)
                try:
                    wrapper.chrome_preflight(args.cdp_url, verbose=False)
                    break
                except OSError:
                    continue
            else:
                continue
            break
    else:
        raise RuntimeError("Chrome CDP did not return after three launches")

    pages = json.loads(chrome_request(args, "/json/list"))
    tabs = [page for page in pages if page.get("type") == "page"]
    stale = [page for page in tabs if page.get("url", "").rstrip("/") == stale_url]
    if stale or not tabs:
        chrome_request(args, "/json/new?" + quote("https://www.facebook.com/", safe=""), "PUT")
        for page in stale:
            chrome_request(args, "/json/close/" + page["id"])


def partial_record(job, args, snapshots, previous):
    merged = {}
    if previous.get("status") == "partial":
        merged.update({row["comment_id"]: row for row in
                       wrapper.validate_common(Path(previous["common_file"]), job.event_id)})
    for source in sorted(snapshots):
        comments = json.loads(source.read_text(encoding="utf-8"))
        for row in to_common_rows(comments, job.event_id, job.url):
            merged[row["comment_id"]] = row
    if not merged:
        return {}
    path = args.output / "posts" / f"{job.key}-partial.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    write_common_jsonl(list(merged.values()), temp)
    temp.replace(path)
    return {"status": "partial", "count": len(merged), "common_file": str(path)}


def crawl(job, args, previous):
    folder = wrapper.crawler_folder(args.crawler, job.url)
    existing = set(folder.glob("partial-comments-*.json"))
    disconnects = 0
    while True:
        ensure_chrome(args)
        try:
            merge_base = {**previous, "status": "success"} if previous.get("status") == "partial" else previous
            return wrapper.crawl_job(job, args, retry=True, previous=merge_base)
        except (wrapper.BrowserUnavailable, subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
            error = str(exc)
            log_match = re.search(r"log: (.+)$", error)
            log_text = Path(log_match[1]).read_text(encoding="utf-8") if log_match else ""
            oom = bool(re.search(r"out.of.memory|status: oom\b", log_text, re.IGNORECASE))
            if isinstance(exc, wrapper.BrowserUnavailable) and not oom and disconnects == 0:
                disconnects += 1
                saved = partial_record(job, args, set(folder.glob("partial-comments-*.json")) - existing,
                                       previous)
                if saved:
                    previous = saved
                print("  Chrome disconnected. Reopening and retrying the same link.", flush=True)
                ensure_chrome(args, job.url)
                continue
            saved = partial_record(job, args, set(folder.glob("partial-comments-*.json")) - existing,
                                   previous)
            reason = "out_of_memory" if oom else (
                "chrome_disconnect" if isinstance(exc, wrapper.BrowserUnavailable) else
                "timeout" if isinstance(exc, subprocess.TimeoutExpired) else "crawler_error"
            )
            return {**asdict(job), "status": "failed", **saved,
                    "skip_reason": reason, "error": error}


def pending_jobs(state, sheet_url):
    rows = wrapper.read_sheet(sheet_url)
    headers = {wrapper.HEADERS.get(wrapper.normalized(value)): index
               for index, value in enumerate(rows[0])}
    ids, names, statuses = (headers[field] for field in ("id_content", "event_name", "status"))
    canonical = {entry["event_id"]: entry["event_name"] for entry in state["jobs"].values()
                 if entry.get("event_id") and entry.get("event_name")}
    changed = set()
    for row in rows[1:]:
        if len(row) <= max(ids, names, statuses) or row[statuses].strip().casefold() != "pending":
            continue
        event_id, name = row[ids].strip(), row[names].strip()
        if not event_id or not name:
            continue
        canonical_name = canonical.setdefault(event_id, name)
        if canonical_name != name:
            changed.add(event_id)
            row[names] = canonical_name
    if changed:
        print(f"Using local event names for {len(changed)} IDs with alternate sheet names.", flush=True)
    return wrapper.pending_jobs(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--sheet-url", default=wrapper.DEFAULT_SHEET, help="Google Sheets tab URL (or FB_SHEET_URL)")
    args = parser.parse_args()
    if not args.progress.exists() and not args.sheet_url:
        parser.error("Provide --sheet-url or set FB_SHEET_URL when creating a progress file")
    args.output = wrapper.DEFAULT_OUTPUT
    args.crawler = wrapper.DEFAULT_CRAWLER
    args.cdp_url = "http://127.0.0.1:9333"
    args.target, args.max_rounds, args.click_pause, args.timeout = 0, 2000, 4, 21600
    state_path = args.output / "state.json"
    lock = args.output / ".running.lock"
    args.output.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(str(os.getpid()))
    try:
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"jobs": {}}
        if args.progress.exists():
            progress = json.loads(args.progress.read_text(encoding="utf-8"))
        else:
            jobs = pending_jobs(state, args.sheet_url)
            jobs = [job for job in jobs if not wrapper.reusable(state["jobs"].get(job.key, {}), job.event_id)]
            known = {job.key for job in jobs}
            for key, entry in state["jobs"].items():
                if (entry.get("status") in {"failed", "partial"} and key not in known
                        and all(entry.get(field) for field in ("event_id", "event_name", "url", "sheet_rows"))):
                    jobs.append(wrapper.Job(entry["event_id"], entry["event_name"], entry["url"], entry["sheet_rows"]))
            progress = {"jobs": [asdict(job) for job in jobs], "results": {}, "current": None}
            wrapper.atomic_json(args.progress, progress)
        total = len(progress["jobs"])
        print(f"Selected {total} unfinished links.", flush=True)
        for index, entry in enumerate(progress["jobs"], 1):
            job = wrapper.Job(**entry)
            if job.key in progress["results"]:
                continue
            progress["current"] = entry
            wrapper.atomic_json(args.progress, progress)
            print(f"[{index}/{total}] {job.event_id}: {job.url}", flush=True)
            record = crawl(job, args, state["jobs"].get(job.key, {}))
            state["jobs"][job.key] = record
            wrapper.atomic_json(state_path, state)
            wrapper.export_events(state, args.output)
            progress["results"][job.key] = record
            wrapper.atomic_json(args.progress, progress)
            print(f"  {record['status']}: {record.get('count', 0)} records"
                  f" {record.get('skip_reason', '')}", flush=True)
            if record.get("skip_reason") in {"out_of_memory", "chrome_disconnect", "timeout"}:
                ensure_chrome(args, job.url)
        progress["current"] = None
        wrapper.atomic_json(args.progress, progress)
        print("Finished all selected links.", flush=True)
    finally:
        lock.unlink()


if __name__ == "__main__":
    main()
