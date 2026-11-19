#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fb_cli.py — Facebook-specific CLI.

Wraps the portable stealth suite at `/home/enzo/stealth-suite/` for browser
management, and adds Facebook-specific operations (crawl, clean, list).

Usage:
  # Delegate to stealth_cli.py (portable):
  python3 scripts/fb_cli.py open [URL]                  # Browser launcher
  python3 scripts/fb_cli.py status                      # Browser + tab status
  python3 scripts/fb_cli.py navigate <URL>              # Navigate current tab
  python3 scripts/fb_cli.py stealth status              # Anti-bot state
  python3 scripts/fb_cli.py stealth inject              # Inject init script

  # Facebook-specific:
  python3 scripts/fb_cli.py crawl group <GROUP_URL> [N]       # N posts in group (default 10)
  python3 scripts/fb_cli.py crawl page <PAGE_URL> [N]         # [legacy] N posts from fanpage (uses 06)
  python3 scripts/fb_cli.py crawl timeline <PAGE_URL> [N]     # N posts from fanpage timeline (uses 08)
  python3 scripts/fb_cli.py crawl post <POST_URL> [N]        # N comments of post (default 100, uses 05)
  python3 scripts/fb_cli.py crawl deep <POST_URL> --target N  # Deep crawl with iterative load (uses 05)
  python3 scripts/fb_cli.py crawl profile <PROFILE_URL> --with-about
                                                              # 3-stage: about + posts + photos (uses 09)

  python3 scripts/fb_cli.py clean <file.json> [--cross-dedup]   # Normalize raw → clean + manifest
  python3 scripts/fb_cli.py export <input.jsonl> {csv|json|parquet} [output]
                                                              # Export for analytics
  python3 scripts/fb_cli.py bulk <urls_file> [--count N]        # Bulk crawl from URL list
  python3 scripts/fb_cli.py list                                  # List raw + clean files

Examples:
  python3 scripts/fb_cli.py crawl group https://www.facebook.com/groups/<group-slug> 20
  python3 scripts/fb_cli.py crawl post https://www.facebook.com/share/p/<POST_ID>/ 50
  python3 scripts/fb_cli.py crawl deep https://www.facebook.com/share/p/<POST_ID>/ --target 100
  python3 scripts/fb_cli.py crawl timeline https://www.facebook.com/<page-slug> 30
  python3 scripts/fb_cli.py export data/posts/<slug>/clean.jsonl csv
  python3 scripts/fb_cli.py bulk my_urls.txt --count 20 --group https://www.facebook.com/groups/<group-slug>
"""
import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
STEALTH_SUITE = Path("/home/enzo/stealth-suite/scripts")
DATA_DIR = SCRIPTS_DIR.parent / "data"


def _delegate_to_stealth(args, subcommand: str):
    """Delegate browser/stealth commands to portable stealth_cli.py.

    `subcommand` can be space-separated (e.g. "stealth status") -- will be split.
    """
    cmd = ["python3", str(STEALTH_SUITE / "stealth_cli.py")]
    cmd.extend(subcommand.split())
    if hasattr(args, "url") and args.url:
        cmd.append(args.url)
    if hasattr(args, "chromedriver") and args.chromedriver:
        cmd.extend(["--chromedriver", args.chromedriver])
    if hasattr(args, "backup") and args.backup:
        cmd.append("--backup")
    if hasattr(args, "locale") and args.locale:
        cmd.extend(["--locale", args.locale])
    if hasattr(args, "port") and args.port:
        cmd.extend(["--port", str(args.port)])
    if hasattr(args, "user_data_dir") and args.user_data_dir:
        cmd.extend(["--user-data-dir", args.user_data_dir])
    subprocess.run(cmd)


def cmd_open(args):
    """Open chromium (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "open")


def cmd_status(args):
    """Browser + tab status (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "status")


def cmd_navigate(args):
    """Navigate current tab (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "navigate")


def cmd_stealth_status(args):
    """Stealth state (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "stealth status")


def cmd_stealth_patch(args):
    """Patch chromedriver (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "stealth patch")


def cmd_stealth_inject(args):
    """Inject stealth init script (delegates to stealth_cli.py)."""
    _delegate_to_stealth(args, "stealth inject")


