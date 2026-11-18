"""
Run manifest + checkpoint utility for FB crawl scripts.

Every crawl run (single post deep extraction, group feed crawl, page timeline,
profile crawl, bulk mode) writes a `manifest.json` sidecar in the output folder.
The manifest captures:
  - run_id, script, input_url, input_args, started_at, ended_at, status
  - stages[]: ordered list of named stages with start/end times
  - checkpoint{}: resume point (for scripts that support resume)
  - output_paths{}: paths to all files written by this run
  - errors[]: collected non-fatal errors

For resumable scripts (05_auto_scrape_cdp.py), a `checkpoint.json` file is
written alongside, updated after every long-running round. On restart, the
script can read the checkpoint and skip already-completed work.

Usage:

    from _run_manifest import RunManifest, manifest_path, checkpoint_path, Checkpoint

    # Context manager pattern (preferred)
    with RunManifest(post_dir, script="05_auto_scrape_cdp.py",
                     input_url=post_url, input_args={"target": 100}) as m:
        m.stage("sort_switch")
        m.checkpoint({"phase": "sort_switch", "completed": True})
        m.stage("click_loop")
        for round_i in range(max_rounds):
            # ... do work ...
            m.checkpoint({"phase": "click_loop", "round": round_i,
                          "comments_extracted": total})
        m.output("raw", raw_path)
        m.finish(status="success", counts={"comments": 100})

    # Non-context-manager pattern (for scripts with complex control flow)
    m = RunManifest(post_dir, script="06_crawl_group.py", input_url=group_url)
    m.start()
    try:
        ...
    except Exception as e:
        m.error(str(e))
        m.finish(status="failed")
        raise
    m.finish(status="success")
"""
from __future__ import annotations
import json
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Path helpers (consistent with _data_paths.py conventions)
# ---------------------------------------------------------------------------

def manifest_path(post_dir: str | Path) -> Path:
    """Path to manifest.json for a given post/output folder."""
    return Path(post_dir) / "manifest.json"


def checkpoint_path(post_dir: str | Path) -> Path:
    """Path to checkpoint.json for a given post/output folder."""
    return Path(post_dir) / "checkpoint.json"


