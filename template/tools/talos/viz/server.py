"""HTTP server (ADR-0001, ADR-0002): static shell, /api/snapshot, /api/events (SSE). Read-only, stdlib only."""
from __future__ import annotations

import argparse
import gzip
import ipaddress
import json
import mimetypes
import queue
import socket
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import hierarchy as H
from . import record as R
from .projects import Projects
from .watch import Watcher

PLACEHOLDER_HTML = "<!doctype html><title>viz</title><p>viz: shell not installed; /api/snapshot is live.</p>"

STATIC_DIR = Path(__file__).resolve().parent / "static"

_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
    ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
}

PING_SECONDS = 15.0

MISDIRECTED = b'{"error":"misdirected"}'


def allowed_hosts(host: str, allow_hosts) -> frozenset[str]:
    """ADR-0008 point 3: the names (lower-cased, no port) a Host header may carry besides an IP literal."""
    return frozenset(["localhost", socket.gethostname().lower(), host.lower(), *(a.lower() for a in allow_hosts)])


def host_name(raw: str | None) -> str | None:
    """ADR-0008 point 2: Host minus any :port, lower-cased; an IPv6 literal keeps its brackets. None when unusable."""
    if raw is None:
        return None
    raw = raw.strip().lower()
    if raw.startswith("["):
        end = raw.find("]")
        return raw[:end + 1] if end > 0 else None
    return raw.partition(":")[0] or None


def host_allowed(raw: str | None, allowed: frozenset[str]) -> bool:
    """True when the request may proceed: name is in `allowed` or is an IP literal (ADR-0008 point 3)."""
    name = host_name(raw)
    if name is None:
        return False
    if name in allowed:
        return True
    try:
        ipaddress.ip_address(name.strip("[]"))
    except ValueError:
        return False
    return True


class _StaticSource:
    """Stands in for the Watcher when --snapshot serves a fixed file."""

    def __init__(self, snap: dict):
        self.snapshot = snap
        self.version = snap.get("version") if isinstance(snap.get("version"), int) else 1
        self.checked_at = datetime.now(timezone.utc)

    def subscribe(self) -> "queue.Queue[int]":
        return queue.Queue()

    def unsubscribe(self, q) -> None:
        pass


def _make_handler(projects: Projects, static_dir: Path, allowed: frozenset[str]):
    static_root = static_dir.resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "viz"
        sys_version = ""

        def log_message(self, fmt, *args):  # quiet; the server writes only the listening line
            pass

        # -- helpers
        def _send(self, status: int, ctype: str, body: bytes, extra: dict | None = None, head: bool = False) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _host_ok(self) -> bool:  # ADR-0008: runs before routing, before any file or snapshot read
            hosts = self.headers.get_all("Host") or []
            return len(hosts) == 1 and host_allowed(hosts[0], allowed)

        def _misdirected(self) -> None:
            self._send(421, "application/json; charset=utf-8", MISDIRECTED, {"Connection": "close"},
                       head=self.command == "HEAD")
            self.close_connection = True

        def _not_found(self, head: bool) -> None:
            self._send(404, "application/json; charset=utf-8", b'{"error":"not found"}', head=head)

        def _static(self, rel: str, head: bool) -> None:
            if not rel or rel.endswith("/") or "\\" in rel or ":" in rel or "\x00" in rel or rel.startswith("/"):
                return self._not_found(head)
            if any(part in ("..", ".") or part == "" for part in rel.split("/")):
                return self._not_found(head)
            target = (static_root / rel).resolve()
            try:
                target.relative_to(static_root)
            except ValueError:
                return self._not_found(head)
            if not target.is_file():
                return self._not_found(head)
            try:
                body = target.read_bytes()
            except OSError:
                return self._not_found(head)
            ctype = _TYPES.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, ctype, body, {"Cache-Control": "no-cache"}, head)

        def _source(self):
            """The project named by ?p=<id> (the --root record when absent); None after a 404 was sent."""
            vals = parse_qs(urlsplit(self.path).query).get("p")
            src = projects.source(vals[0] if vals else None)
            if src is None:
                self._send(404, "application/json; charset=utf-8", b'{"error":"unknown project"}', head=self.command == "HEAD")
            return src

        def _projects(self, head: bool) -> None:
            body = json.dumps({"projects": projects.scan()}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body, {"Cache-Control": "no-store"}, head)

        def _json(self, data: dict, head: bool) -> None:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            extra = {"Cache-Control": "no-store", "Vary": "Accept-Encoding"}
            if "gzip" in self.headers.get("Accept-Encoding", ""):
                body = gzip.compress(body, compresslevel=5)
                extra["Content-Encoding"] = "gzip"
            self._send(200, "application/json; charset=utf-8", body, extra, head)

        def _snapshot(self, head: bool) -> None:
            source = self._source()
            if source is None:
                return
            self._json(source.snapshot, head)

        def _hierarchy(self, head: bool) -> None:
            source = self._source()
            if source is None:
                return
            if not isinstance(source, Watcher):  # --snapshot serves a fixed file: there is no record to read
                return self._send(404, "application/json; charset=utf-8", b'{"error":"no record"}', head=head)
            ledger, _ = R.read_ledger(source.record / "ledger.jsonl")
            self._json(H.build(source.project_root, source.record, ledger, source.transcripts, source.talos_dir), head)

        def _events(self, head: bool) -> None:
            source = self._source()
            if source is None:
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            if head:
                return
            q = source.subscribe()

            def emit(event: str, version: int) -> None:
                data = {"version": version, "checked_at": R.iso(source.checked_at)}
                if event == "change":
                    data["generated_at"] = source.snapshot.get("generated_at")
                self.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8"))
                self.wfile.flush()

            try:
                self.wfile.write(b"retry: 2000\n\n")
                sent = source.version
                emit("hello", sent)
                while True:
                    try:
                        v = q.get(timeout=PING_SECONDS)
                    except queue.Empty:
                        emit("ping", sent)
                        continue
                    while True:  # collapse a burst into the newest version
                        try:
                            v = max(v, q.get_nowait())
                        except queue.Empty:
                            break
                    if v > sent:
                        sent = v
                        emit("change", sent)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                return
            finally:
                source.unsubscribe(q)
                self.close_connection = True

        def _route(self, head: bool) -> None:
            path = urlsplit(self.path).path
            if path in ("/", "/index.html"):
                index = static_root / "index.html"
                if index.is_file():
                    return self._send(200, "text/html; charset=utf-8", index.read_bytes(), {"Cache-Control": "no-cache"}, head)
                return self._send(200, "text/html; charset=utf-8", PLACEHOLDER_HTML.encode("utf-8"), {"Cache-Control": "no-cache"}, head)
            if path.startswith("/static/"):
                return self._static(unquote(path[len("/static/"):]), head)
            if path == "/api/snapshot":
                return self._snapshot(head)
            if path == "/api/hierarchy":
                return self._hierarchy(head)
            if path == "/api/events":
                return self._events(head)
            if path == "/api/projects":
                return self._projects(head)
            self._not_found(head)

        # -- verbs
        def do_GET(self):
            if not self._host_ok():
                return self._misdirected()
            self._route(False)

        def do_HEAD(self):
            if not self._host_ok():
                return self._misdirected()
            self._route(True)

        def _no(self):
            if not self._host_ok():
                return self._misdirected()
            self._send(405, "application/json; charset=utf-8", b'{"error":"method not allowed"}', {"Allow": "GET, HEAD"})

        def __getattr__(self, name):  # ADR-0001 point 3: every method other than GET and HEAD answers 405, never 501
            if name.startswith("do_"):
                return self._no
            raise AttributeError(name)

    return Handler


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows SO_REUSEADDR would let a second process share the port


