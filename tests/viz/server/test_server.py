from __future__ import annotations

import gzip
import http.client
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from viz import server

from .conftest import FIXTURE, REPO, SSE, cli


def test_routes(record_root, start_viz):
    v = start_viz("--root", str(record_root))
    index = server.STATIC_DIR / "index.html"
    expected = index.read_bytes() if index.is_file() else server.PLACEHOLDER_HTML.encode("utf-8")
    resp, body = v.get("/")
    assert resp.status == 200 and resp.getheader("Content-Type") == "text/html; charset=utf-8"
    assert body == expected
    resp, body = v.get("/index.html")
    assert resp.status == 200 and body == expected

    resp, body = v.get("/api/snapshot", {"Accept-Encoding": "gzip"})
    assert resp.status == 200
    assert resp.getheader("Content-Type") == "application/json; charset=utf-8"
    assert resp.getheader("Cache-Control") == "no-store"
    assert resp.getheader("Content-Encoding") == "gzip"
    assert json.loads(gzip.decompress(body))["counts"]["events"] == 68
    resp, body = v.get("/api/snapshot")
    assert resp.getheader("Content-Encoding") is None and json.loads(body)["schema"] == 1

    assert v.get("/static/../server.py")[0].status == 404
    assert v.get("/static/%2e%2e/server.py")[0].status == 404
    assert v.get("/static/..%2fserver.py")[0].status == 404
    assert v.get("/static/")[0].status == 404
    assert v.get("/static/C:/Windows/win.ini")[0].status == 404
    assert v.get("/static/..\\server.py")[0].status == 404

    resp, body = v.get("/api/snapshot", method="POST")
    assert resp.status == 405
    for m in ("PUT", "DELETE", "PATCH", "OPTIONS", "TRACE", "CONNECT", "BREW"):
        resp, body = v.get("/", method=m)
        assert resp.status == 405 and resp.getheader("Allow") == "GET, HEAD", m
        assert body == b'{"error":"method not allowed"}'
    resp, body = v.get("/nothing")
    assert resp.status == 404 and body == b'{"error":"not found"}'
    resp, body = v.get("/api/snapshot", method="HEAD")
    assert resp.status == 200 and body == b""


def test_sse_change(record_root, start_viz):
    v = start_viz("--root", str(record_root))
    sse = SSE(v.port)
    try:
        hello, _ = sse.next("hello", 10)
        assert isinstance(hello["version"], int) and isinstance(hello["checked_at"], str)
        last = hello["version"]
        for i in range(3):
            r = cli(record_root, "log", "note", "--summary", "freshness probe")
            assert r.returncode == 0, r.stderr
            exited = time.monotonic()
            data, at = sse.next("change", 10)
            assert at - exited < 10
            assert data["version"] > last
            assert isinstance(data["generated_at"], str)
            last = data["version"]
            snap = v.snapshot()
            assert snap["version"] == last
            assert snap["events"][0]["summary"] == "freshness probe"
    finally:
        sse.close()


def test_unicode_roundtrip(record_root, start_viz):
    v = start_viz("--root", str(record_root))
    state = json.loads((record_root / "company" / "state.json").read_text(encoding="utf-8"))
    snap = v.snapshot()
    assert snap["cycle"]["budget"] == state["budget"] and "\u00a7" in snap["cycle"]["budget"]
    sse = SSE(v.port)
    try:
        sse.next("hello", 10)
        text = "probe \u00a7 \u00e9 \u6f22\u5b57"
        assert cli(record_root, "log", "note", "--summary", text).returncode == 0
        sse.next("change", 10)
        assert v.snapshot()["events"][0]["summary"] == text
    finally:
        sse.close()


def test_concurrent_clients(record_root, start_viz):
    v = start_viz("--root", str(record_root))
    a, b = SSE(v.port), SSE(v.port)
    try:
        ha, _ = a.next("hello", 10)
        hb, _ = b.next("hello", 10)
        assert cli(record_root, "log", "note", "--summary", "one write").returncode == 0
        ca, _ = a.next("change", 10)
        cb, _ = b.next("change", 10)
        assert ca["version"] == cb["version"] > ha["version"]
        time.sleep(2.5)  # a single write yields a single change
        assert a.events.empty() or a.events.get()[0] != "change"
    finally:
        a.close()
        b.close()


def test_snapshot_file(start_viz):
    path = REPO.parents[2] / "tests" / "viz" / "fixtures" / "snapshots" / "live-active.json"
    v = start_viz("--snapshot", str(path))
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert v.snapshot() == expected
    sse = SSE(v.port)
    try:
        hello, _ = sse.next("hello", 10)
        assert isinstance(hello["version"], int)
    finally:
        sse.close()