def cmd_crawl(args):
    """Crawl posts or comments (FB-specific)."""
    kind = args.kind
    url = args.url
    count = args.count

    # Dispatch table — keeps routing explicit + extensible.
    # Each entry: (script, args-list-builder). None = use raw URL/count passthrough.
    SCRIPTS = {
        "group":    ("06_crawl_group.py",        lambda u, c: [u, str(c)]),
        "page":     ("06_crawl_group.py",        lambda u, c: [u, str(c)]),  # legacy alias
        "timeline": ("08_crawl_page_timeline.py", lambda u, c: [u, str(c)]),  # fanpage timeline
        "profile":  ("09_crawl_profile.py",      lambda u, c: _profile_args(u, args)),
        "post":     ("05_auto_scrape_cdp.py",    lambda u, c: [u, str(min(c, 30))]),
        "deep":     ("05_auto_scrape_cdp.py",    lambda u, c: _deep_args(u, c, args)),
    }

    if kind not in SCRIPTS:
        print(f"❌ Unknown kind: {kind}. Use one of: {', '.join(SCRIPTS)}.")
        sys.exit(1)

    script_name, builder = SCRIPTS[kind]
    script = SCRIPTS_DIR / script_name
    sys.argv = [script_name] + builder(url, count)

    # Forward cookie/browser flags if provided
    for flag in ["cookie_file", "cookie_string", "cookie_domain", "browser",
                 "max_rounds", "click_pause"]:
        val = getattr(args, flag, None)
        if val is not None and val != "" and val != 0:
            cli_name = "--" + flag.replace("_", "-")
            if flag == "max_rounds" and val == 50:
                continue  # Skip default
            if flag == "click_pause" and val == 4.0:
                continue  # Skip default
            if flag == "cookie_domain" and val == ".facebook.com":
                continue  # Skip default
            if flag == "browser" and val == "auto":
                continue  # Skip default
            sys.argv.extend([cli_name, str(val)])

    # Only 05_auto_scrape_cdp.py (post/deep) writes the shared-schema common.jsonl.
    if kind in ("post", "deep") and getattr(args, "event_id", None):
        sys.argv.extend(["--event-id", args.event_id])

    print(f"→ Running: {script.name} {' '.join(sys.argv[1:])}")
    subprocess.run([sys.executable, str(script)] + sys.argv[1:])


def _deep_args(url, count, args):
    """Build argv for `deep` mode. --target 0 (default) = take every comment FB serves."""
    return [url, "--target", str(getattr(args, "target", 0) or 0)]


def _profile_args(url, args):
    """Build argv for `profile` mode (3-stage: about + posts + photos)."""
    argv = [url]
    if getattr(args, "with_about", False):
        argv.append("--with-about")
    if getattr(args, "no_about", False):
        argv.append("--no-about")
    if getattr(args, "with_photos", False):
        argv.append("--with-photos")
    if getattr(args, "max_posts", None) is not None:
        argv.extend(["--max-posts", str(args.max_posts)])
    if getattr(args, "max_scrolls", None) is not None:
        argv.extend(["--max-scrolls", str(args.max_scrolls)])
    return argv



def cmd_clean(args):
    """Clean raw file (FB-specific)."""
    script = SCRIPTS_DIR / "04_clean_data.py"
    file_path = Path(args.file)
    if not file_path.is_absolute():
        file_path = SCRIPTS_DIR.parent / file_path
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        sys.exit(1)
    argv = [str(file_path)]
    if getattr(args, "cross_dedup", False):
        argv.append("--cross-dedup")
    if getattr(args, "output_dir", None):
        argv.extend(["--output-dir", str(args.output_dir)])
    subprocess.run([sys.executable, str(script)] + argv)


def cmd_export(args):
    """Export clean JSONL to CSV / JSON / Parquet."""
    script = SCRIPTS_DIR / "_export.py"
    inp = Path(args.input)
    if not inp.is_absolute():
        inp = SCRIPTS_DIR.parent / inp
    if not inp.exists():
        print(f"❌ File not found: {inp}")
        sys.exit(1)
    argv = [str(inp), args.format]
    if args.output:
        argv.append(str(args.output))
    print(f"→ Exporting {inp.name} → {args.format}")
    subprocess.run([sys.executable, str(script)] + argv)


def cmd_bulk(args):
    """Bulk crawl: read URL list from file, run 07_crawl_n_posts.py."""
    script = SCRIPTS_DIR / "07_crawl_n_posts.py"
    urls_file = Path(args.urls_file)
    if not urls_file.is_absolute():
        urls_file = SCRIPTS_DIR.parent / urls_file
    if not urls_file.exists():
        print(f"❌ URLs file not found: {urls_file}")
        sys.exit(1)
    argv = ["--urls-file", str(urls_file), "--count", str(args.count)]
    if args.group:
        argv.extend(["--group", args.group])
    if args.no_auto_find:
        argv.append("--no-auto-find")
    print(f"→ Bulk crawl: {args.count} posts from {urls_file}")
    subprocess.run([sys.executable, str(script)] + argv)


