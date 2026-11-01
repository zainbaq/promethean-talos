"""What the review of v0.3 found. None of these start a runner or a session."""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
import unittest.mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_routes_v03 import Repo  # noqa: E402


class Guard(Repo):
    def setUp(self):
        super().setUp()
        self.stamp()
        self.cli("protect", self.git("symbolic-ref", "--short", "HEAD").stdout.strip(), "--actor", "ceo", "--tier", "ceo")
        self.branch = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()

    def test_every_spelling_is_refused(self):
        b = self.branch
        for cmd in ("tools/talos/talos.cmd automerge on", 'python "tools/talos/talos.py" automerge on', 'talos automerge "on"', f"tools/talos/talos.cmd protect {b} --off",
                    "tools/talos/talos.cmd notify https://example.com", "git push", "git push origin", f'git push origin "{b}"', f"git -C . push origin {b}", f"git push origin HEAD",
                    f"git -C . update-ref refs/heads/{b} HEAD", f"git branch -f '{b}' HEAD", f"git switch {b} && git merge --ff-only x", f"git checkout {b}",
                    "git config core.hooksPath /dev/null", "git -c core.hooksPath=x commit -m y"):
            self.assertEqual(self.guard(cmd).returncode, 2, cmd)

    def test_ordinary_work_still_passes(self):
        for cmd in ("git push origin vc/item-0001", f"git log {self.branch}", f"git checkout {self.branch} -- a.txt", "git switch -c vc/item-0002", "tools/talos/talos.cmd status --brief"):
            self.assertEqual(self.guard(cmd).returncode, 0, cmd)

    def test_powershell_and_notify_file(self):
        payload = {"tool_name": "PowerShell", "tool_input": {"command": "git push"}, "cwd": str(self.root)}
        env = dict(self.env, CLAUDE_PROJECT_DIR=str(self.root))
        guard = str(self.root / "tools/talos/hooks/guard.py")
        run = lambda p: subprocess.run([sys.executable, guard], input=json.dumps(p), env=env, capture_output=True, text=True, encoding="utf-8").returncode  # noqa: E731
        self.assertEqual(run(payload), 2)
        self.assertEqual(run({"tool_name": "Write", "tool_input": {"file_path": str(self.root / ".talos/notify.json")}, "cwd": str(self.root)}), 2)
        self.assertIn("PowerShell", (self.root / ".claude/settings.json").read_text(encoding="utf-8"))


class Record(Repo):
    def setUp(self):
        super().setUp()
        self.stamp()
        self.next()
        import talos
        self.talos = talos

    def test_a_rejection_or_new_verification_ends_an_approval(self):
        t = self.talos
        yes = {"id": "E1", "event": "release.approved", "ref": "ITEM-0001"}
        self.assertEqual(t.live_approval([yes], "ITEM-0001"), yes)
        self.assertIsNone(t.live_approval([yes, {"id": "E2", "event": "release.rejected", "ref": "ITEM-0001"}], "ITEM-0001"))
        self.assertIsNone(t.live_approval([yes, {"id": "E2", "event": "item.verified", "ref": "ITEM-0001"}], "ITEM-0001"))
        self.assertEqual(t.live_approval([yes, {"id": "E2", "event": "release.rejected", "ref": "ITEM-0002"}], "ITEM-0001"), yes)

    def test_a_rejected_release_does_not_merge(self):
        t = self.talos
        items = [{"id": "ITEM-0001", "status": "verified"}]
        ev = [{"id": "E0", "event": "plan.approved", "ref": None}, {"id": "E1", "event": "release.approved", "ref": "ITEM-0001"},
              {"id": "E2", "event": "release.rejected", "ref": "ITEM-0001", "summary": "no"}, {"id": "E3", "event": "run.completed", "ref": "review", "phase": "review"}]
        action = t.next_action(ev, {}, items, {"status": "approved"})[0]
        self.assertFalse(action and "merge" in action[2], action)

    def test_a_moved_branch_holds_merges_and_asks(self):
        t = self.talos
        items = [{"id": "ITEM-0001", "status": "verified"}, {"id": "ITEM-0002", "route": "fast", "status": "ready", "title": "x"}]
        ev = [{"id": "E0", "event": "release.approved", "ref": "ITEM-0001"}, {"id": "E1", "event": "question.asked", "ref": "Q-0001", "actor": "talos-run", "summary": "main moved from a to b during plan."}]
        with unittest.mock.patch.object(t, "open_ceo_blocks", return_value={"Q-0001": "x"}):
            action, why = t.next_action(ev, {}, items, {"status": "approved"})
        self.assertIsNone(action)
        self.assertIn("moved", why)

    def test_one_stuck_ask_does_not_block_the_next(self):
        t = self.talos
        items = [{"id": "ITEM-0001", "route": "dept", "dept": "gtm", "status": "ready", "title": "x", "priority": "P1"}, {"id": "ITEM-0002", "route": "dept", "dept": "gtm", "status": "ready", "title": "y", "priority": "P2"}]
        act = lambda phase, text, key, why, tried={"route:ITEM-0001"}: ((phase, text, key), why) if key not in tried else (None, "tried")  # noqa: E731
        self.assertEqual(t.routed_step([], {}, items, act)[0][2], "route:ITEM-0002")

    def test_git_answers(self):
        t = self.talos
        act = lambda *a: (a, a[3])  # noqa: E731
        with unittest.mock.patch("survey.is_repo", return_value=False):
            for said, goes in (("yeah, do it", True), ("yes", True), ("sounds good", True), ("no", False), ("not yet", False), ("don't", False)):
                ev = [{"id": "E1", "event": "question.asked", "ref": "Q-1", "blocks": "git-init"}, {"id": "E2", "event": "question.answered", "ref": "Q-1", "summary": said}]
                self.assertEqual(bool(t.adoption_step(ev, {"adopt": "files"}, act)[0]), goes, said)

    def test_only_the_ceo_speaks_for_the_ceo(self):
        env = dict(self.env, TALOS_PHASE="cycle-build", PYTHONUTF8="1")
        tool = str(self.root / "tools/talos/talos.py")
        run = lambda *a, e=env: subprocess.run([sys.executable, tool, *a], cwd=self.root, env=e, capture_output=True, text=True, encoding="utf-8").returncode  # noqa: E731
        q = self.cli("ask", "--for", "ceo", "which?").split()[0]
        for args in (["approve", "plan", "--quote", "ok"], ["answer", q, "mine"], ["log", "release.approved", "--ref", "ITEM-0001", "--actor", "ceo"], ["reject", "plan", "--reason", "x"], ["automerge", "on"]):
            self.assertNotEqual(run(*args), 0, args)
        self.assertEqual(run("approve", "plan", "--quote", "ok", e=dict(env, TALOS_PHASE="review")), 0)
        self.assertEqual(run("approve", "plan", "--quote", "ok", e={k: v for k, v in env.items() if k != "TALOS_PHASE"}), 0)

    def test_questions_can_be_read(self):
        q = self.cli("ask", "--for", "ceo", "May I?").split()[0]
        self.assertIn("May I?", self.cli("questions"))
        self.cli("answer", q, "yes")
        self.assertNotIn("May I?", self.cli("questions"))

    def test_recovered_decisions_are_allowed(self):
        self.cli("decision", "add", "--title", "Recovered: x", "--status", "recovered")


