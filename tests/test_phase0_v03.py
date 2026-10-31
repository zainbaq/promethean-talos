"""Tests for the v0.3 phase 0 fixes: honest stops, resume, verify proof, the kill guard, release every cycle, next step, doctor.

No real Claude runs: the launcher is driven with fixture results.
Run from the repo root: .venv/Scripts/python -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
TALOS = REPO / "template" / "tools" / "talos"
sys.path.insert(0, str(TALOS))

import run as launcher  # noqa: E402

REAL_RUN = subprocess.run  # for git calls during a faked phase


def guard(cmd, root):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(root)})
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    return subprocess.run([sys.executable, str(TALOS / "hooks" / "guard.py")], input=payload, capture_output=True, text=True, env=env)


class Project(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = dict(os.environ, TALOS_ROOT=str(self.root), TALOS_ACTOR="chief-of-staff", TALOS_TIER="executive", PYTHONUTF8="1")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        for k, v in (("user.email", "t@example.com"), ("user.name", "t")):
            subprocess.run(["git", "config", k, v], cwd=self.root, check=True)
        self.cli("init")
        launcher.ROOT = self.root

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), *args], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def events(self):
        return [json.loads(l) for l in (self.root / "company" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    def run_with(self, phase, result, text=""):
        """One launcher phase with `claude -p` replaced by a fixture result."""
        fake = subprocess.CompletedProcess([], 0, json.dumps(result), "")
        with mock.patch.object(launcher.subprocess, "run", side_effect=lambda cmd, **kw: fake if "-p" in cmd else REAL_RUN(cmd, **kw)), \
                mock.patch.object(launcher, "claude_bin", return_value="claude"), mock.patch.dict(os.environ, {"TALOS_ROOT": str(self.root)}):
            return launcher.run_phase(phase, text, None, None, False)


class Stops(Project):
    def test_usage_limit_is_named_never_success(self):
        rc = self.run_with("plan", {"subtype": "success", "is_error": True, "result": "You've hit your limit", "num_turns": 3, "total_cost_usd": 1.0, "session_id": "s"})
        self.assertEqual(rc, 1)
        stop = [e for e in self.events() if e["event"] == "run.stopped"]
        self.assertEqual(len(stop), 1)
        self.assertIn("usage limit", stop[0]["summary"])
        self.assertNotIn("success", stop[0]["summary"])
        self.assertTrue(any(e["event"] == "run.completed" for e in self.events()))  # the cost still counts

    def test_changes_requested_alone_does_not_prove_verify(self):
        self.cli("log", "review.changes_requested", "--ref", "ITEM-0001", "--summary", "no")
        ok = {"subtype": "success", "is_error": False, "result": "done", "num_turns": 1, "total_cost_usd": 0, "session_id": "s"}
        self.assertEqual(self.run_with("cycle-verify", ok), 1)
        self.assertIn("verify.blocked", self.events()[-1]["summary"])

    def test_close_refuses_when_nothing_verified_or_blocked(self):
        ok = {"subtype": "success", "is_error": False, "result": "done", "num_turns": 1, "total_cost_usd": 0, "session_id": "s"}
        self.assertEqual(self.run_with("cycle-close", ok), 1)
        self.assertIn("nothing is verified", self.events()[-1]["summary"])


class Resume(Project):
    def test_saves_worktree_work_and_resumes_the_stopped_phase(self):
        (self.root / "a.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.root, check=True)
        wt = self.root.parent / (self.root.name + "-wt")
        subprocess.run(["git", "worktree", "add", "-q", "-b", "vc/item-0001", str(wt)], cwd=self.root, check=True)
        self.addCleanup(lambda: subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=self.root))
        (wt / "new.txt").write_text("work", encoding="utf-8")
        self.cli("log", "run.stopped", "--ref", "cycle-build", "--summary", "usage limit reached")
        phases, note = launcher.resume_plan("")
        self.assertEqual(phases, launcher.CYCLE)
        self.assertIn("usage limit", note)
        self.assertIn("wip/" + wt.name, note)
        self.assertTrue((wt / "new.txt").exists())  # the files stay where they were
        shown = subprocess.run(["git", "show", f"wip/{wt.name}:new.txt"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(shown.stdout, "work")

    def test_a_finished_rerun_clears_the_stop(self):
        self.cli("log", "run.stopped", "--ref", "plan", "--summary", "limit")
        self.cli("log", "run.completed", "--ref", "plan", "--summary", "ok")
        self.assertIsNone(launcher.resume_plan(""))

    def test_handback_is_filed_as_it_arrives(self):
        out = self.cli("handback", "ITEM-0001", "--role", "engineer", "--text", "ITEM: ITEM-0001\nSTATUS: completed").stdout.strip()
        self.assertIn("STATUS: completed", (self.root / out).read_text(encoding="utf-8"))
        self.assertEqual(self.events()[-1]["event"], "handback.received")


class KillGuard(Project):
    def test_blocks_what_it_cannot_prove_is_ours(self):
        for cmd in ("taskkill /IM python.exe /F", "taskkill /PID 999 /F", "kill -9 999", "pkill node", "killall python",
                    "fuser -k 8000/tcp", "kill $(lsof -t -i:8000)", "lsof -t -i:8000 | xargs kill", "Get-Process node | Stop-Process",
                    "cd x && taskkill //F //PID 999"):
            self.assertEqual(guard(cmd, self.root).returncode, 2, cmd)

    def test_allows_recorded_pids_and_mere_mentions(self):
        self.cli("pid", "add", "4242")
        for cmd in ("kill 4242", "kill -9 4242", "taskkill /PID 4242 /F", "taskkill //F //PID 4242", "Stop-Process -Id 4242",
                    'git commit -m "kill the old worker"', "grep -n kill notes.txt"):
            self.assertEqual(guard(cmd, self.root).returncode, 0, cmd)
        self.cli("pid", "done", "4242")
        self.assertEqual(guard("kill 4242", self.root).returncode, 2)


class ReleaseAndNextStep(Project):
    def _item(self, status):
        iid = self.cli("item", "new", "--title", "Thing").stdout.strip().split()[0]
        self.cli("item", "set", iid, "--status", status, "--evidence", "ok", "--commit", "abc", "--branch", "vc/x")
        return iid

    def test_cycle_will_not_stack_on_unreleased_work(self):
        iid = self._item("verified")
        p = self.cli("cycle", "start", ok=False)
        self.assertEqual(p.returncode, 1)
        self.assertIn(iid, p.stderr)
        self.cli("cycle", "start", "--stack")

    def test_status_names_the_next_step(self):
        self.assertIn("run kickoff", self.cli("status", "--no-spend").stdout)
        self.cli("log", "run.stopped", "--ref", "kickoff", "--summary", "limit")
        self.assertIn("run resume", self.cli("status", "--no-spend").stdout)


class Doctor(Project):
    def test_reports_each_check(self):
        out = self.cli("doctor", ok=False).stdout
        for word in ("Claude Code", "git", "Python", "trust"):
            self.assertIn(word, out)


if __name__ == "__main__":
    unittest.main()
