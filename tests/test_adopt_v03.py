"""Plugging into any folder: the first reply, the survey, the baseline, what is left alone, and the runner's steps. No model runs."""
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

import survey  # noqa: E402
import talos  # noqa: E402

TEST_PASS = "def test_ok():\n    assert True\n"
TEST_FAIL = "def test_bad():\n    assert False\n"


class Folder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.env = dict(os.environ, TALOS_ROOT=str(self.root), TALOS_ACTOR="chief-of-staff", TALOS_TIER="executive", PYTHONUTF8="1")

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.email=t@e", "-c", "user.name=t", *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=True).stdout

    def write(self, rel, text="x\n"):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def make_repo(self):
        self.write("app/main.py", "print('hi')  # TODO later\n")
        self.write("requirements.txt", "")
        self.write("tests/test_a.py", TEST_PASS)
        self.write("tests/test_b.py", TEST_FAIL)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", "first")

    def stamp(self, *extra):
        p = subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), "--teams", "core", *extra], capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"))
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), *args], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def events(self):
        return [json.loads(l) for l in (self.root / "company" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    def next(self):
        talos.ROOT, talos.CO = self.root, self.root / "company"
        talos.LEDGER, talos.STATE, talos.QUESTIONS = talos.CO / "ledger.jsonl", talos.CO / "state.json", talos.CO / "questions.md"
        fm, _ = talos.parse_frontmatter((talos.CO / "charter.md").read_text(encoding="utf-8"))
        return talos.next_action(talos.read_ledger(), talos.read_state(), talos.load_items(), fm)


class FirstReply(Folder):
    def test_empty_folder_asks_what_we_are_making(self):
        self.stamp()
        self.assertIn("What are we making?", self.cli("start"))
        self.assertIsNone(self.next()[0])
        self.cli("start")  # repeating it asks nothing new
        self.assertEqual(sum(e["event"] == "question.asked" for e in self.events()), 1)
        self.cli("answer", "--by", "ceo", "Q-0001", "a timer")
        action, _ = self.next()
        self.assertEqual(action[0], "kickoff")
        self.assertIn("a timer", action[1])

    def test_files_without_git_ask_first_and_git_only_on_yes(self):
        self.write("plan.docx")
        self.write("numbers.xlsx")
        self.write("notes.md")
        self.stamp()
        reply = self.cli("start")
        self.assertIn("git init", reply)
        self.assertIn("3 files", reply)
        self.assertIn("spreadsheets", reply)
        self.assertFalse((self.root / ".git").exists())
        self.cli("answer", "--by", "ceo", "Q-0001", "no thanks")
        self.assertIn("only questions and drafts", self.next()[1])
        self.assertFalse((self.root / ".git").exists())

    def test_saying_yes_creates_a_local_repo_with_their_files(self):
        self.write("notes.md")
        self.stamp()
        self.cli("start")
        self.cli("answer", "--by", "ceo", "Q-0001", "yes please")
        action, _ = self.next()
        self.assertEqual(action[0], "git-init")
        talos.init_git()
        self.assertIn("notes.md", self.git("ls-files"))
        self.assertEqual(self.git("remote").strip(), "")

    def test_a_repo_says_what_it_sees_and_what_reading_costs(self):
        self.make_repo()
        self.stamp()
        reply = self.cli("start")
        self.assertIn("Python", reply)
        self.assertIn("hard cap of $6", reply)
        self.assertEqual(json.loads(self.cli("--help") and (self.root / "company/knowledge/inventory.json").read_text(encoding="utf-8"))["size"], "small")


class LeavesItAlone(Folder):
    def test_a_repo_keeps_its_ignores_line_endings_and_other_changes(self):
        self.make_repo()
        self.write(".gitignore", "*.log\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "ignore")
        self.write("app/main.py", "print('half done')\n")  # the developer's work in progress
        self.write("staged.py", "x = 1\n")
        self.git("add", "staged.py")
        out = self.stamp()
        self.assertIn("committed the framework", out)
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8"), "*.log\n")
        self.assertFalse((self.root / ".gitattributes").exists())
        self.assertIn(".talos/", (self.root / ".git/info/exclude").read_text(encoding="utf-8"))
        self.assertIn("half done", (self.root / "app/main.py").read_text(encoding="utf-8"))
        status = self.git("status", "--porcelain")
        self.assertIn(" M app/main.py", status)
        self.assertIn("A  staged.py", status)
        last = self.git("show", "--stat", "--format=%s", "HEAD")
        self.assertIn("Add Talos", last)
        self.assertNotIn("app/main.py", last)
        self.assertNotIn("staged.py", last)

    def test_baseline_records_known_failures_without_touching_the_checkout(self):
        self.make_repo()
        self.stamp()
        self.cli("start")
        self.write("app/main.py", "print('half done')\n")
        before = self.git("status", "--porcelain")
        summary = self.cli("baseline")
        self.assertIn("1 passed, 1 failed", summary)
        known = json.loads((self.root / "company/baseline.json").read_text(encoding="utf-8"))
        self.assertEqual(known["failures"], ["tests/test_b.py::test_bad"])
        self.assertIn("never regress", (self.root / "company/baseline.md").read_text(encoding="utf-8"))
        self.assertEqual({l for l in self.git("status", "--porcelain").splitlines() if "company/" not in l}, {l for l in before.splitlines() if "company/" not in l})
        self.assertNotIn("talos-baseline", self.git("worktree", "list"))
        self.assertIn("no regressions", self.cli("baseline", "--check"))
        self.write("tests/test_c.py", "def test_new():\n    assert False\n")
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), "baseline", "--check"], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 1)
        self.assertIn("test_new", p.stderr)


