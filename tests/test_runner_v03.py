"""The runner's choice of next phase, presets on the launcher's command line, and CEO messages. No real Claude runs."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TALOS = REPO / "template" / "tools" / "talos"
sys.path.insert(0, str(TALOS))

import talos  # noqa: E402


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, TALOS_ROOT=str(self.root), TALOS_ACTOR="chief-of-staff", TALOS_TIER="executive", PYTHONUTF8="1")
        self.cli("init")
        talos.ROOT, talos.CO = self.root, self.root / "company"
        talos.LEDGER, talos.STATE, talos.QUESTIONS = talos.CO / "ledger.jsonl", talos.CO / "state.json", talos.CO / "questions.md"

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), *args], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def next(self, tried=()):
        fm, _ = talos.parse_frontmatter((talos.CO / "charter.md").read_text(encoding="utf-8"))
        return talos.next_action(talos.read_ledger(), talos.read_state(), talos.load_items(), fm, tried)

    def phase(self):
        action, why = self.next()
        return action[0] if action else why

    def test_walks_the_whole_lifecycle_and_waits_at_each_gate(self):
        self.assertIn("what to build", self.phase())
        (talos.CO / "brief.md").write_text("A thing", encoding="utf-8")
        self.assertEqual(self.phase(), "kickoff")
        self.cli("log", "charter.proposed", "--summary", "c")
        self.assertIn("charter", self.phase())
        self.cli("approve", "charter", "--quote", "ok")
        self.assertEqual(self.phase(), "plan")
        self.cli("log", "plan.proposed", "--summary", "p")
        self.assertIn("plan", self.phase())
        self.cli("reject", "plan", "--reason", "too big")
        action, _ = self.next()
        self.assertEqual(action[0], "plan")
        self.assertIn("too big", action[1])
        self.cli("log", "plan.proposed", "--summary", "p2")
        self.cli("approve", "plan", "--quote", "ok")
        self.assertIn("nothing is ready", self.phase())
        iid = self.cli("item", "new", "--title", "Thing").split()[0]
        self.cli("item", "set", iid, "--status", "ready")
        self.assertEqual(self.phase(), "cycle-build")
        self.cli("cycle", "start")
        self.assertEqual(self.phase(), "cycle-build")
        self.cli("log", "run.completed", "--ref", "cycle-build", "--summary", "x")
        ev = talos.read_ledger()  # the launcher's run.completed carries `phase` at the top level
        lines = [json.dumps(dict(e, phase="cycle-build") if e["event"] == "run.completed" else e) for e in ev]
        talos.LEDGER.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(self.phase(), "cycle-verify")
        self.cli("item", "set", iid, "--status", "verified", "--evidence", "ok")
        self.cli("cycle", "end", "--summary", "x")
        self.assertIn("release decision", self.phase())
        self.cli("approve", "release", "--ref", iid, "--quote", "ok")
        action, _ = self.next()
        self.assertEqual(action[0], "review")
        self.assertIn(iid, action[1])

    def test_a_message_is_read_once_then_waits_rather_than_looping(self):
        self.cli("say", "--text", "keep it warm")
        action, _ = self.next()
        self.assertEqual(action[0], "triage")
        retry, why = self.next({action[2]})
        self.assertIsNone(retry)
        self.assertIn("already tried", why)
        self.cli("ack", "MSG-0001", "--became", "note", "--note", "noted")
        self.assertNotEqual(self.next({action[2]})[0], action)

    def test_stop_waits_for_the_word_resume(self):
        self.cli("log", "run.stopped", "--ref", "plan", "--summary", "limit")
        action, why = self.next()
        self.assertIsNone(action)
        self.assertIn("resume", why)
        self.cli("say", "--text", "Resume")
        self.assertEqual(self.next()[0][0], "resume")

    def test_pause_is_a_control_word_not_a_message(self):
        self.cli("say", "--text", "pause")
        self.assertEqual(talos.runner_word(talos.read_ledger())[0], "pause")
        self.assertEqual(talos.unacked_messages(), [])

    def test_preset_sets_models_and_fable_only_on_heavy(self):
        self.assertEqual(self.cli("preset"), "medium")
        for name, models in ((n, talos.preset_models(n)) for n in talos.PRESETS):
            self.assertEqual("fable" in models.values(), name == "heavy", name)
        self.cli("preset", "heavy")
        self.assertEqual(talos.preset_name(), "heavy")
        self.assertIn("preset changed", talos.read_inbox()[-1]["text"])
        env = dict(self.env)
        dry = subprocess.run([sys.executable, str(TALOS / "run.py"), "plan", "--dry-run"], cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("--model fable", dry)
        self.assertIn("chief-architect=fable", dry)
        once = subprocess.run([sys.executable, str(TALOS / "run.py"), "plan", "--dry-run", "--preset", "lite"], cwd=self.root, env=env, capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("--model sonnet", once)
        self.assertIn("risk high", once)


if __name__ == "__main__":
    unittest.main()
