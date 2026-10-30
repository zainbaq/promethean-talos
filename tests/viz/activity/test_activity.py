import pytest
import builtins
import json
import os
import pathlib
import time
from datetime import datetime, timezone
from pathlib import Path


def _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, case, age, worktree=False):
    proj = record_copy(tmp_path)
    cfg = transcripts(tmp_path, case, proj, age, worktree=worktree)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    return proj, read_ledger(proj), cfg


def _agent(result, role):
    return [a for a in result["agents"] if a["role"] == role]


def test_active(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, cfg = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 30)
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "active" and r["reason"] is None
    assert r["window_seconds"] == 120 and r["recent_seconds"] == 300
    (eng,) = _agent(r, "engineer")
    assert eng["state"] == "active" and eng["item"] == "ITEM-0003" and eng["worktree"] is False
    assert abs(eng["seconds_ago"] - 30) <= 2
    sub = next(cfg.rglob("agent-a7f3.jsonl"))
    mtime = datetime.fromtimestamp(sub.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert eng["last_write_at"] == mtime
    assert eng["transcript"] == "agent-a7f3.jsonl" and eng["session"] == "5a1f3c2e-main"
    (main,) = _agent(r, "main session")
    assert main["state"] == "active" and main["item"] is None
    assert r["phase"]["status"] == "running" and r["phase"]["name"] == "cycle-build"
    assert r["phase"]["session"] == "5a1f3c2e-main"
    assert r["phase"]["since"] == "2026-10-28T17:25:00Z"
    assert r["last_run"]["event_id"] == "EVT-20261028180433-d87e"
    assert len(r["transcript_dirs"]) == 1


def test_recent_then_idle(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, _ = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 150)
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "idle"
    (eng,) = _agent(r, "engineer")
    assert eng["state"] == "recent"

    t2 = tmp_path / "second"
    t2.mkdir()
    cfg = transcripts(t2, "engineer-active", proj, 400)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "idle" and r["agents"] == []
    assert r["phase"]["status"] == "idle"
    lr = r["last_run"]
    assert lr["phase"] == "cycle-close" and lr["model"] == "sonnet"
    assert lr["ts"] == "2026-10-28T18:04:33Z" and lr["event_id"] == "EVT-20261028180433-d87e"
    assert abs(lr["cost_usd"] - 1.08) < 0.005 and lr["turns"] == 7


def test_worktree_slug(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, _ = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts,
                             "engineer-active-worktree", 30, worktree=True)
    r = activity.derive(proj, proj / "company", ledger, 1)
    (eng,) = _agent(r, "engineer")
    assert eng["worktree"] is True and eng["item"] == "ITEM-0003"
    assert len(r["transcript_dirs"]) == 1
    assert r["transcript_dirs"][0].endswith("--claude-worktrees-abc123")


def test_unavailable(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj = record_copy(tmp_path)
    ledger = read_ledger(proj)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing"))
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "unavailable" and "no Claude Code transcripts" in r["reason"]
    assert r["agents"] == [] and r["phase"]["status"] == "unknown" and r["transcript_dirs"] == []

    t2 = tmp_path / "second"
    t2.mkdir()
    cfg = transcripts(t2, "malformed-meta", proj, 30)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "unavailable" and r["reason"].endswith("malformed .meta.json")
    assert r["agents"] == [] and r["phase"]["status"] == "unknown" and r["transcript_dirs"] == []


def test_empty_jsonl_does_not_break(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, cfg = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 30)
    subs = next(cfg.rglob("agent-a7f3.jsonl")).parent
    (subs / "agent-b.jsonl").write_bytes(b"")
    (subs / "agent-b.meta.json").write_text('{"agentType": "engineer"}', encoding="utf-8")
    when = time.time() - 30
    for p in subs.glob("agent-b.*"):
        os.utime(p, (when, when))
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["status"] == "active"
    empty = [a for a in r["agents"] if a["transcript"] == "agent-b.jsonl"]
    assert len(empty) == 1 and empty[0]["item"] is None


def test_item_scan_is_limited_to_last_64kb(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, cfg = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 30)
    sub = next(cfg.rglob("agent-a7f3.jsonl"))
    lines = [
        {"type": "user", "timestamp": "2026-10-28T17:26:10Z",
         "message": {"role": "user", "content": "Implement ITEM-0003 exactly."}},
        {"type": "assistant", "timestamp": "2026-10-28T17:26:20Z",
         "message": {"role": "assistant", "content": [{"type": "text", "text": "see ITEM-0009"}]}},
    ]
    filler = {"type": "assistant", "timestamp": "2026-10-28T17:27:00Z",
              "message": {"role": "assistant", "content": [{"type": "text", "text": "x" * 200}]}}
    lines += [filler] * 400  # about 90 KB, no ITEM- text
    sub.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    assert sub.stat().st_size > 64 * 1024
    when = time.time() - 30
    os.utime(sub, (when, when))
    r = activity.derive(proj, proj / "company", ledger, 1)
    (eng,) = _agent(r, "engineer")
    assert eng["item"] == "ITEM-0003"


def test_reads_only_allowed_paths(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj, ledger, cfg = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 30)
    opened = []
    real_open, real_path_open = builtins.open, pathlib.Path.open

    def spy_open(file, mode="r", *a, **kw):
        opened.append((str(file), mode))
        return real_open(file, mode, *a, **kw)

    def spy_path_open(self, mode="r", *a, **kw):
        opened.append((str(self), mode))
        return real_path_open(self, mode, *a, **kw)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(pathlib.Path, "open", spy_path_open)
    activity.derive(proj, proj / "company", ledger, 1)
    activity.spend(ledger, 1, proj)
    monkeypatch.undo()
    assert opened, "expected the deriver to read transcripts"
    repo = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"
    allowed = [Path(proj).resolve(), Path(cfg).resolve(), (repo / "usage.py").resolve()]
    for name, mode in opened:
        p = Path(name).resolve()
        assert any(p == a or a in p.parents for a in allowed), name
        assert not any(c in mode for c in "wa+"), (name, mode)


### ---- ITEM-0016 (SPEC-0010, ADR-0009, ADR-0010): finished runs are not running; labels only from execution roles ----
def _case_ledger(case):
    """tests/fixtures/transcripts/<case>.ledger.jsonl when the case ships one, else the sample record's ledger."""
    path = Path(__file__).resolve().parents[1] / "fixtures" / "transcripts" / f"{case}.ledger.jsonl"
    if not path.is_file():
        path = Path(__file__).resolve().parents[1] / "fixtures" / "sample-company" / "ledger.jsonl"
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_closed_15_43(tmp_path, monkeypatch, activity, record_copy, transcripts):
    proj = record_copy(tmp_path)
    cfg = transcripts(tmp_path, "closed-15-43", proj, 50)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    ledger = _case_ledger("closed-15-43")
    assert ledger[-2]["event"] == "cycle.ended" and ledger[-2]["ref"] == "cycle-002"
    assert ledger[-1]["event"] == "run.completed" and ledger[-1]["phase"] == "cycle-close"
    assert ledger[-1]["session"] == "16021ae8-7b90-4c6d-9b64-c9e949443e03"
    r = activity.derive(proj, proj / "company", ledger, 2)
    assert r["phase"]["status"] != "running"
    assert r["phase"] == {"status": "idle", "name": None, "session": None, "since": None}
    assert r["last_run"]["phase"] == "cycle-close" and r["last_run"]["ts"] == "2026-10-29T15:42:55Z"
    assert r["status"] == "active"
    assert {a["role"] for a in r["agents"]} == {"main session", "librarian", "head-of-product", "chief-of-staff"}
    assert all(a["item"] is None for a in r["agents"])


def test_launcher_format(tmp_path, monkeypatch, activity, record_copy, transcripts):
    proj = record_copy(tmp_path)
    cfg = transcripts(tmp_path, "launcher-verify", proj, 30)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    ledger = _case_ledger("launcher-verify")  # the sample record: no run.completed carries 9d4c1b2a-verify
    assert all(e.get("session") != "9d4c1b2a-verify" for e in ledger)
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["phase"]["status"] == "running" and r["phase"]["name"] == "cycle-verify"
    assert r["phase"]["session"] == "9d4c1b2a-verify" and r["phase"]["since"] == "2026-10-29T15:24:05Z"
    (main,) = _agent(r, "main session")
    assert main["item"] is None
    t2 = tmp_path / "second"
    t2.mkdir()
    cfg = transcripts(t2, "engineer-active", proj, 30)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    r = activity.derive(proj, proj / "company", _case_ledger("engineer-active"), 1)
    assert r["phase"]["status"] == "running" and r["phase"]["name"] == "cycle-build"
    (eng,) = _agent(r, "engineer")
    assert eng["item"] == "ITEM-0003"


def test_phase_name_table(activity):
    launcher = "<command-message>talos-{c}</command-message>\n<command-name>/talos-{c}</command-name>\n<command-args>{a}</command-args>"
    assert activity.phase_name("/talos-cycle build Cycle 3 scope.") == "cycle-build"
    assert activity.phase_name(launcher.format(c="cycle", a="close Cycle 2. ITEM-0003 carries over")) == "cycle-close"
    assert activity.phase_name(launcher.format(c="cycle", a="verify Cycle 2.")) == "cycle-verify"
    assert activity.phase_name(launcher.format(c="review", a="CEO, exact words: 'Run cycle 3'.")) == "review"
    assert activity.phase_name("<command-message>talos-kickoff</command-message>\n<command-name>/talos-kickoff</command-name>") == "kickoff"
    assert activity.phase_name("/talos-cycle") is None
    assert activity.phase_name(launcher.format(c="cycle", a="")) is None
    assert activity.phase_name("Implement ITEM-0003 exactly.") is None
    assert activity.phase_name("") is None and activity.phase_name(None) is None


def test_live_record_never_claims_a_finished_run(activity):
    """Against this checkout's company/ and the machine's real transcripts (read-only; vacuous when there are none)."""
    root = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"
    if not (root / "company" / "ledger.jsonl").is_file():
        pytest.skip("no company/ record in this checkout")
    with open(root / "company" / "ledger.jsonl", encoding="utf-8") as f:
        ledger = [json.loads(line) for line in f if line.strip()]
    r = activity.derive(root, root / "company", ledger, 0)
    finished = {e.get("session") for e in ledger if e.get("event") == "run.completed"}
    if r["phase"]["status"] == "running":
        assert r["phase"]["name"] is not None
        assert r["phase"]["session"] not in finished


def test_run_is_live_while_only_its_subagent_writes(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    """A launcher session blocked on a long subagent call writes nothing itself; the run is still in flight."""
    proj, ledger, cfg = _setup(tmp_path, monkeypatch, record_copy, read_ledger, transcripts, "engineer-active", 30)
    main = next(cfg.rglob("5a1f3c2e-main.jsonl"))
    when = time.time() - 200
    os.utime(main, (when, when))
    r = activity.derive(proj, proj / "company", ledger, 1)
    assert r["phase"]["status"] == "running" and r["phase"]["name"] == "cycle-build"
    assert r["phase"]["session"] == "5a1f3c2e-main"
    (m,) = _agent(r, "main session")
    assert m["state"] == "recent"
