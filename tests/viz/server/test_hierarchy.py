"""viz/hierarchy.py: tasks and costs from transcripts, outcomes and waits from the ledger, ledger-only fallback."""
from __future__ import annotations

import json

from viz import hierarchy as H


def _ledger(*rows):
    return [{"id": f"E{i}", "actor": a, "event": ev, "ts": ts, "ref": ref, "summary": s} for i, (ts, a, ev, ref, s) in enumerate(rows)]


LEDGER = _ledger(
    ("2026-10-28T10:00:00Z", "chief-of-staff", "note", "cycle-1", "CEO: fix ITEM-0001 now"),
    ("2026-10-28T11:00:00Z", "code-reviewer", "review.changes_requested", "ITEM-0001", "nope"),
    ("2026-10-28T11:30:00Z", "test-engineer", "item.verified", "ITEM-0001", "ok"),
    ("2026-10-28T13:30:00Z", "ceo", "release.approved", "ITEM-0001", "ship"),
    ("2026-10-28T13:31:00Z", "chief-of-staff", "release.shipped", "ITEM-0001", "merged"),
)


def _agent(folder, name, role, desc, ts, tokens):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.meta.json").write_text(json.dumps({"agentType": role, "description": desc}), encoding="utf-8")
    line = {"timestamp": ts, "message": {"id": name, "model": "claude-sonnet-5", "usage": {"input_tokens": tokens, "output_tokens": 0}}}
    (folder / f"{name}.jsonl").write_text(json.dumps(line) + "\n", encoding="utf-8")


def test_outcomes_tokens_and_waits(tmp_path):
    tr = tmp_path / "tr"
    tr.mkdir()
    main = {"timestamp": "2026-10-28T10:00:00Z", "message": {"id": "m", "model": "claude-opus-5", "usage": {"input_tokens": 100}}}
    (tr / "s1.jsonl").write_text(json.dumps(main) + "\n", encoding="utf-8")
    subs = tr / "s1" / "subagents"
    _agent(subs, "agent-a", "engineer", "Build ITEM-0001", "2026-10-28T10:30:00Z", 500)
    _agent(subs, "agent-b", "engineer", "Fix ITEM-0001", "2026-10-28T11:10:00Z", 200)
    _agent(subs, "agent-c", "librarian", "Rebuild index", "2026-10-28T12:00:00Z", 50)
    d = H.build(tmp_path, tmp_path, LEDGER, transcripts=str(tr))
    by = {t["id"]: t for t in d["tasks"]}
    assert d["source"] == "transcripts"
    assert (by["agent-a"]["outcome"], by["agent-b"]["outcome"], by["agent-c"]["outcome"]) == ("sent_back", "verified", "support")
    assert d["totals"]["tokens"] == 850 and d["totals"]["orchestration"] == 100 and d["totals"]["unattributed"] == 150
    route = d["items"]["ITEM-0001"]
    assert route["state"] == "shipped" and route["sent_back"] == 1 and route["tokens"] == 700
    waits = [(s["actor"], s["wait"], s["on_you"]) for s in route["steps"] if s["wait"]]
    assert ("ceo", 7200, True) in waits and all(not on for a, _, on in waits if a != "ceo")
    assert route["steps"][0]["actor"] == "ceo"  # the CEO's note counts as the CEO speaking


def test_ledger_only_without_transcripts(tmp_path):
    d = H.build(tmp_path, tmp_path, LEDGER, transcripts=str(tmp_path / "none"))
    assert d["source"] == "ledger" and d["reason"]
    assert {t["role"] for t in d["tasks"]} == {"code-reviewer", "test-engineer", "chief-of-staff"}
    assert all(t["tokens"] == 0 for t in d["tasks"])