def now_iso() -> str:
    """ISO 8601 timestamp with timezone, second precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def gen_run_id() -> str:
    """Short unique ID for a run (timestamp + 8-char uuid suffix)."""
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Checkpoint dataclass
# ---------------------------------------------------------------------------

@dataclass
class Checkpoint:
    """Resume point for long-running scripts.

    `phase` is the current phase name (matches a stage).
    `round` is the round index for iterative loops (click_loop, scroll).
    `completed_phases` is the set of phases already fully completed.
    `extra` carries any script-specific state.
    """
    phase: str = ""
    round: int = 0
    completed_phases: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Checkpoint":
        return cls(
            phase=d.get("phase", ""),
            round=d.get("round", 0),
            completed_phases=list(d.get("completed_phases", [])),
            extra=dict(d.get("extra", {})),
        )

    def is_phase_done(self, phase_name: str) -> bool:
        return phase_name in self.completed_phases


# ---------------------------------------------------------------------------
# RunManifest
# ---------------------------------------------------------------------------

class RunManifest:
    """Audit + resume metadata for a single crawl run.

    Thread-safety: not thread-safe. Use one manifest per crawl process.
    Atomicity: each `save()` writes the full file (small JSON; cheap).
    """

    def __init__(
        self,
        post_dir: str | Path,
        script: str,
        input_url: str = "",
        input_args: dict | None = None,
        resume: bool = True,
    ):
        self.post_dir = Path(post_dir)
        self.script = script
        self.input_url = input_url
        self.input_args = dict(input_args or {})
        self._resume = resume

        # Fields written to manifest
        self.run_id = gen_run_id()
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.status: str = "pending"  # pending | running | success | failed | cancelled
        self.stages: list[dict] = []
        self._current_stage: dict | None = None
        self.checkpoint_data: dict = {}
        self.output_paths: dict[str, str] = {}
        self.errors: list[dict] = []
        self.counts: dict[str, int] = {}
        self.warnings: list[str] = []

        # Resume support
        self._resumed_from: dict | None = None
        if resume:
            existing = self._read_existing()
            if existing:
                self._resumed_from = existing
                self.run_id = existing.get("run_id", self.run_id)
                # Preserve prior stages so resume history is visible
                self.stages = list(existing.get("stages", []))
                self.errors = list(existing.get("errors", []))
                self.warnings = list(existing.get("warnings", []))

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def __enter__(self) -> "RunManifest":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            tb = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            self.error(f"{exc_type.__name__}: {exc_val}", traceback=tb)
            self.finish(status="failed")
        else:
            if self.status == "running":
                self.finish(status="success")

    def start(self) -> None:
        """Mark run as started and write initial manifest."""
        if self.started_at is not None:
            return  # Already started
        self.post_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = now_iso()
        self.status = "running"
        self.save()

    def finish(self, status: str = "success") -> None:
        """Mark run as finished. Closes any open stage."""
        if self._current_stage is not None:
            self._close_stage()
        self.ended_at = now_iso()
        self.status = status
        self.save()

    # -----------------------------------------------------------------------
    # Stages
    # -----------------------------------------------------------------------

    def stage(self, name: str, meta: dict | None = None) -> None:
        """Open a named stage. Auto-closes any previously open stage."""
        if self._current_stage is not None:
            self._close_stage()
        self._current_stage = {
            "name": name,
            "started_at": now_iso(),
            "ended_at": None,
            "meta": dict(meta or {}),
        }

    def _close_stage(self) -> None:
        if self._current_stage is None:
            return
        self._current_stage["ended_at"] = now_iso()
        self.stages.append(self._current_stage)
        self._current_stage = None
        self.save()

    # -----------------------------------------------------------------------
    # Checkpoint
    # -----------------------------------------------------------------------

    def checkpoint(self, data: dict | Checkpoint, persist_every: int = 1,
                   round_index: int | None = None) -> None:
        """Update checkpoint state and optionally persist to disk.

        `persist_every=5` writes checkpoint.json every 5th call (for hot loops).
        `round_index` is used to gate persistence: persist when `round_index % persist_every == 0`.
        """
        if isinstance(data, Checkpoint):
            data = data.to_dict()
        else:
            data = dict(data)
        self.checkpoint_data = data

        should_persist = False
        if round_index is None:
            should_persist = True
        elif round_index % max(1, persist_every) == 0:
            should_persist = True

        if should_persist:
            ckpt_path = checkpoint_path(self.post_dir)
            ckpt_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = ckpt_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                      default=str), encoding="utf-8")
            tmp.replace(ckpt_path)

    @classmethod
    def load_checkpoint(cls, post_dir: str | Path) -> Checkpoint | None:
        """Load checkpoint from disk if it exists."""
        p = checkpoint_path(post_dir)
        if not p.exists():
            return None
        try:
            return Checkpoint.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # Outputs / errors / warnings / counts
    # -----------------------------------------------------------------------

    def output(self, key: str, path: str | Path) -> None:
        """Register an output file path."""
        self.output_paths[key] = str(path)

    def error(self, message: str, traceback: str = "") -> None:
        self.errors.append({
            "at": now_iso(),
            "message": str(message),
            "traceback": traceback,
        })
        self.save()

    def warning(self, message: str) -> None:
        self.warnings.append(f"[{now_iso()}] {message}")

    def count(self, key: str, value: int) -> None:
        """Record a numeric count (e.g. comments=100, posts=10)."""
        self.counts[key] = int(value)

    # -----------------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = {
            "run_id": self.run_id,
            "script": self.script,
            "input_url": self.input_url,
            "input_args": self.input_args,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "stages": self.stages,
            "current_stage": self._current_stage,
            "checkpoint": self.checkpoint_data,
            "output_paths": self.output_paths,
            "errors": self.errors,
            "warnings": self.warnings,
            "counts": self.counts,
        }
        if self._resumed_from is not None:
            d["resumed_from_run_id"] = self._resumed_from.get("run_id")
            d["resumed_at"] = now_iso()
        return d

    def save(self) -> None:
        """Atomically write manifest.json."""
        self.post_dir.mkdir(parents=True, exist_ok=True)
        path = manifest_path(self.post_dir)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2,
                                  default=str), encoding="utf-8")
        tmp.replace(path)

    # -----------------------------------------------------------------------
    # Resume detection
    # -----------------------------------------------------------------------

    def _read_existing(self) -> dict | None:
        """Read existing manifest if it represents an interrupted run we can resume."""
        path = manifest_path(self.post_dir)
        if not path.exists():
            return None
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        # Only consider resumable if status was running (not finished/cancelled)
        if existing.get("status") not in ("running", "pending"):
            return None
        return existing

    @property
    def is_resume(self) -> bool:
        return self._resumed_from is not None


# ---------------------------------------------------------------------------
# Convenience: scan all manifests (used by _audit.py)
# ---------------------------------------------------------------------------

def find_manifests(root: str | Path) -> Iterable[Path]:
    """Yield all manifest.json paths under root (recursive)."""
    root = Path(root)
    if not root.exists():
        return
    yield from root.rglob("manifest.json")


def summarize_manifest(path: Path) -> dict:
    """Read a manifest and return a compact summary for dashboards."""
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"path": str(path), "error": "unreadable"}
    # Compute duration
    duration_s = None
    if m.get("started_at") and m.get("ended_at"):
        try:
            t0 = datetime.fromisoformat(m["started_at"])
            t1 = datetime.fromisoformat(m["ended_at"])
            duration_s = (t1 - t0).total_seconds()
        except Exception:
            pass
    return {
        "path": str(path),
        "run_id": m.get("run_id"),
        "script": m.get("script"),
        "status": m.get("status"),
        "started_at": m.get("started_at"),
        "ended_at": m.get("ended_at"),
        "duration_s": duration_s,
        "counts": m.get("counts", {}),
        "errors": len(m.get("errors", [])),
        "input_url": m.get("input_url", "")[:80],
    }


# ---------------------------------------------------------------------------
# CLI for quick debugging
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 _run_manifest.py test <post_dir>     # roundtrip test")
        print("  python3 _run_manifest.py show <manifest>     # print manifest")
        print("  python3 _run_manifest.py scan <root>         # summarize all manifests")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "test":
        post_dir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/_manifest_test"
        post_dir = Path(post_dir)
        if post_dir.exists():
            import shutil
            shutil.rmtree(post_dir)

        with RunManifest(post_dir, script="_run_manifest.py:test",
                         input_url="https://example.com/test",
                         input_args={"max": 5}) as m:
            m.stage("stage_a", meta={"x": 1})
            m.checkpoint({"phase": "stage_a", "round": 1})
            m.stage("stage_b")
            m.count("items", 42)
            m.output("raw", str(post_dir / "raw.json"))
            m.warning("test warning")

        print(f"✓ Test passed. Manifest at: {manifest_path(post_dir)}")
        print(f"  Status: {json.loads(manifest_path(post_dir).read_text())['status']}")

        # Reopen — should detect resume
        m2 = RunManifest(post_dir, script="retry")
        print(f"  Resume detected: {m2.is_resume}")
        print(f"  Run ID preserved: {m2.run_id}")

    elif cmd == "show":
        print(json.dumps(json.loads(Path(sys.argv[2]).read_text()),
                         indent=2, ensure_ascii=False))

    elif cmd == "scan":
        for p in find_manifests(sys.argv[2]):
            s = summarize_manifest(p)
            dur = f"{s.get('duration_s'):.1f}s" if s.get('duration_s') is not None else "    -  "
            print(f"{s.get('status','?'):8s} {dur:>10}  "
                  f"{s.get('script','?'):40s}  {p}")