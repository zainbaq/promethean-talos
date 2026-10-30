"""Projects: the records this server may show. The --root record, plus every folder one level under each --scan
directory that holds a Talos record. The page names a project by a short id, never by a path, so it can only open
what the server found. Each project gets its own Watcher, started on first request."""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

from . import record as R
from .watch import Watcher

MAX_WATCHERS = 6


def project_id(root: Path) -> str:
    return hashlib.sha1(str(root.resolve()).lower().encode("utf-8")).hexdigest()[:10]


def _record_of(folder: Path) -> Path | None:
    rec = folder / "company"
    return rec if (rec / "ledger.jsonl").is_file() else None


def _name(record: Path, folder: str) -> str:
    try:
        text = (record / "charter.md").read_text(encoding="utf-8")
    except OSError:
        text = ""
    try:
        return R.display_name(text, folder)
    except Exception:  # a malformed charter never hides the project
        return folder


class Projects:
    def __init__(self, project_root: Path, record: Path, scan_dirs=(), *, transcripts=None, talos_dir=None,
                 primary_source=None):
        self.primary = {"id": project_id(project_root), "root": Path(project_root).resolve(), "record": Path(record).resolve()}
        self.scan_dirs = [Path(d).resolve() for d in scan_dirs]
        self.transcripts, self.talos_dir = transcripts, talos_dir
        self._mu = threading.Lock()
        self._known: dict[str, dict] = {self.primary["id"]: self.primary}
        self._sources: dict[str, object] = {}
        self._used: list[str] = []
        if primary_source is not None:
            self._sources[self.primary["id"]] = primary_source

    def scan(self) -> list[dict]:
        """Rescan the scan directories; returns the project list for /api/projects, the primary first."""
        found = {self.primary["id"]: self.primary}
        for d in self.scan_dirs:
            try:
                children = sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith("."))
            except OSError:
                continue
            for folder in children:
                rec = _record_of(folder)
                if rec is None:
                    continue
                pid = project_id(folder)
                found.setdefault(pid, {"id": pid, "root": folder.resolve(), "record": rec.resolve()})
        with self._mu:
            self._known = found
        out = []
        for p in found.values():
            try:
                last = (p["record"] / "ledger.jsonl").stat().st_mtime
            except OSError:
                last = None
            out.append({"id": p["id"], "name": _name(p["record"], p["root"].name), "folder": p["root"].name,
                        "path": str(p["root"]).replace("\\", "/"), "primary": p["id"] == self.primary["id"],
                        "last_write": last})
        rest = sorted(out[1:], key=lambda x: -(x["last_write"] or 0))
        return out[:1] + rest

    def source(self, pid: str | None):
        """The snapshot source for a project id (None: the primary). None when the id is unknown."""
        pid = pid or self.primary["id"]
        with self._mu:
            known = pid in self._known
        if not known:
            self.scan()
        with self._mu:
            p = self._known.get(pid)
            if p is None:
                return None
            src = self._sources.get(pid)
            if src is None:
                src = Watcher(p["root"], p["record"], transcripts=self.transcripts if pid == self.primary["id"] else None,
                              talos_dir=self.talos_dir)
                src.start()
                self._sources[pid] = src
            if pid in self._used:
                self._used.remove(pid)
            self._used.append(pid)
            self._evict()
            return src

    def _evict(self) -> None:
        """Keep at most MAX_WATCHERS running; the primary and any watcher with a live stream are never stopped."""
        for pid in list(self._used):
            if len(self._sources) <= MAX_WATCHERS:
                return
            src = self._sources.get(pid)
            if pid == self.primary["id"] or not isinstance(src, Watcher) or src.subscriber_count():
                continue
            src.stop()
            del self._sources[pid]
            self._used.remove(pid)

    def stop(self) -> None:
        with self._mu:
            for src in self._sources.values():
                if isinstance(src, Watcher):
                    src.stop()