class Adoption(Folder):
    def test_runner_goes_survey_baseline_read_gate_then_waits_for_work(self):
        self.make_repo()
        self.stamp()
        self.cli("start")
        self.assertEqual(self.next()[0][0], "baseline")
        self.cli("baseline")
        self.assertEqual(self.next()[0][0], "adopt")
        self.write("company/knowledge/product.md", "# Thing\n\nIt does things (app/main.py:1).\n")
        self.cli("ask", "Who is it for?", "--ref", "understanding")
        self.cli("log", "understanding.proposed", "--summary", "a thing")
        self.assertIsNone(self.next()[0])
        self.cli("answer", "--by", "ceo", "Q-0001", "Me")
        self.assertIn("understanding", self.next()[1])
        self.cli("reject", "understanding", "--reason", "it is for teams")
        action, _ = self.next()
        self.assertEqual(action[0], "adopt")
        self.assertIn("it is for teams", action[1])
        self.cli("log", "understanding.proposed", "--summary", "corrected")
        self.cli("approve", "understanding", "--quote", "right")
        charter = (self.root / "company/charter.md").read_text(encoding="utf-8")
        self.assertIn("status: approved", charter)
        self.assertIn("It does things", charter)
        self.assertIn("Who is it for?", charter)
        self.assertIn("Me", charter)
        self.assertIn("knows this project", self.next()[1])

    def test_the_read_is_capped_by_size(self):
        self.make_repo()
        self.stamp()
        self.cli("start")
        dry = subprocess.run([sys.executable, str(TALOS / "run.py"), "adopt", "--dry-run"], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8").stdout
        self.assertIn("--max-budget-usd 6", dry)
        self.assertNotIn("--max-budget-usd", subprocess.run([sys.executable, str(TALOS / "run.py"), "plan", "--dry-run"], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8").stdout)


class Survey(unittest.TestCase):
    def test_size_classes(self):
        self.assertEqual(survey.size_class(100, 10), "small")
        self.assertEqual(survey.size_class(6000, 10), "medium")
        self.assertEqual(survey.size_class(100, 5000), "large")

    def test_pytest_parse(self):
        out = "FAILED tests/a.py::t - boom\nERROR tests/b.py\n1 failed, 3 passed, 1 error in 0.2s\n"
        got = survey.parse_pytest(out)
        self.assertEqual((got["passed"], got["failed"], got["errors"]), (3, 1, 1))
        self.assertEqual(got["failures"], ["tests/a.py::t", "tests/b.py"])
        self.assertEqual(survey.new_failures({"failures": ["tests/a.py::t"]}, {"failures": ["tests/a.py::t", "x"]}), ["x"])


if __name__ == "__main__":
    unittest.main()
