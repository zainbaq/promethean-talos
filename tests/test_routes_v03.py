"""v0.3 phase 3: protected branches, asks routed by what they need, drift, and departments that only draft."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TALOS = REPO / "template" / "tools" / "talos"
GUARD = TALOS / "hooks" / "guard.py"
sys.path.insert(0, str(TALOS))
import talos  # noqa: E402


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = dict(os.environ, TALOS_ROOT=str(self.root), TALOS_ACTOR="coordinator", TALOS_TIER="execution", PYTHONUTF8="1")
        self.env.pop("CLAUDECODE", None)
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.email", "dev@example.com")
        self.git("config", "user.name", "dev")
        (self.root / "app.py").write_text("x = 1\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-qm", "first")

    def git(self, *args, env=None, check=True):
        p = subprocess.run(["git", *args], cwd=self.root, env=env or self.env, capture_output=True, text=True, encoding="utf-8")
        if check:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p

    def stamp(self, *extra):
        p = subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), "--teams", "core", *extra], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def cli(self, *args, ok=True):
        p = subprocess.run([sys.executable, str(TALOS / "talos.py"), *args], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        if ok:
            self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip() if ok else p

    def guard(self, command, cwd=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.root)}
        return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload), env=dict(self.env, CLAUDE_PROJECT_DIR=str(self.root)),
                              capture_output=True, text=True, encoding="utf-8")

    def next(self):
        talos.ROOT, talos.CO = self.root, self.root / "company"
        talos.LEDGER, talos.STATE, talos.QUESTIONS = talos.CO / "ledger.jsonl", talos.CO / "state.json", talos.CO / "questions.md"
        fm, _ = talos.parse_frontmatter((talos.CO / "charter.md").read_text(encoding="utf-8"))
        return talos.next_action(talos.read_ledger(), talos.read_state(), talos.load_items(), fm)

    def adopted(self):
        self.cli("log", "survey.completed", "--summary", "s")
        self.cli("log", "baseline.recorded", "--summary", "b")
        state = json.loads((self.root / "company/state.json").read_text(encoding="utf-8"))
        state["adopt"] = "repo"
        (self.root / "company/state.json").write_text(json.dumps(state), encoding="utf-8")

    def ask(self, text):
        return self.cli("say", "--text", text)


class ProtectedBranch(Repo):
    def setUp(self):
        super().setUp()
        self.first = self.git("rev-parse", "main").stdout.strip()
        self.said = self.stamp("--protect", "main")

    def test_stamping_leaves_main_and_the_checkout_alone(self):
        self.assertEqual(self.git("rev-parse", "main").stdout.strip(), self.first)
        self.assertEqual(self.git("symbolic-ref", "--short", "HEAD").stdout.strip(), "main")
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")
        self.assertIn("tools/talos/talos.py", self.git("ls-tree", "-r", "--name-only", "talos/work").stdout)
        self.assertEqual(self.cli("base"), "talos/work")

    def test_release_merges_happen_off_the_developers_checkout(self):
        where = Path(self.cli("base", "--worktree"))
        self.assertNotEqual(where.resolve(), self.root)
        self.assertEqual(subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=where, capture_output=True, text=True).stdout.strip(), "talos/work")

    def test_guard_refuses_every_way_onto_main(self):
        for cmd in ("git merge vc/item-0001", 'git commit -m "x"', "git push origin main", "git push origin HEAD:main",
                    "git branch -f main HEAD", "git update-ref refs/heads/main HEAD", "git commit --no-verify -m x", "tools/talos/talos protect main --off"):
            self.assertEqual(self.guard(cmd).returncode, 2, cmd)

    def test_guard_lets_work_happen_on_branches(self):
        where = self.cli("base", "--worktree")
        for cmd in (f'git -C "{where}" merge --no-ff --no-edit vc/item-0001', f'cd "{where}" && git commit -m x', "git push origin vc/item-0001", "git log --oneline"):
            self.assertEqual(self.guard(cmd).returncode, 0, cmd)

    def test_git_hook_stops_the_company_not_the_developer(self):
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")
        self.git("add", "app.py")
        stopped = self.git("commit", "-qm", "company", env=dict(self.env, CLAUDECODE="1"), check=False)
        self.assertNotEqual(stopped.returncode, 0)
        self.assertIn("protected", stopped.stderr)
        self.git("commit", "-qm", "the developer")

    def test_the_ceo_can_lift_it(self):
        self.cli("protect", "main", "--off")
        self.assertEqual(self.guard('git commit -m "x"').returncode, 0)

    def test_hand_commits_show_up_and_reach_the_work_branch(self):
        self.cli("drift", "--seen")
        (self.root / "app.py").write_text("x = 2\n", encoding="utf-8")
        self.git("commit", "-qam", "by hand")
        self.assertIn("app.py", self.cli("drift"))
        self.assertIn("by hand", self.git("log", "--format=%s", "talos/work").stdout)
        self.cli("drift", "--seen")
        self.assertIn("nothing changed", self.cli("drift"))


class Unprotected(Repo):
    def test_a_stamp_without_the_rule_still_commits_where_it_did(self):
        self.stamp()
        self.assertIn("Add Talos", self.git("log", "--format=%s", "-1", "main").stdout)
        self.assertEqual(self.cli("base"), "main")
        self.assertEqual(Path(self.cli("base", "--worktree")).resolve(), self.root)

    def test_company_built_commits_are_not_drift(self):
        self.stamp()
        self.cli("drift", "--seen")
        self.git("switch", "-q", "-c", "vc/item-0001")
        (self.root / "built.py").write_text("y = 1\n", encoding="utf-8")
        self.git("add", "built.py")
        self.git("commit", "-qm", "built")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "--no-edit", "vc/item-0001")
        self.assertIn("nothing changed", self.cli("drift"))


class Routes(Repo):
    def setUp(self):
        super().setUp()
        self.stamp()

    def test_a_message_goes_to_triage_first(self):
        self.ask("fix the typo")
        self.assertEqual(self.next()[0][0], "triage")

    def test_a_fix_runs_as_soon_as_the_baseline_exists_and_says_so(self):
        self.adopted()
        mid = self.ask("fix the typo")
        reply = self.cli("triage", mid, "--route", "fast", "--title", "Fix typo", "--estimate", "about $2", "--risk", "low")
        self.assertEqual(reply, "Fast lane, engineering, about $2, you'll approve one branch")
        action = self.next()[0]
        self.assertEqual(action[:2], ("task", "ITEM-0001"))

    def test_an_item_waits_for_the_understanding_gate(self):
        self.adopted()
        self.cli("triage", self.ask("rebuild reports"), "--route", "item", "--title", "Reports")
        self.assertEqual(self.next()[0][0], "adopt")
        self.cli("log", "understanding.proposed", "--summary", "u")
        self.cli("approve", "understanding", "--quote", "ok")
        self.assertEqual(self.next()[0][:2], ("task", "ITEM-0001"))

    def test_a_question_is_answered_without_an_item(self):
        self.cli("triage", self.ask("what does this do?"), "--route", "answer", "--note", "It sets x.")
        self.assertEqual(self.cli("queue"), "nothing queued")
        self.assertEqual(self.cli("inbox"), "no unacknowledged messages")

    def test_routes_can_be_overridden(self):
        self.adopted()
        self.cli("triage", self.ask("fix it"), "--route", "fast", "--title", "Fix")
        self.cli("triage", self.ask("make it an initiative"), "--route", "initiative", "--item", "ITEM-0001")
        self.assertIn("initiative", self.cli("queue"))

    def test_asks_wait_for_an_open_cycle(self):
        self.adopted()
        self.cli("triage", self.ask("fix it"), "--route", "fast", "--title", "Fix")
        self.cli("cycle", "start", "--budget", "1 item")
        self.assertNotEqual(self.next()[0][:2], ("task", "ITEM-0001"))

    def test_a_ready_ask_does_not_wait_for_another_release_or_a_gate_question(self):
        self.adopted()
        self.cli("ask", "Who uses it?", "--ref", "understanding", "--actor", "chief-of-staff", "--tier", "executive")
        self.cli("triage", self.ask("fix it"), "--route", "fast", "--title", "Fix")
        self.assertEqual(self.next()[0][0], "task")


class Departments(Repo):
    def test_unstaffed_says_how_and_blocks(self):
        self.stamp()
        reply = self.cli("triage", self.ask("launch copy"), "--route", "dept", "--dept", "gtm", "--title", "Launch copy")
        self.assertIn("--teams gtm", reply)
        self.assertEqual(self.cli("queue"), "nothing queued")

    def test_a_draft_runs_at_once_and_its_question_holds_up_nothing(self):
        subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), "--teams", "core,gtm"], capture_output=True, check=True)
        self.adopted()
        reply = self.cli("triage", self.ask("launch copy"), "--route", "dept", "--dept", "gtm", "--title", "Launch copy", "--estimate", "about $1")
        self.assertEqual(reply, "Department, gtm, about $1, a draft comes to you; nothing is sent")
        self.assertEqual(self.next()[0][:2], ("department", "ITEM-0001"))
        self.cli("item", "set", "ITEM-0001", "--status", "completed", "--evidence", "company/gtm/copy/launch.md")
        self.cli("ask", "Done?", "--ref", "ITEM-0001", "--actor", "coordinator", "--tier", "execution")
        self.assertNotIn("question", self.next()[1])

    def test_gtm_roles_cannot_run_commands(self):
        for role in ("head-of-gtm", "gtm-analyst"):
            head = (REPO / "template/.claude/agents" / f"{role}.md").read_text(encoding="utf-8").split("---")[1]
            self.assertNotIn("Bash", head)

    def test_launch_gate_refuses_open_lines(self):
        self.stamp()
        self.assertNotEqual(self.cli("gate", "launch", ok=False).returncode, 0)
        (self.root / "company/launch").mkdir()
        (self.root / "company/launch/readiness.md").write_text("- [ ] backups\n- [x] docs\n", encoding="utf-8")
        self.assertIn("backups", self.cli("gate", "launch", ok=False).stderr)
        (self.root / "company/launch/readiness.md").write_text("- [x] backups\n", encoding="utf-8")
        self.cli("log", "launch.proposed", "--summary", "ready")
        self.cli("approve", "launch", "--quote", "go")
        self.assertIn("gate open", self.cli("gate", "launch"))


class Safety(Repo):
    def test_suites_that_name_real_hosts_only_run_blocked(self):
        self.stamp()
        (self.root / "company/knowledge").mkdir(exist_ok=True)
        (self.root / "company/knowledge/inventory.json").write_text(json.dumps({"hosts_in_tests": [{"host": "prod.example.com"}]}), encoding="utf-8")
        for cmd in ("pytest", ".venv/Scripts/python -m pytest tests", "cd x && pytest -q", "npm test"):
            self.assertEqual(self.guard(cmd).returncode, 2, cmd)
        self.assertEqual(self.guard("tools/talos/talos test --where .").returncode, 0)
        self.assertEqual(self.guard('git commit -m "pytest passes"').returncode, 0)

    def test_understanding_puts_the_ceos_words_first(self):
        self.stamp()
        (self.root / "company/knowledge").mkdir(exist_ok=True)
        (self.root / "company/knowledge/product.md").write_text("# App\n\n## What it does\n\nThings.\n\n## Not known\n\nWhether it is backed up.\n\n## Risks\n\nSome.\n", encoding="utf-8")
        q = self.cli("ask", "Backed up?", "--ref", "understanding", "--actor", "chief-of-staff", "--tier", "executive")
        self.cli("answer", q, "No", "--by", "ceo")
        self.ask("anything built stays on its own branch")
        self.cli("approve", "understanding", "--quote", "ok")
        charter = (self.root / "company/charter.md").read_text(encoding="utf-8")
        self.assertNotIn("Not known", charter)
        self.assertIn("## Risks", charter)
        self.assertIn("anything built stays on its own branch", charter)
        self.assertLess(charter.index("What the CEO told us"), charter.index("What it does"))


if __name__ == "__main__":
    unittest.main()
