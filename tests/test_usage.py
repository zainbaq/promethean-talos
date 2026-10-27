"""Fixture tests for template/tools/talos/usage.py and the `talos usage` command.

Run from the repo root:  .venv/Scripts/python -m unittest discover -s tests   (Windows)
                         .venv/bin/python -m unittest discover -s tests       (elsewhere)
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TALOS = HERE.parent / "template" / "tools" / "talos"
sys.path.insert(0, str(TALOS))
import usage as U  # noqa: E402


def line(mid, model, ts, fresh=1, write=10, read=100, out=5, kind="assistant"):
    return json.dumps({"type": kind, "timestamp": ts, "message": {
        "id": mid, "model": model, "role": "assistant",
        "usage": {"input_tokens": fresh, "cache_creation_input_tokens": write,
                  "cache_read_input_tokens": read, "output_tokens": out}}})


def build(tdir: Path) -> None:
    """One main session (Fable) with two subagents: an engineer on ITEM-0001 and a reviewer naming two items."""
    tdir.mkdir(parents=True)
    main = tdir / "s1.jsonl"
    main.write_text("\n".join([
        json.dumps({"type": "user", "timestamp": "2026-10-25T09:00:00.000Z", "message": {"role": "user", "content": "kickoff"}}),
        line("m1", "claude-fable-5-1", "2026-10-25T09:00:05.000Z"),
        line("m1", "claude-fable-5-1", "2026-10-25T09:00:05.000Z"),  # streamed duplicate: counted once
        line("m2", "claude-fable-5-1", "2026-10-25T11:00:00.000Z", read=1000),
        "not json",
    ]) + "\n", encoding="utf-8")
    sub = tdir / "s1" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-a.jsonl").write_text("\n".join([
        json.dumps({"type": "user", "timestamp": "2026-10-25T10:30:00.000Z", "message": {"role": "user", "content": "Implement ITEM-0001 per SPEC-0002."}}),
        line("e1", "claude-sonnet-5-5", "2026-10-25T10:30:10.000Z", read=50),
        line("e2", "claude-sonnet-5-5", "2026-10-25T10:31:10.000Z", read=50),
    ]) + "\n", encoding="utf-8")
    (sub / "agent-a.meta.json").write_text(json.dumps({"agentType": "engineer"}), encoding="utf-8")
    (sub / "agent-b.jsonl").write_text("\n".join([
        json.dumps({"type": "user", "timestamp": "2026-10-25T10:40:00.000Z", "message": {"role": "user", "content": [{"type": "text", "text": "Review ITEM-0001 and ITEM-0002."}]}}),
        line("r1", "claude-opus-5-5", "2026-10-25T10:40:10.000Z", read=20),
    ]) + "\n", encoding="utf-8")
    (sub / "agent-b.meta.json").write_text(json.dumps({"agentType": "code-reviewer"}), encoding="utf-8")


LEDGER = [
    {"event": "project.kickoff", "ts": "2026-10-25T08:59:00Z", "cycle": 0},
    {"event": "cycle.started", "ts": "2026-10-25T10:00:00Z", "cycle": 1},
    {"event": "item.verified", "ts": "2026-10-25T10:50:00Z", "cycle": 1, "ref": "ITEM-0001", "evidence": ["x"]},
    {"event": "cycle.started", "ts": "2026-10-25T10:59:00Z", "cycle": 2},
]


class UsageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name) / "transcripts"
        build(self.t)

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_dedupes_and_names_roles_and_items(self):
        recs, why = U.collect(".", self.t)
        self.assertIsNone(why)
        self.assertEqual(len(recs), 5)  # m1 once, m2, e1, e2, r1
        roles = {(r["role"], r["item"]) for r in recs}
        self.assertIn(("main session", "-"), roles)
        self.assertIn(("engineer", "ITEM-0001"), roles)
        self.assertIn(("code-reviewer", "several"), roles)

    def test_cycles_follow_ledger_starts(self):
        recs, _ = U.collect(".", self.t)
        U.assign_cycles(recs, LEDGER)
        by = {r["ts"]: r["cycle"] for r in recs}
        self.assertEqual(by["2026-10-25T09:00:05"], 0)
        self.assertEqual(by["2026-10-25T10:30:10"], 1)
        self.assertEqual(by["2026-10-25T11:00:00"], 2)

    def test_summarize_totals(self):
        recs, _ = U.collect(".", self.t)
        rows = U.summarize(recs, lambda r: U.family(r["model"]))
        top = rows[0]
        self.assertEqual(top["key"], "fable")
        self.assertEqual(top["read"], 1100)
        self.assertEqual(top["total"], (1 + 10 + 100 + 5) + (1 + 10 + 1000 + 5))

    def test_missing_transcripts_fail_soft(self):
        recs, why = U.collect(".", Path(self.tmp.name) / "nope")
        self.assertEqual(recs, [])
        self.assertIn("no Claude Code transcripts for this project", why)

    def test_cli_usage_and_report_spend(self):
        proj = Path(self.tmp.name) / "proj"
        (proj / "company" / "reports").mkdir(parents=True)
        (proj / "company" / "ledger.jsonl").write_text("\n".join(json.dumps(e) for e in LEDGER) + "\n", encoding="utf-8")
        (proj / "company" / "state.json").write_text(json.dumps({"cycle": 1, "cycle_open": False, "counters": {}}), encoding="utf-8")
        env = dict(os.environ, TALOS_TRANSCRIPTS=str(self.t), TALOS_ROOT=str(proj))
        cli = [sys.executable, str(TALOS / "talos.py")]
        out = subprocess.run(cli + ["usage", "--cycle", "1"], cwd=proj, env=env, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("| engineer | sonnet | 2 |", out.stdout)
        self.assertIn("Per verified item:", out.stdout)
        js = json.loads(subprocess.run(cli + ["usage", "--by", "cycle", "--json"], cwd=proj, env=env, capture_output=True, text=True).stdout)
        self.assertEqual(sorted(r["key"][0] for r in js["rows"]), ["0", "1", "2"])
        rep = subprocess.run(cli + ["report", "--cycle", "1"], cwd=proj, env=env, capture_output=True, text=True)
        self.assertEqual(rep.returncode, 0, rep.stderr)
        text = (proj / "company" / "reports" / "cycle-001.md").read_text(encoding="utf-8")
        self.assertIn("## Spend (measured from transcripts)", text)
        self.assertIn("Per verified item:", text)


if __name__ == "__main__":
    unittest.main()
