"""Tests for the v0.2 phase 1 CLI and init.py additions: brief status, events, context packs,
spec lint, item risk, the run launcher's command line, and team stamping.

Run from the repo root: .venv/Scripts/python -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TALOS = REPO / "template" / "tools" / "talos"

GOOD_SPEC = """---
id: SPEC-0001
title: Add thing
item: ITEM-0001
---

# Add thing

## Goal
Add `thing()`.

## Non-goals
None.

## Files and modules in scope
- New: `app/thing.py`
- Edited: `README.md`

## Acceptance criteria
_Executed by the architect on 2026-10-26._
- [ ] `python -m pytest -q` exits 0 and prints `3 passed`.
- [ ] Manual check on a phone (UNEXECUTED: needs the CEO).

## Constraints from the record
- ADRs: ADR-0001
"""

BAD_SPEC = """---
id: SPEC-0002
title: Vague
---

# Vague

## Goal
Do it well.

## Files and modules in scope
- `src/missing.py`

## Acceptance criteria
- [ ] It works properly.
- [ ] `make test`

Depends on ADR-0099.
"""


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        (self.root / "README.md").write_text("x\n", encoding="utf-8")
        self.env = dict(os.environ, TALOS_ROOT=str(self.root), TALOS_ACTOR="test", TALOS_TIER="mechanical",
                        TALOS_TRANSCRIPTS=str(Path(self.tmp.name) / "none"))
        self.cli("init", "--teams", "core,design")

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), *args], cwd=self.root, env=self.env,
                           capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p


class Phase1Cli(CliBase):
    def test_risk_brief_status_and_events(self):
        self.cli("item", "new", "--title", "Docs only", "--risk", "low")
        self.cli("item", "new", "--title", "Login")
        self.cli("item", "set", "ITEM-0002", "--risk", "high", "--status", "ready")
        out = self.cli("status", "--brief").stdout
        self.assertIn("teams core,design", out)
        self.assertIn("proposed ITEM-0001(low)", out)
        self.assertIn("ready ITEM-0002(high)", out)
        self.assertLessEqual(len(out.splitlines()), 6)
        ev = self.cli("events", "--type", "item.").stdout.splitlines()
        self.assertEqual(len(ev), 2)  # item.created x2; the set logs item.* only for transitions it maps
        self.assertTrue(all(" item." in l for l in ev))

    def test_multiline_acceptance_becomes_one_line_per_criterion(self):
        self.cli("item", "new", "--title", "T", "--acceptance", "- [ ] first\n- second\n\nthird")
        body = (self.root / "company" / "backlog" / "ITEM-0001.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] first\n- [ ] second\n- [ ] third\n", body)

    def test_context_pack_finds_spec_by_path_and_rulings(self):
        self.cli("item", "new", "--title", "Add thing")
        self.cli("decision", "add", "--title", "Toolchain", "--status", "accepted", "--context", "long context",
                 "--decision", "Use uv.", "--consequences", "c", "--alternatives", "conda")
        (self.root / "company" / "specs" / "SPEC-0001-add-thing.md").write_text(GOOD_SPEC, encoding="utf-8")
        self.cli("item", "set", "ITEM-0001", "--spec", "company/specs/SPEC-0001-add-thing.md")
        self.cli("lesson", "add", "--title", "Engineers: venv first", "--body", "Use the venv.", "--applies-to", "engineering",
                 "--evidence", "EVT-1", "--confidence", "high")
        self.cli("lesson", "add", "--title", "Sales only", "--body", "Irrelevant to engineers.", "--applies-to", "gtm",
                 "--evidence", "EVT-2", "--confidence", "high")
        out = self.cli("context", "ITEM-0001", "--role", "engineer").stdout
        self.assertIn("1 decisions, 1 lessons", out)
        pack = (self.root / "company" / ".context" / "ITEM-0001-engineer.md").read_text(encoding="utf-8")
        self.assertIn("## Spec (company/specs/SPEC-0001-add-thing.md)", pack)
        self.assertIn("Use uv.", pack)
        self.assertNotIn("long context", pack)  # rulings only, not the ADR's context
        self.assertIn("Use the venv.", pack)
        self.assertNotIn("Irrelevant to engineers.", pack)
        self.assertIn("STATUS: completed | blocked | needs_question", pack)
        top = [l for l in pack.splitlines() if l.startswith("## ")]
        self.assertEqual(top[:2], ["## Item", "## Spec (company/specs/SPEC-0001-add-thing.md)"])

    def test_spec_lint(self):
        self.cli("decision", "add", "--title", "Toolchain", "--status", "accepted", "--decision", "uv")
        specs = self.root / "company" / "specs"
        (specs / "SPEC-0001-good.md").write_text(GOOD_SPEC, encoding="utf-8")
        (specs / "SPEC-0002-bad.md").write_text(BAD_SPEC, encoding="utf-8")
        self.assertEqual(self.cli("spec", "lint", "SPEC-0001").returncode, 0)
        p = self.cli("spec", "lint", ok=False)
        self.assertEqual(p.returncode, 1)
        out = p.stdout
        for needle in ("missing section '## Non-goals'", "acceptance line 1 has no command", "acceptance line 2 names no expected result",
                       "does not say the architect executed", "references ADR-0099", "not marked new: src/missing.py"):
            self.assertIn(needle, out)
        long = GOOD_SPEC.replace("## Non-goals\nNone.", "## Non-goals\n" + "\n".join(f"- line {i}" for i in range(130)))
        (specs / "SPEC-0001-good.md").write_text(long, encoding="utf-8")
        self.assertIn("the budget is 120", self.cli("spec", "lint", "SPEC-0001", ok=False).stdout)


class DesignGate(CliBase):
    def test_gate_follows_staffing_proposal_approval_and_waiver(self):
        # setUp staffs core,design: closed until the CEO approves a proposed design
        self.assertEqual(self.cli("gate", "design", ok=False).returncode, 1)
        self.cli("log", "design.proposed", "--summary", "direction + 2 screens")
        self.assertEqual(self.cli("gate", "design", ok=False).returncode, 1)
        self.cli("approve", "design", "--quote", "Love it")
        self.assertIn("design approved", self.cli("gate", "design").stdout)
        self.cli("log", "design.proposed", "--summary", "revised screens")
        self.assertEqual(self.cli("gate", "design", ok=False).returncode, 1)  # a new proposal needs a new approval
        self.cli("approve", "design-waiver", "--quote", "Skip the design gate for this one")
        self.assertIn("waived", self.cli("gate", "design").stdout)

    def test_no_design_team_means_no_gate(self):
        self.cli("init", "--teams", "core")
        self.assertIn("no design team staffed", self.cli("gate", "design").stdout)


class Size(CliBase):
    def test_size_drives_brief_lint_and_plan_turns(self):
        self.assertIn("medium", self.cli("size").stdout)
        self.cli("size", "small")
        self.assertIn("size small", self.cli("status", "--brief").stdout)
        specs = self.root / "company" / "specs"
        mid = GOOD_SPEC.replace("## Non-goals\nNone.", "## Non-goals\n" + "\n".join(f"- line {i}" for i in range(70)))
        self.cli("decision", "add", "--title", "Toolchain", "--status", "accepted", "--decision", "uv")
        (specs / "SPEC-0001-mid.md").write_text(mid, encoding="utf-8")
        self.assertIn("the budget is 60", self.cli("spec", "lint", ok=False).stdout)
        self.cli("size", "medium")
        self.assertEqual(self.cli("spec", "lint").returncode, 0)
        self.cli("size", "small")
        env = dict(self.env, TALOS_CLAUDE=sys.executable)
        out = subprocess.run([sys.executable, str(TALOS / "run.py"), "plan", "--dry-run"], cwd=self.root, env=env, capture_output=True, text=True).stdout
        self.assertIn("--max-turns 40", out)
        self.assertIn("size: small", (self.root / "company" / "charter.md").read_text(encoding="utf-8"))


class Launcher(CliBase):
    def test_dry_run_uses_lean_flags_and_phase_models(self):
        env = dict(self.env, TALOS_CLAUDE=sys.executable)  # any existing file stands in for the CLI
        def dry(*a):
            p = subprocess.run([sys.executable, str(TALOS / "run.py"), *a, "--dry-run"], cwd=self.root, env=env,
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout
        out = dry("cycle-verify")
        for flag in ("--strict-mcp-config", "--setting-sources project,local", "--no-chrome", "--exclude-dynamic-system-prompt-sections",
                     "--tools Bash,Read,Glob,Grep,Write,Edit,Agent,Skill,TodoWrite", "--model sonnet", '"/talos-cycle verify"'):
            self.assertIn(flag, out)
        self.assertIn("--model fable", dry("cycle-build"))
        self.assertIn('"/talos-review I approve"', dry("review", "I approve", "--model", "opus"))
        self.assertIn("--model opus", dry("review", "x", "--model", "opus"))
        self.assertEqual(len(dry("cycle").strip().splitlines()), 3)
        self.cli("item", "new", "--title", "Docs", "--risk", "low")
        self.cli("item", "set", "ITEM-0001", "--status", "ready")
        self.assertIn("--model sonnet", dry("cycle-build"))  # all ready items low risk: dispatch on Sonnet
        self.cli("item", "new", "--title", "Login")
        self.cli("item", "set", "ITEM-0002", "--status", "ready")
        self.assertIn("--model fable", dry("cycle-build"))


class PhaseProof(CliBase):
    def test_close_needs_cycle_end_and_report(self):
        sys.path.insert(0, str(TALOS))
        import importlib
        import run as R
        importlib.reload(R)
        R.ROOT = self.root
        before = R.ledger_len()
        self.assertIn("cycle.ended", R.proof_missing("cycle-close", before))
        self.cli("cycle", "start")
        self.cli("cycle", "end", "--summary", "done")
        self.assertIn("no report", R.proof_missing("cycle-close", before))
        self.cli("report")
        self.assertIsNone(R.proof_missing("cycle-close", before))
        self.assertIn("no retro.completed", R.proof_missing("retro", R.ledger_len()))
        self.assertIsNone(R.proof_missing("review", before))


class Teams(unittest.TestCase):
    def test_init_stamps_only_staffed_teams_and_prunes(self):
        with tempfile.TemporaryDirectory() as t:
            target = Path(t) / "p"
            target.mkdir()
            env = dict(os.environ, PATH="", UV="")  # no uv: init skips the venv, which keeps the test fast
            def init(*a):
                p = subprocess.run([sys.executable, str(REPO / "init.py"), str(target), *a], env=env, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                return p.stdout
            init("--teams", "core")
            agents = {p.stem for p in (target / ".claude" / "agents").glob("*.md")}
            self.assertIn("chief-of-staff", agents)
            self.assertNotIn("ux-designer", agents)
            self.assertNotIn("head-of-research", agents)
            self.assertEqual(json.loads((target / "company" / "state.json").read_text())["teams"], ["core"])
            init("--teams", "core,design")
            self.assertTrue((target / ".claude" / "agents" / "ux-designer.md").exists())
            out = init("--teams", "core", "--prune")
            self.assertIn("pruned (design-qa, head-of-design, ui-engineer, ux-designer)", out)
            self.assertFalse((target / ".claude" / "agents" / "ux-designer.md").exists())
            self.assertIn("company/.context/", (target / ".gitignore").read_text())
            bad = subprocess.run([sys.executable, str(REPO / "init.py"), str(target), "--teams", "design"], env=env, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
