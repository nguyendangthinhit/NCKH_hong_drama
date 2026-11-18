"""Repair legacy platform='news' metadata without rebuilding event contents.

Preview: python repair-platforms.py
Apply:   python repair-platforms.py --apply   (creates a SQLite backup first)
"""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from platforms import normalize_platform, preferred_platform, resolve_platform

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw = json.loads((ROOT / "data/raw/data_web.json").read_text(encoding="utf-8-sig"))
    source_events = {event["id_content"]: event for items in raw.values() for event in items}
    mode = "rw" if args.apply else "ro"
    conn = sqlite3.connect(f"file:{(BACKEND / 'events.db').as_posix()}?mode={mode}", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        before = [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY id_content")]
        changes = []
        counts = Counter()
        for row in before:
            raw_event = source_events.get(row["id_content"], {})
            stored = normalize_platform(row["platform"])
            explicit = preferred_platform(raw_event.get("platform"), stored if stored != "news" else None)
            platform = resolve_platform(json.loads(row["links"] or "[]"), raw_event.get("source_url"), explicit)
            counts[platform] += 1
            if platform != row["platform"]:
                changes.append((platform, row["id_content"], row["platform"]))
        result = {"total": len(before), "before": dict(Counter(row["platform"] for row in before)),
                  "after": dict(counts), "changed": len(changes), "applied": False}
        if args.apply and changes:
            backup_dir = ROOT / "_tmp"
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = backup_dir / f"events-before-platform-fix-{timestamp}.db"
            with closing(sqlite3.connect(backup_path)) as backup:
                conn.backup(backup)
            conn.execute("BEGIN IMMEDIATE")
            for platform, event_id, previous in changes:
                updated = conn.execute("UPDATE events SET platform = ? WHERE id_content = ? AND platform IS ?",
                                       (platform, event_id, previous))
                if updated.rowcount != 1:
                    raise RuntimeError(f"Event changed during repair: {event_id}")
            after = [dict(row) for row in conn.execute("SELECT * FROM events ORDER BY id_content")]
            without_platform = lambda rows: [{key: value for key, value in row.items() if key != "platform"} for row in rows]
            if without_platform(before) != without_platform(after):
                raise RuntimeError("Fields other than platform changed; rolling back")
            conn.commit()
            result.update(applied=True, backup=str(backup_path))
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
