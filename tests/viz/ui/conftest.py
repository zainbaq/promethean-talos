"""UI test plumbing (ADR-0006): a stdlib static server over viz/static/ and Playwright fixtures.

`?data=<name>` tests need no product server: `/` and `/index.html` map to viz/static/index.html,
`/static/<path>` to viz/static/<path>, anything else is a 404.
"""
from __future__ import annotations

import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"
STATIC = ROOT / "viz" / "static"
TYPES = {".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".html": "text/html"}

PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 800}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output quiet
        pass

    def _target(self) -> Path | None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            return STATIC / "index.html"
        if path.startswith("/static/"):
            candidate = (STATIC / unquote(path[len("/static/"):])).resolve()
            try:
                candidate.relative_to(STATIC.resolve())
            except ValueError:
                return None
            return candidate if candidate.is_file() else None
        return None

    def _send(self, head_only: bool) -> None:
        target = self._target()
        if target is None:
            body = b'{"error":"not found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
        else:
            body = target.read_bytes()
            self.send_response(200)
            kind = TYPES.get(target.suffix) or mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text/") or kind.endswith("json") else ""))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def do_GET(self):
        self._send(False)

    def do_HEAD(self):
        self._send(True)


class StaticServer(ThreadingHTTPServer):
    """Listen backlog raised from socketserver's default of 5: a page load opens up to six connections at once
    and a full backlog on Windows resets the connection, which drops a stylesheet and makes layout assertions flaky."""

    request_queue_size = 128
    daemon_threads = True


def serve_static(port):
    """Serve viz/static/ on 127.0.0.1:<port> until killed."""
    StaticServer(("127.0.0.1", int(port)), Handler).serve_forever()


def _browsers_path() -> Path | None:
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return Path(env)
    guess = Path(sys.executable).parents[1] / "ms-playwright"
    if guess.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(guess)
        return guess
    return None


@pytest.fixture(scope="session")
def static_url():
    server = StaticServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def browser():
    path = _browsers_path()
    if path is None or not path.exists():
        pytest.skip("playwright browser missing")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        try:
            b = pw.chromium.launch()
        except Exception:  # browser binary absent
            pytest.skip("playwright browser missing")
        yield b
        b.close()


@pytest.fixture
def open_page(browser, static_url):
    """Factory: open_page("view=now&data=sample-company", size=PHONE, scheme="dark", reduced=False) -> page."""
    made = []

    def factory(query, size=DESKTOP, scheme="light", reduced=None, init_script=None, wait="#phase", clipboard=True):
        context = browser.new_context(viewport=size, color_scheme=scheme, reduced_motion=reduced or "no-preference")
        if clipboard:
            context.grant_permissions(["clipboard-read", "clipboard-write"], origin=static_url)
        page = context.new_page()
        page.errors = []
        page.log = []
        page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
        page.on("console", lambda m: page.log.append(m.text))
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        page.on("requestfailed", lambda r: page.log.append(f"request failed: {r.url} {r.failure}"))
        if init_script:
            page.add_init_script(init_script)
        page.goto(f"{static_url}/?{query}")
        if wait:
            try:
                page.wait_for_selector(wait, timeout=10000)
            except Exception:
                raise AssertionError(f"{wait} never appeared for ?{query}; log={page.log}; body={page.evaluate('document.body.innerHTML.slice(0, 300)')}")
        failed = [m for m in page.log if m.startswith("request failed: ")]
        assert not failed, f"test server dropped requests for ?{query} (infrastructure, not the product): {failed}"
        sheets = page.evaluate("[document.styleSheets.length, document.querySelectorAll('link[rel=stylesheet]').length]")
        assert sheets[0] == sheets[1], f"{sheets[0]} of {sheets[1]} stylesheets applied for ?{query} (infrastructure, not the product); log={page.log}"
        made.append(context)
        return page

    yield factory
    for context in made:
        context.close()


@pytest.fixture
def page(open_page):
    """Desktop light page on Now with the sample record; the clipboard grant is made before the first goto."""
    return open_page("view=now&data=sample-company&motion=reduce")