class Runner(Repo):
    def setUp(self):
        super().setUp()
        self.stamp()
        self.next()
        import run as launcher
        launcher.ROOT, launcher.LEFT_USD = self.root, None
        self.launcher = launcher
        self.addCleanup(setattr, launcher, "LEFT_USD", None)

    def test_every_phase_stops_at_what_is_left(self):
        self.assertEqual(self.launcher.budget_cap("plan"), [])
        self.launcher.LEFT_USD = 3.5
        self.assertEqual(self.launcher.budget_cap("plan"), ["--max-budget-usd", "3.50"])

    def test_chat_text_can_not_escape_cmd(self):
        with unittest.mock.patch.object(self.launcher.os, "name", "nt"):
            out = self.launcher.through_cmd(["c:/x/claude.cmd", 'a" & calc & "b'])
            self.assertEqual(self.launcher.through_cmd(["c:/x/claude.exe", "a&b"])[1], "a&b")
        self.assertFalse(set('"&|<>^%') & set(out[1]))

    def test_any_character_reaches_a_file(self):
        code = "import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace'); print('\u2192')"
        self.assertEqual(subprocess.run([sys.executable, "-c", code], capture_output=True, env={k: v for k, v in self.env.items() if k != "PYTHONUTF8"}).returncode, 0)
        for name in ("run.py", "talos.py"):
            self.assertIn("reconfigure(encoding", (self.root / "tools/talos" / name).read_text(encoding="utf-8"))

    def test_saving_leaves_a_developers_worktree_alone_and_keeps_staging(self):
        mine = self.root.parent / (self.root.name + "-mine")
        ours = self.root.parent / (self.root.name + "-ours")
        self.git("worktree", "add", "-q", "-b", "feature", str(mine))
        self.git("worktree", "add", "-q", "-b", "vc/item-0001", str(ours))
        self.addCleanup(lambda: [self.git("worktree", "remove", "--force", str(p)) for p in (mine, ours)])
        for tree in (mine, ours):
            (tree / "staged.txt").write_text("s", encoding="utf-8")
            subprocess.run(["git", "add", "staged.txt"], cwd=tree, check=True)
            (tree / "loose.txt").write_text("l", encoding="utf-8")
        saved = self.launcher.save_worktrees()
        self.assertEqual(len(saved), 1)
        self.assertIn(ours.name, saved[0])
        for tree in (mine, ours):
            status = subprocess.run(["git", "status", "--porcelain"], cwd=tree, capture_output=True, text=True).stdout
            self.assertIn("A  staged.txt", status, "still staged")
        shown = self.git("show", f"wip/{ours.name}:loose.txt")
        self.assertEqual(shown.stdout, "l")


class Stamping(Repo):
    def init(self, *extra):
        p = subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), *extra], env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_add_team_does_not_lose_your_edit_at_the_next_upgrade(self):
        self.init("--teams", "core")
        mine = self.root / ".claude/agents/engineer.md"
        mine.write_text("mine\n", encoding="utf-8")
        self.init("--add-team", "research")
        self.init()
        self.init("--upgrade")
        self.assertEqual(mine.read_text(encoding="utf-8"), "mine\n")

    def test_a_subfolder_of_a_repo_can_be_stamped(self):
        sub = self.root / "pkg"
        sub.mkdir()
        p = subprocess.run([sys.executable, str(REPO / "init.py"), str(sub), "--teams", "core", "--no-commit"], env={k: v for k, v in self.env.items() if k != "TALOS_ROOT"}, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        self.assertTrue((sub / "tools/talos/talos.py").exists())

    def test_protecting_a_branch_you_are_not_on_still_gives_the_work_its_own_branch(self):
        main = self.git("symbolic-ref", "--short", "HEAD").stdout.strip()
        self.git("switch", "-q", "-c", "dev")
        self.init("--teams", "core", "--protect", main)
        self.assertEqual(self.cli("base"), "talos/work")
        self.assertEqual(self.git("rev-parse", "--verify", "-q", "refs/heads/talos/work").returncode, 0)


if __name__ == "__main__":
    unittest.main()
