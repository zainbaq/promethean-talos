"""v0.3 phase 4: packaging, upgrades, the record on a protected project, notifications and auto-merge."""
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_routes_v03 import Repo  # noqa: E402

TALOS = REPO / "template" / "tools" / "talos"


class Packaging(unittest.TestCase):
    def test_versions_agree(self):
        plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], (TALOS / "VERSION").read_text(encoding="utf-8").strip())
        self.assertIn(f"## {plugin['version']}", (TALOS / "CHANGES.md").read_text(encoding="utf-8"))


class Install(Repo):
    def init(self, *extra):
        p = subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), *extra], env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def test_control_room_ships_unless_headless(self):
        self.init("--teams", "core", "--headless")
        self.assertFalse((self.root / "tools/talos/viz/server.py").exists())
        self.init()
        self.assertFalse((self.root / "tools/talos/viz/server.py").exists(), "a re-stamp keeps the choice")
        self.init("--viz")
        self.assertTrue((self.root / "tools/talos/viz/server.py").exists())

    def test_upgrade_keeps_what_you_changed(self):
        self.init("--teams", "core")
        mine = self.root / ".claude/agents/engineer.md"
        mine.write_text("mine\n", encoding="utf-8")
        gone = self.root / ".claude/agents/librarian.md"
        gone.unlink()
        (self.root / "tools/talos/VERSION").write_text("0.2.0\n", encoding="utf-8")
        ledger = (self.root / "company/ledger.jsonl").read_bytes()
        out = self.init("--upgrade")
        self.assertEqual(mine.read_text(encoding="utf-8"), "mine\n")
        self.assertIn(".claude/agents/engineer.md", out)
        self.assertIn("## 0.3.0", out)
        self.assertTrue(gone.exists())
        self.assertFalse((self.root / ".claude/agents/head-of-gtm.md").exists(), "the teams stay")
        self.assertEqual((self.root / "company/ledger.jsonl").read_bytes(), ledger)
        self.init("--upgrade")
        self.assertEqual(mine.read_text(encoding="utf-8"), "mine\n", "still yours on the next upgrade")

    def test_add_team_keeps_the_others(self):
        self.init("--teams", "core")
        self.init("--add-team", "gtm")
        self.assertTrue((self.root / ".claude/agents/head-of-gtm.md").exists())
        self.assertEqual(json.loads((self.root / "company/state.json").read_text(encoding="utf-8"))["teams"], ["core", "gtm"])


class Protected(Repo):
    def setUp(self):
        super().setUp()
        self.stamp("--protect", "main")
        self.main = self.git("rev-parse", "main").stdout.strip()

    def test_record_gets_a_branch_of_its_own(self):
        self.next()
        import talos
        first = talos.save_record()
        self.assertTrue(first)
        files = self.git("ls-tree", "-r", "--name-only", "talos/record").stdout.split()
        self.assertIn("company/ledger.jsonl", files)
        self.assertFalse([f for f in files if not f.startswith("company/")])
        self.assertIsNone(talos.save_record(), "nothing new, no commit")
        self.cli("say", "--text", "hello")
        self.assertTrue(talos.save_record())
        self.assertEqual(self.git("rev-parse", "talos/record^").stdout.strip(), first)
        self.assertEqual(self.git("rev-parse", "main").stdout.strip(), self.main)
        self.assertEqual(self.git("symbolic-ref", "--short", "HEAD").stdout.strip(), "main")
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")

    def test_restamp_stays_off_the_protected_branch(self):
        self.cli("base", "--worktree")
        subprocess.run([sys.executable, str(REPO / "init.py"), str(self.root), "--force"], capture_output=True, check=True)
        self.assertEqual(self.git("rev-parse", "main").stdout.strip(), self.main)
        work = self.root / ".talos" / "work"
        self.assertEqual(self.git("-C", str(work), "status", "--porcelain").stdout.strip(), "")

    def test_a_move_during_a_phase_stops_for_the_ceo(self):
        self.next()
        import talos
        tips = talos.protected_tips()
        (self.root / "hand.txt").write_text("x\n", encoding="utf-8")
        self.git("add", "hand.txt")
        self.git("commit", "-qm", "hand")
        self.assertEqual(talos.report_moved(tips, "task"), ["main"])
        self.assertIsNone(self.next()[0])
        self.assertEqual(talos.report_moved(talos.protected_tips(), "task"), [])

    def test_hook_refuses_any_ref_change_on_new_git(self):
        hook = self.root / ".git" / "hooks" / "reference-transaction"
        line = f"{self.main} {'0' * 40} refs/heads/main\n".encode()

        def run(text, env):
            return subprocess.run(["sh", str(hook), "prepared"], input=text, cwd=self.root, env=env, capture_output=True).returncode
        ours = dict(self.env, CLAUDECODE="1")
        self.assertEqual(run(line, ours), 1)
        self.assertEqual(run(line.replace(b"refs/heads/main", b"refs/heads/talos/work"), ours), 0)
        self.assertEqual(run(line, self.env), 0, "the developer's own shell")

    def test_only_the_ceo_turns_these_on(self):
        self.assertEqual(self.guard("tools/talos/talos automerge on").returncode, 2)
        self.assertEqual(self.guard("tools/talos/talos notify https://example.com/x").returncode, 2)
        self.assertEqual(self.guard("tools/talos/talos automerge").returncode, 0)