def serve(project_root: Path, record: Path, host: str, port: int, *, snapshot_file=None,
          transcripts=None, talos_dir=None, allow_hosts=(), scan_dirs=()) -> None:
    if snapshot_file is not None:
        projects = Projects(project_root, record, primary_source=_StaticSource(json.loads(Path(snapshot_file).read_text(encoding="utf-8"))))
    else:
        projects = Projects(project_root, record, scan_dirs, transcripts=transcripts, talos_dir=talos_dir)
        projects.source(None)
    httpd = _Server((host, port), _make_handler(projects, STATIC_DIR, allowed_hosts(host, allow_hosts)))
    print(f"viz: listening on http://{host}:{httpd.server_address[1]}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        projects.stop()


def resolve_record(root: Path) -> tuple[Path, Path] | None:
    """(project_root, record) for --root, per ADR-0001 point 2; None when it holds no record."""
    root = root.resolve()
    if (root / "company" / "ledger.jsonl").exists() or (root / "company").is_dir():
        return root, root / "company"
    if (root / "ledger.jsonl").exists():
        return root.parent, root
    return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m viz", description="Serve a Talos record (read-only).")
    p.add_argument("--root", default=".", help="directory holding company/ (or a record directory itself)")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1; 0.0.0.0 is opt-in)")
    p.add_argument("--port", type=int, default=8000, help="port (0 picks an ephemeral port)")
    p.add_argument("--transcripts", default=None, help="override transcript discovery")
    p.add_argument("--talos-dir", default=None, help="directory holding usage.py")
    p.add_argument("--snapshot", default=None, help="serve this JSON file as /api/snapshot instead of reading a record")
    p.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                   help="also answer requests whose Host is NAME (repeatable; ADR-0008)")
    p.add_argument("--scan", action="append", default=None, metavar="DIR",
                   help="offer every Talos project one level under DIR in the switcher (repeatable; default: the "
                        "folder holding --root; --no-scan for none)")
    p.add_argument("--no-scan", action="store_true", help="offer only the --root project")
    args = p.parse_args(argv)

    if args.snapshot:
        f = Path(args.snapshot)
        try:
            json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"viz: cannot read snapshot file {f}: {exc}", file=sys.stderr)
            return 2
        project_root = record = Path.cwd()
    else:
        root = Path(args.root)
        found = resolve_record(root) if root.is_dir() else None
        if found is None:
            print(f"viz: no Talos record under {root} (expected company/ or ledger.jsonl)", file=sys.stderr)
            return 2
        project_root, record = found
    try:
        scan = [] if args.no_scan or args.snapshot else (args.scan if args.scan is not None else [project_root.parent])
        serve(project_root, record, args.host, args.port, snapshot_file=args.snapshot,
              transcripts=args.transcripts, talos_dir=args.talos_dir, allow_hosts=args.allow_host, scan_dirs=scan)
    except OSError as exc:
        print(f"viz: cannot listen on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 2
    return 0
