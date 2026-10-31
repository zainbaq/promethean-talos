"""The control room's writes: who may write, what each press records, and that chat text stays data."""
from __future__ import annotations

import http.client
import json
import threading

import pytest

from viz import control as C
from viz.projects import Projects
from viz.server import _Server, _make_handler, STATIC_DIR, allowed_hosts

SECRET = "s3cret"


@pytest.fixture
def control_server(record_root):
    projects = Projects(record_root, record_root / "company")
    httpd = _Server(("127.0.0.1", 0), _make_handler(projects, STATIC_DIR, allowed_hosts("127.0.0.1", ()), SECRET))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd.server_address[1], record_root
    httpd.shutdown()
    httpd.server_close()
    projects.stop()


def post(port, action, body, cookie=SECRET, origin=True):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = f"talos_k={cookie}"
    if origin:
        headers["Origin"] = f"http://127.0.0.1:{port}" if origin is True else origin
    conn.request("POST", f"/api/control/{action}", json.dumps(body), headers)
    r = conn.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def events(root):
    return [json.loads(l) for l in (root / "company" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def test_only_the_secret_and_the_same_origin_may_write(control_server):
    port, root = control_server
    before = len(events(root))
    assert post(port, "say", {"text": "hi"}, cookie=None)[0] == 403
    assert post(port, "say", {"text": "hi"}, cookie="wrong")[0] == 403
    assert post(port, "say", {"text": "hi"}, origin=False)[0] == 403
    assert post(port, "say", {"text": "hi"}, origin="http://evil.example")[0] == 403
    assert len(events(root)) == before
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request("POST", "/api/snapshot", "{}", {"Content-Type": "application/json"})
    assert conn.getresponse().status == 405


def test_the_link_sets_the_cookie_and_leaves_the_address_bar(control_server):
    port, _ = control_server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    conn.request("GET", f"/?k={SECRET}&view=canopy")
    r = conn.getresponse()
    r.read()
    assert r.status == 303 and r.getheader("Location") == "/?view=canopy"
    assert f"talos_k={SECRET}" in r.getheader("Set-Cookie") and "HttpOnly" in r.getheader("Set-Cookie")
    conn.request("GET", "/?k=wrong")
    r = conn.getresponse()
    r.read()
    assert r.status == 303 and r.getheader("Set-Cookie") is None


def test_a_message_is_data_even_when_it_looks_like_a_flag_or_a_command(control_server):
    port, root = control_server
    for text in ("--force; rm -rf /", '"; taskkill /IM python.exe', "$(whoami) `id` & del *"):
        status, body = post(port, "say", {"text": text})
        assert status == 200, body
    lines = (root / "company" / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["text"] == "--force; rm -rf /"
    assert json.loads(lines[2])["text"] == "$(whoami) `id` & del *"


def test_presses_record_what_the_cli_would(control_server):
    port, root = control_server
    assert post(port, "preset", {"name": "heavy"})[0] == 200
    assert events(root)[-1]["event"] == "preset.changed" and events(root)[-1]["preset"] == "heavy"
    assert post(port, "approve", {"gate": "release", "ref": "ITEM-0001"})[0] == 200
    last = events(root)[-1]
    assert (last["event"], last["actor"], last["ref"], last["recorded_by"]) == ("release.approved", "ceo", "ITEM-0001", "control-room")
    assert post(port, "reject", {"gate": "plan", "reason": "--too big"})[0] == 200
    assert (events(root)[-1]["event"], events(root)[-1]["summary"]) == ("plan.rejected", "--too big")


@pytest.mark.parametrize("action,body", [
    ("nope", {}), ("approve", {"gate": "merge"}), ("approve", {"gate": "release", "ref": "../../x"}), ("approve", {"gate": "plan", "ref": "x"}),
    ("answer", {"qid": "Q-1; rm", "text": "x"}), ("preset", {"name": "mega"}), ("say", {"text": ""}), ("say", {"text": "x" * 5000}),
])
def test_bad_requests_never_reach_the_cli(action, body):
    with pytest.raises(C.Invalid):
        C.command(action, body)