class Adopted(Repo):
    def test_understanding_opens_the_charter_gate(self):
        self.stamp()
        self.assertNotEqual(self.cli("gate", "charter", ok=False).returncode, 0)
        self.cli("log", "understanding.proposed", "--summary", "x")
        self.cli("approve", "understanding", "--quote", "ok")
        self.assertIn("gate open", self.cli("gate", "charter"))


class OneRunner(Repo):
    def test_a_second_runner_leaves(self):
        self.stamp()
        run = self.root / ".talos" / "runner.json"
        run.parent.mkdir(exist_ok=True)
        run.write_text(json.dumps({"pid": 123, "beat": time.time()}), encoding="utf-8")
        p = subprocess.run([sys.executable, str(TALOS / "run.py"), "work"], cwd=self.root, env=self.env, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("already working", p.stdout)
        self.assertTrue(run.exists(), "it's the other runner's file")


class Notify(Repo):
    def test_sends_names_only_and_once(self):
        got = []

        class Sink(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                got.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), Sink)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.stamp()
        self.next()
        import talos
        self.assertEqual(talos.send_notifications(talos.read_ledger(), talos.load_items()), [], "off until the CEO sets it")
        self.cli("notify", f"http://127.0.0.1:{srv.server_port}/t")
        self.cli("log", "charter.proposed", "--summary", "SECRET PLAN DETAILS")
        talos.send_notifications(talos.read_ledger(), talos.load_items())
        talos.send_notifications(talos.read_ledger(), talos.load_items())
        self.assertEqual(len(got), 1)
        self.assertIn("charter gate", got[0])
        self.assertNotIn("SECRET", got[0])


class AutoMerge(Repo):
    def test_only_verified_low_risk_fast_lane(self):
        self.stamp()
        self.next()
        import talos
        items = [{"id": "ITEM-0001", "route": "fast", "risk": "low", "status": "verified"},
                 {"id": "ITEM-0002", "route": "fast", "risk": "medium", "status": "verified"},
                 {"id": "ITEM-0003", "route": "item", "risk": "low", "status": "verified"},
                 {"id": "ITEM-0004", "route": "fast", "risk": "low", "status": "ready"}]
        self.assertEqual(talos.auto_approvals([], {}, items), [])
        done = talos.auto_approvals([], {"automerge": True}, items)
        self.assertEqual([e["ref"] for e in done], ["ITEM-0001"])
        self.assertEqual(talos.auto_approvals(talos.read_ledger(), {"automerge": True}, items), [], "once")


if __name__ == "__main__":
    unittest.main()