def test_bad_root_exits_2(tmp_path):
    r = subprocess.run([sys.executable, "-m", "viz", "--root", str(tmp_path / "nope"), "--port", "0"], cwd=REPO,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 2
    assert len(r.stderr.strip().splitlines()) == 1 and r.stdout == ""
    r = subprocess.run([sys.executable, "-m", "viz", "--snapshot", str(tmp_path / "nope.json"), "--port", "0"],
                       cwd=REPO, capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and len(r.stderr.strip().splitlines()) == 1


def test_fixture_dir_as_record(start_viz):
    v = start_viz("--root", str(FIXTURE))
    snap = v.snapshot()
    assert snap["counts"]["events"] == 68 and snap["project"]["name"] == "focus"


def test_long_record(tmp_path, start_viz):
    """612 events = the fixture ledger repeated 9 times with fresh ids."""
    proj = tmp_path / "proj"
    shutil.copytree(FIXTURE, proj / "company")
    lines = (FIXTURE / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    out = []
    for n in range(9):
        for ln in lines:
            e = json.loads(ln)
            e["id"] = f"{e['id']}-r{n}"
            if e.get("run"):
                e["run"] = f"{e['run']}-r{n}"
            out.append(json.dumps(e, ensure_ascii=False))
    (proj / "company" / "ledger.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    v = start_viz("--root", str(proj))
    t0 = time.perf_counter()
    snap = v.snapshot()
    assert time.perf_counter() - t0 < 1
    assert snap["counts"]["events"] == len(out) == 612
    sse = SSE(v.port)
    try:
        sse.next("hello", 10)
        assert cli(proj, "log", "note", "--summary", "long probe").returncode == 0
        exited = time.monotonic()
        _, at = sse.next("change", 10)
        assert at - exited < 10
    finally:
        sse.close()


def test_no_runtime_network():
    static = server.STATIC_DIR
    files = [p for p in static.rglob("*") if p.is_file() and p.suffix in (".html", ".css", ".js", ".mjs")] if static.is_dir() else []
    for text in [server.PLACEHOLDER_HTML] + [p.read_text(encoding="utf-8") for p in files]:
        text = text.replace("http://www.w3.org/2000/svg", "")  # the SVG namespace name (ADR-0005), not a URL any fetch uses
        assert "http://" not in text and "https://" not in text


def raw_status(port: int, request: bytes) -> int:
    """Send `request` on a bare socket, read to EOF, return the status code of the status line."""
    with socket.create_connection(("127.0.0.1", port), timeout=15) as s:
        s.sendall(request)
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    return int(data.split(b" ", 2)[1])


def test_host_allowlist(record_root, start_viz):
    v = start_viz("--root", str(record_root))
    resp, body = v.get("/api/snapshot", {"Host": "evil.example:8000"})
    assert resp.status == 421 and body == b'{"error":"misdirected"}'
    assert resp.getheader("Content-Type") == "application/json; charset=utf-8"
    me = socket.gethostname()
    for host in ("127.0.0.1:1", "localhost", me, me.upper() + ":9", "[::1]:8000", "100.64.0.10:8000"):
        assert v.get("/api/snapshot", {"Host": host})[0].status == 200, host
    assert v.get("/api/snapshot", {"Host": "preview.local"})[0].status == 421
    assert v.get("/api/snapshot", {"Host": me + ".evil.example"})[0].status == 421
    assert raw_status(v.port, b"GET /api/snapshot HTTP/1.1\r\n\r\n") == 421
    assert raw_status(v.port, b"GET /api/snapshot HTTP/1.1\r\nHost: localhost\r\nHost: localhost\r\n\r\n") == 421
    resp, body = v.get("/api/snapshot", {"Host": "evil.example"}, method="HEAD")
    assert resp.status == 421 and body == b""
    resp, body = v.get("/api/snapshot", {"Host": "evil.example"}, method="POST")
    assert resp.status == 421
    w = start_viz("--root", str(record_root), "--allow-host", "preview.local")
    assert w.get("/api/snapshot", {"Host": "preview.local"})[0].status == 200
    assert w.get("/api/snapshot", {"Host": "PREVIEW.LOCAL:8000"})[0].status == 200
    assert w.get("/api/snapshot", {"Host": "evil.example"})[0].status == 421


def test_host_check_precedes_reads(tmp_path):
    """ADR-0008 point 3: a misdirected request touches neither the snapshot source nor the static directory."""

    class Tripwire:
        version = 1
        checked_at = datetime.now(timezone.utc)

        @property
        def snapshot(self):
            raise AssertionError("snapshot read before the Host check")

        def subscribe(self):
            raise AssertionError("subscribe before the Host check")

        def unsubscribe(self, q):
            pass

    handler = server._make_handler(Tripwire(), tmp_path / "missing", server.allowed_hosts("127.0.0.1", ()))
    httpd = server._Server(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        for path in ("/", "/index.html", "/api/snapshot", "/api/events", "/static/app.js", "/nothing"):
            t0 = time.perf_counter()
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
            conn.request("GET", path, headers={"Host": "evil.example"})
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            assert resp.status == 421 and body == b'{"error":"misdirected"}', path
            assert resp.getheader("Content-Type") == "application/json; charset=utf-8"
            assert time.perf_counter() - t0 < 1, path
        assert raw_status(port, b"GET /api/events HTTP/1.1\r\n\r\n") == 421
        assert raw_status(port, b"GET /api/snapshot HTTP/1.0\r\n\r\n") == 421
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---- the project switcher: /api/projects lists what the server found; ?p=<id> picks one; unknown ids are 404 ----
def test_projects_switch(tmp_path, start_viz):
    from .conftest import FIXTURE
    for name in ("alpha", "beta"):
        shutil.copytree(FIXTURE, tmp_path / name / "company")
    (tmp_path / "not-a-project").mkdir()
    v = start_viz("--root", str(tmp_path / "alpha"))
    resp, body = v.get("/api/projects")
    assert resp.status == 200
    projects = json.loads(body)["projects"]
    assert [p["folder"] for p in projects] == ["alpha", "beta"] and projects[0]["primary"] is True
    beta = projects[1]["id"]
    resp, body = v.get(f"/api/snapshot?p={beta}")
    assert resp.status == 200 and json.loads(body)["project"]["folder"] == "beta"
    resp, _ = v.get("/api/snapshot?p=../../etc")
    assert resp.status == 404
    resp, body = v.get("/api/projects", method="POST")
    assert resp.status == 405