def cmd_schedule(args):
    """Schedule runner (delegates to _schedule.py)."""
    script = SCRIPTS_DIR / "_schedule.py"
    argv = [args.subcmd] if hasattr(args, "subcmd") else []
    if getattr(args, "name", None):
        argv.append(args.name)
    if getattr(args, "kind", None):
        argv.append(args.kind)
    if getattr(args, "url", None):
        argv.append(args.url)
    if getattr(args, "count", None) is not None:
        argv.append(str(args.count))
    subprocess.run([sys.executable, str(script)] + argv)


def cmd_audit(args):
    """Audit dashboard (delegates to _audit.py)."""
    script = SCRIPTS_DIR / "_audit.py"
    argv = []
    if getattr(args, "json", None):
        argv.extend(["--json", args.json])
    if getattr(args, "since", None):
        argv.extend(["--since", args.since])
    if getattr(args, "script", None):
        argv.extend(["--script", args.script])
    if getattr(args, "root", None):
        argv.extend(["--root", args.root])
    subprocess.run([sys.executable, str(script)] + argv)


def cmd_list(args):
    """List posts/folders + raw + clean files (new folder structure)."""
    sys.path.insert(0, str(SCRIPTS_DIR))
    from _data_paths import POSTS_DIR, TESTS_DIR, ARCHIVE_DIR, list_posts

    posts = list_posts()
    print(f"=== Posts ({len(posts)}) ===")
    for p in posts:
        slug = p['slug']
        comments = p.get('comments_count', '?')
        n_files = len(p.get('files', {}))
        print(f"  {slug:60s} {comments} comments, {n_files} files")

    print(f"\n=== Tests ===")
    if TESTS_DIR.exists():
        for d in sorted(TESTS_DIR.iterdir()):
            if d.is_dir():
                files = list(d.iterdir())
                print(f"  {d.name}/ ({len(files)} files)")
                for f in files[:5]:
                    print(f"    {f.name}")

    print(f"\n=== Loose files in data/ root ===")
    for f in sorted(DATA_DIR.iterdir()):
        if f.is_file():
            print(f"  {f.name} ({f.stat().st_size} bytes)")


