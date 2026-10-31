"""Freshness (ADR-0002): one daemon thread polls record mtimes and publishes versioned snapshots."""
from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import record as R
from . import snapshot as S

_FILES = ("ledger.jsonl", "state.json", "questions.md", "charter.md", "inbox.jsonl")
_DIRS = ("backlog", "reports", "specs", "decisions")


def _stat_pair(p: Path) -> tuple[int, int]:
    try:
        st = p.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def fingerprint(record: Path) -> tuple:
    parts = [(name, _stat_pair(record / name)) for name in _FILES]
    for d in _DIRS:
        try:
            names = sorted(p for p in (record / d).glob("*.md"))
        except OSError:
            names = []
        parts += [(f"{d}/{p.name}", _stat_pair(p)) for p in names]
    return tuple(parts)


def _significant(snap: dict) -> tuple:
    """What a 10 s activity/spend recompute is allowed to republish on (ADR-0002 point 1)."""
    act, spend = snap.get("activity", {}), snap.get("spend", {})
    ev, tr = spend.get("events", {}), spend.get("transcripts", {})
    runner = (snap.get("control") or {}).get("runner")
    return (repr(runner), act.get("status"), repr(act.get("agents")), repr(act.get("phase")),
            ev.get("cost_usd"), ev.get("tokens"), tr.get("tokens"), tr.get("calls"))


class Watcher(threading.Thread):
    """Daemon thread. `.snapshot`, `.version`, `.checked_at`, `.subscribe()`; `poll_once()` for tests."""

    def __init__(self, project_root: Path, record: Path, *, transcripts: str | None = None,
                 talos_dir: str | None = None, poll_seconds: float = 1.0, activity_seconds: float = 10.0):
        super().__init__(name="viz-watcher", daemon=True)
        self.project_root, self.record = Path(project_root), Path(record)
        self.transcripts, self.talos_dir = transcripts, talos_dir
        self.poll_seconds, self.activity_seconds = poll_seconds, activity_seconds
        self._mu = threading.Lock()
        self._subs: list[queue.Queue] = []
        self._stop_event = threading.Event()
        self.version = 0
        self.checked_at = datetime.now(timezone.utc)
        self._fp = fingerprint(self.record)
        self.snapshot: dict = {}
        self._last_activity = time.monotonic()
        self._publish(self._build(self.version + 1))

    # -- internals
    def _build(self, version: int) -> dict:
        return S.build(self.project_root, self.record, now=datetime.now(timezone.utc), version=version,
                       checked_at=self.checked_at, transcripts=self.transcripts, talos_dir=self.talos_dir)

    def _publish(self, snap: dict) -> None:
        with self._mu:
            self.version = snap["version"]
            self.snapshot = snap
            for q in list(self._subs):
                q.put(self.version)

    # -- public
    def subscribe(self) -> "queue.Queue[int]":
        q: queue.Queue = queue.Queue()
        with self._mu:
            self._subs.append(q)
        return q

    def subscriber_count(self) -> int:
        with self._mu:
            return len(self._subs)

    def unsubscribe(self, q: "queue.Queue[int]") -> None:
        with self._mu:
            if q in self._subs:
                self._subs.remove(q)

    def poll_once(self) -> bool:
        """One poll. Returns True when a new snapshot version was published."""
        self.checked_at = datetime.now(timezone.utc)
        self.snapshot["checked_at"] = R.iso(self.checked_at)
        fp = fingerprint(self.record)
        if fp != self._fp:
            self._fp = fp
            self._last_activity = time.monotonic()
            self._publish(self._build(self.version + 1))
            return True
        if S.have_activity() and time.monotonic() - self._last_activity >= self.activity_seconds:
            self._last_activity = time.monotonic()
            cand = self._build(self.version + 1)
            if _significant(cand) != _significant(self.snapshot):
                self._publish(cand)
                return True
        return False

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(self.poll_seconds):
            try:
                self.poll_once()
            except Exception as exc:  # never let the thread die
                print(f"viz: watcher error: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
