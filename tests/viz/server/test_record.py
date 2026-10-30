from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from itertools import groupby

import pytest

from viz import record as R
from viz import snapshot as S

from .conftest import FIXTURE, PINNED, REPO, cli

NOW = datetime(2026, 10, 29, 6, 0, 0, tzinfo=timezone.utc)


def build_for(record, project_root=None, version=1):
    return S.build(project_root or record.parent, record, now=NOW, version=version, checked_at=NOW)


@pytest.fixture(scope="module")
def fixture_snapshot():
    return build_for(FIXTURE, FIXTURE.parent)


def test_fixture_counts(fixture_snapshot):
    s = fixture_snapshot
    assert s["counts"]["events"] == 68
    assert len(s["event_types"]) == 24 and s["counts"]["event_types"] == 24
    items = s["counts"]["items"]
    assert items["proposed"] == 5 and items["verified"] == 2 and items["total"] == 7
    assert all(v == 0 for k, v in items.items() if k not in ("proposed", "verified", "total"))
    c = s["cycle"]
    assert (c["number"], c["open"], c["elapsed_minutes"]) == (1, False, 37)
    assert [w["key"] for w in s["waiting"]] == ["gate:release:ITEM-0001", "gate:release:ITEM-0002"]
    assert s["project"]["name"] == "focus"
    assert s["activity"]["status"] == "unavailable"
    assert s["counts"]["ceo_questions_open"] == 0
    assert s["errors"] == []


def test_runs(fixture_snapshot):
    ev = fixture_snapshot["events"]
    groups = [(c, p, len(list(g))) for (c, p), g in groupby(ev, key=lambda e: (e["cycle"], e["phase"]))]
    assert groups == [(1, "cycle-close", 4), (1, "retro", 7), (1, "cycle-close", 8), (1, "cycle-verify", 10),
                      (1, "cycle-build", 9), (0, "review", 3), (0, "plan", 17), (0, "review", 3), (0, "kickoff", 7)]
    assert ev[0]["run"] == "EVT-20261028180433-d87e"


def _strip(d: dict, dotted: list[str]) -> dict:
    d = copy.deepcopy(d)
    for key in dotted:
        node = d
        parts = key.split(".")
        for p in parts[:-1]:
            node = node[p]
        node.pop(parts[-1], None)
    return d


VOLATILE = ["generated_at", "checked_at", "version", "project.root", "project.record", "project.folder",
            "activity.checked_at", "activity.reason", "activity.transcript_dirs", "spend.transcripts.reason",
            "report.modified_at"]


def test_pinned_snapshot(fixture_snapshot):
    pinned = json.loads(PINNED.read_text(encoding="utf-8"))
    built = fixture_snapshot
    drop = list(VOLATILE)
    assert set(built["spend"]) == set(pinned["spend"])
    assert set(built["spend"]["events"]) == set(pinned["spend"]["events"])
    if not S.have_activity():
        # ITEM-0002 owns the whole spend block and last_run; the stub only has to match the key sets (ADR-0005).
        drop += ["activity.last_run", "spend"]
    assert _strip(built, drop) == _strip(pinned, drop)
    assert built["spend"]["cycle"] == 1


def test_budget_string_has_section_sign(fixture_snapshot):
    state = json.loads((FIXTURE / "state.json").read_text(encoding="utf-8"))
    assert fixture_snapshot["cycle"]["budget"] == state["budget"]
    assert "§" in state["budget"]


def test_questions_and_gates(record_root):
    company = record_root / "company"
    r = cli(record_root, "ask", "--for", "ceo", "--context", "c", "--options", "a | b", "Q text?")
    assert r.returncode == 0, r.stderr
    r = cli(record_root, "ask", "--for", "architect", "T?")
    assert r.returncode == 0, r.stderr
    s = build_for(company, record_root)
    assert s["counts"]["ceo_questions_open"] == 1 and s["counts"]["other_questions_open"] == 1
    q = [w for w in s["waiting"] if w["kind"] == "question"]
    assert len(q) == 1
    q = q[0]
    assert q["id"] == "Q-0002" and q["key"] == "Q-0002"
    assert q["title"] == "Q text?" and q["context"] == "c" and q["options"] == "a | b"
    assert q["command"] == 'tools/talos/run review "Q-0002: <your answer>"'
    assert q["asked_by"] == "test-engineer" and q["asked_at"]

    assert cli(record_root, "answer", "Q-0002", "yes").returncode == 0
    s = build_for(company, record_root)
    assert not [w for w in s["waiting"] if w["kind"] == "question"]
    assert s["counts"]["ceo_questions_open"] == 0 and s["counts"]["other_questions_open"] == 1

    assert cli(record_root, "log", "charter.proposed", "--summary", "s").returncode == 0
    s = build_for(company, record_root)
    assert [w["key"] for w in s["waiting"]] == ["gate:charter", "gate:release:ITEM-0001", "gate:release:ITEM-0002"]
    g = s["waiting"][0]
    assert g["title"] == "Charter gate: s" and g["ref"] is None
    assert g["command"] == 'tools/talos/run review "<your words approving the charter>"'
    assert g["proposed_event"].startswith("EVT-")


def test_fail_soft(record_root):
    company = record_root / "company"
    import shutil
    shutil.rmtree(company / "reports")
    with open(company / "ledger.jsonl", "a", encoding="utf-8", newline="\n") as f:
        f.write("{not json\n")
    (company / "state.json").write_text("{", encoding="utf-8")
    s = build_for(company, record_root)
    assert s["report"] is None
    blocks = {e["block"] for e in s["errors"]}
    assert {"report", "ledger-line", "state"} <= blocks
    assert s["counts"]["events"] == 68
    assert any(e["block"] == "ledger-line" and e["reason"].startswith("line 69:") for e in s["errors"])


def test_missing_everything_does_not_raise(tmp_path):
    (tmp_path / "company").mkdir()
    s = build_for(tmp_path / "company", tmp_path)
    assert s["counts"]["events"] == 0
    assert {"ledger", "state", "charter", "items", "questions", "report"} <= {e["block"] for e in s["errors"]}


def test_display_name():
    assert R.display_name("---\nstatus: x\n---\n\n# Charter: Talos visualizer\n", "viz") == "Talos visualizer"
    assert R.display_name("# Charter\n", "folder") == "folder"
    assert R.display_name("# Charter:   \n", "folder") == "folder"
    assert R.display_name("no heading", "folder") == "folder"


def test_parse_frontmatter():
    fm, body = R.parse_frontmatter('---\nid: X-1\ntitle: "a: b"\ntags: [a, "b"]\n---\n\nbody\n')
    assert fm == {"id": "X-1", "title": "a: b", "tags": ["a", "b"]}
    assert body == "body\n"
    assert R.parse_frontmatter("plain") == ({}, "plain")


def test_items_empty_strings_become_none(fixture_snapshot):
    it = {i["id"]: i for i in fixture_snapshot["items"]}
    assert it["ITEM-0003"]["spec"] is None and it["ITEM-0003"]["branch"] is None and it["ITEM-0003"]["commit"] is None
    assert it["ITEM-0001"]["commit"] == "4464661" and it["ITEM-0001"]["cycle"] == 0
    assert [i["id"] for i in fixture_snapshot["items"]] == sorted(it)


def test_events_newest_first_and_extra(fixture_snapshot):
    ev = fixture_snapshot["events"]
    assert ev[-1]["event"] == "project.kickoff"
    assert ev[0]["extra"]["model"] == "sonnet"
    assert not set(ev[0]["extra"]) & set(R.STANDARD_KEYS)