def main():
    parser = argparse.ArgumentParser(
        description="FB CLI — Facebook-specific wrapper (delegates browser ops to stealth_cli.py)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # open
    p = sub.add_parser("open", help="Open Chromium browser")
    p.add_argument("url", nargs="?", help="Default URL (FB login)")
    p.set_defaults(func=cmd_open)

    # status
    p = sub.add_parser("status", help="Browser + tab status")
    p.set_defaults(func=cmd_status)

    # navigate
    p = sub.add_parser("navigate", help="Navigate current tab to URL")
    p.add_argument("url", help="URL to navigate")
    p.set_defaults(func=cmd_navigate)

    # crawl (FB-specific)
    p = sub.add_parser("crawl", help="Crawl posts or comments")
    p.add_argument("kind",
                   choices=["group", "post", "page", "deep", "timeline", "profile"],
                   help="group/post/page/timeline/profile/deep — see docstring at top of fb_cli.py")
    p.add_argument("url", help="Group/Post/Page/Profile URL")
    p.add_argument("count", type=int, nargs="?", default=10,
                   help="Count (default: 10)")
    p.add_argument("--target", type=int, default=0,
                   help="Deep mode: stop at N comments. Default 0 = get as many as possible")
    p.add_argument("--event-id", type=str, default=None,
                   help="post/deep mode: event id written to common.jsonl (shared schema)")
    # Profile-specific flags (forwarded to 09_crawl_profile.py)
    p.add_argument("--with-about", action="store_true",
                   help="[profile] Extract About section (Stage 1)")
    p.add_argument("--no-about", action="store_true",
                   help="[profile] Skip About section")
    p.add_argument("--with-photos", action="store_true",
                   help="[profile] Extract photos from /photos tab (Stage 3)")
    p.add_argument("--max-posts", type=int, default=None,
                   help="[profile] Max timeline posts (default: 10)")
    p.add_argument("--max-scrolls", type=int, default=None,
                   help="[profile] Max scroll rounds for posts (default: 10)")
    p.add_argument("--cookie-file", default="",
                   help="Path to Netscape/JSON cookie file (injected via CDP)")
    p.add_argument("--cookie-string", default="",
                   help="Raw cookie string (e.g. 'c_user=123; xs=abc')")
    p.add_argument("--cookie-domain", default=".facebook.com",
                   help="Cookie domain (default: .facebook.com)")
    p.add_argument("--browser", default="auto",
                   help="Browser: auto|chromium|google-chrome|brave|edge (default: auto)")
    p.add_argument("--max-rounds", type=int, default=50,
                   help="Max click-loop rounds (default 50)")
    p.add_argument("--click-pause", type=float, default=4.0,
                   help="Seconds between click rounds (default 4.0)")
    p.set_defaults(func=cmd_crawl)

    # clean (FB-specific)
    p = sub.add_parser("clean", help="Clean raw file → clean.jsonl + quarantine + stats + clean_manifest")
    p.add_argument("file", help="Path to raw .json file")
    p.add_argument("--cross-dedup", action="store_true",
                   help="Skip records whose cleaned-text hash matches any existing "
                        "data/posts/*/clean.jsonl (cross-run dedup)")
    p.add_argument("--output-dir", default=None,
                   help="Output directory (default: auto-detect from input location)")
    p.set_defaults(func=cmd_clean)

    # export (FB-specific)
    p = sub.add_parser("export", help="Export clean JSONL to CSV/JSON/Parquet")
    p.add_argument("input", help="Input JSONL file (e.g. clean.jsonl)")
    p.add_argument("format", choices=["csv", "json", "parquet"],
                   help="Output format")
    p.add_argument("output", nargs="?", default=None,
                   help="Output path (default: <input_stem>.<ext>)")
    p.set_defaults(func=cmd_export)

    # bulk (FB-specific)
    p = sub.add_parser("bulk", help="Bulk crawl from URL list file")
    p.add_argument("urls_file", help="File with URLs (1 per line)")
    p.add_argument("--count", type=int, default=10,
                   help="Max posts to crawl (default: 10)")
    p.add_argument("--group", default=None,
                   help="Group URL for auto-finding more posts if URLs insufficient")
    p.add_argument("--no-auto-find", action="store_true",
                   help="Disable auto-find from group feed")
    p.set_defaults(func=cmd_bulk)

    # schedule (delegates to _schedule.py)
    p = sub.add_parser("schedule", help="Manage scheduled jobs (YAML config)")
    p_sub = p.add_subparsers(dest="subcmd", required=True)
    p_sub.add_parser("list", help="List jobs")
    p_sub.add_parser("validate", help="Validate schedule.yaml")
    p_show = p_sub.add_parser("show", help="Show one job")
    p_show.add_argument("name")
    p_run = p_sub.add_parser("run", help="Run a job once")
    p_run.add_argument("name")
    p_add = p_sub.add_parser("add", help="Add a new job")
    p_add.add_argument("name")
    p_add.add_argument("kind", choices=["group", "post", "page", "deep",
                                          "timeline", "profile"])
    p_add.add_argument("url")
    p_add.add_argument("count", type=int, nargs="?", default=10)
    p.set_defaults(func=cmd_schedule)

    # audit (delegates to _audit.py)
    p = sub.add_parser("audit", help="Audit dashboard for crawl runs")
    p.add_argument("--json", default=None,
                   help="Write JSON output to this path")
    p.add_argument("--since", default=None,
                   help="Filter to last N (e.g. 7d, 24h, 30m)")
    p.add_argument("--script", default=None,
                   help="Filter to specific script (e.g. 05, 08)")
    p.add_argument("--root", default=None,
                   help="Root directory to scan")
    p.set_defaults(func=cmd_audit)

    # list (FB-specific)
    p = sub.add_parser("list", help="List raw + clean files")
    p.set_defaults(func=cmd_list)

    # stealth (delegate to stealth_cli.py)
    p_stealth = sub.add_parser("stealth", help="Anti-bot / stealth (delegates to stealth_cli.py)")
    p_stealth_sub = p_stealth.add_subparsers(dest="stealth_cmd", required=True)

    p_status = p_stealth_sub.add_parser("status", help="Report current stealth state")
    p_status.set_defaults(func=cmd_stealth_status)

    p_patch = p_stealth_sub.add_parser("patch", help="Patch a chromedriver binary")
    p_patch.add_argument("--chromedriver", required=True)
    p_patch.add_argument("--backup", action="store_true")
    p_patch.set_defaults(func=cmd_stealth_patch)

    p_inject = p_stealth_sub.add_parser("inject", help="Inject stealth init script via CDP")
    p_inject.add_argument("--locale", default="vi-VN")
    p_inject.set_defaults(func=cmd_stealth_inject)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()