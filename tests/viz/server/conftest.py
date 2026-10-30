"""Shared helpers for tests/server (ADR-0006): record copies in tmp_path, CLI oracle by subprocess."""
from __future__ import annotations

import http.client
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"
FIXTURE = REPO.parents[2] / "tests" / "viz" / "fixtures" / "sample-company"
PINNED = REPO.parents[2] / "tests" / "viz" / "fixtures" / "snapshots" / "sample-company.json"


def cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    """Run the Talos CLI against `root` (the directory holding company/). Returns the CompletedProcess."""
    env = dict(os.environ, TALOS_ROOT=str(root), TALOS_ACTOR="test-engineer", TALOS_TIER="execution",
               PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    return subprocess.run([sys.executable, str(REPO / "talos.py"), *args], cwd=REPO, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


@pytest.fixture
def record_root(tmp_path: Path) -> Path:
    """Copy of fixtures/sample-company at tmp_path/proj/company; returns tmp_path/proj."""
    proj = tmp_path / "proj"
    shutil.copytree(FIXTURE, proj / "company")
    return proj


@pytest.fixture
def run_cli():
    return cli


class Viz:
    """A `python -m viz` subprocess on an ephemeral port."""

    def __init__(self, *argv: str):
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        self.proc = subprocess.Popen([sys.executable, "-m", "viz", *argv, "--port", "0"], cwd=REPO, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        line = self.proc.stdout.readline()
        assert line.startswith("viz: listening on http://127.0.0.1:"), f"unexpected first line {line!r}"
        self.port = int(line.strip().rstrip("/").rsplit(":", 1)[1])

    def get(self, path: str, headers: dict | None = None, method: str = "GET"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp, body

    def snapshot(self) -> dict:
        resp, body = self.get("/api/snapshot")
        assert resp.status == 200
        return json.loads(body)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except Exception:
                pass


@pytest.fixture
def start_viz():
    started: list[Viz] = []

    def start(*argv: str) -> Viz:
        v = Viz(*argv)
        started.append(v)
        return v

    yield start
    for v in started:
        v.close()


class SSE:
    """Minimal SSE client: a reader thread pushes (event, data, received_at) onto .events."""

    def __init__(self, port: int):
        self.conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        self.conn.request("GET", "/api/events")
        self.resp = self.conn.getresponse()
        assert self.resp.status == 200
        self.events: queue.Queue = queue.Queue()
        self._t = threading.Thread(target=self._read, daemon=True)
        self._t.start()

    def _read(self) -> None:
        name = None
        try:
            while True:
                raw = self.resp.fp.readline()
                if not raw:
                    return
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    name = line[7:]
                elif line.startswith("data: ") and name:
                    self.events.put((name, json.loads(line[6:]), time.monotonic()))
                    name = None
        except Exception:
            return

    def next(self, kind: str, timeout: float):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(f"no {kind!r} event within {timeout} s")
            try:
                name, data, at = self.events.get(timeout=remaining)
            except queue.Empty:
                continue
            if name == kind:
                return data, at

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
