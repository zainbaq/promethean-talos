#!/usr/bin/env python3
"""PreToolUse guard for the Talos template.

Blocks (exit 2 with a reason on stderr):
  - direct edits to company/ledger.jsonl or company/state.json (use the talos CLI)
  - shell redirection into those files
  - destructive git: force push, hard reset, history rewrite, deleting main/master
  - rm -rf of / or the home directory
  - killing a process the company did not start (only PIDs in .talos/pids; never by name or port)
  - changing a branch the CEO protected (`talos protect`), or lifting that rule
  - running a test suite directly when the survey found real hosts in the tests (use `talos test`)

Everything else is allowed (exit 0, no output). Standard library only.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROTECTED = ("company/ledger.jsonl", "company/state.json")

BASH_DENY = [
    (r"git\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b)", "force push is not allowed; open a PR instead"),
    (r"git\s+reset\s+--hard", "hard reset is not allowed; use a new branch or revert"),
    (r"git\s+(rebase\s+-i|filter-branch|filter-repo)", "history rewriting is not allowed"),
    (r"git\s+branch\s+-[dD]\s+(main|master)\b", "deleting the main branch is not allowed"),
    (r"git\s+push\s+\S+\s+--delete\s+(main|master)\b", "deleting the main branch is not allowed"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\$HOME)(\s|$)", "recursive delete of root or home is not allowed"),
    (r">{1,2}\s*\S*company/(ledger\.jsonl|state\.json)", "write to the company record through the talos CLI, not shell redirection"),
]


# A kill verb where a command starts: not the word inside a commit message or a grep.
KILL_AT = (r"(?:^|[;&|(\n]|\bsudo\s|\bcmd(?:\.exe)?\s+/c\s+[\"']?|-Command\s+[\"']?|\bxargs\s+(?:-\S+\s+)*)\s*"
           r"(taskkill|tskill|kill|pkill|killall|stop-process|spps|fuser|wmic)(?:\.exe)?(?=\s|$)([^;&|\n]*)")
BY_NAME = {"pkill", "killall", "fuser", "wmic", "tskill"}
HOW = ("the company only kills processes it started: record each one with `tools/talos/talos pid add <pid>` when you start it, "
       "then kill that PID. Never by name or port: killing by port took out about nine unrelated processes once")


def kill_problem(cmd: str, payload: dict) -> str | None:
    """Why this command may not run, or None. An exact PID list is the only form that can be checked."""
    for m in re.finditer(KILL_AT, cmd, re.I | re.M):
        verb, rest = m.group(1).lower(), m.group(2)
        if verb == "wmic" and not re.search(r"\bprocess\b.*\b(delete|terminate)\b", rest, re.I):
            continue
        if verb == "fuser" and not re.search(r"(^|\s)-\w*k", rest):
            continue
        if verb in BY_NAME or re.search(r"[/-](im|name|processname)\b|[$`%*:]", rest, re.I):
            return f"{verb} by name, port or computed value is not allowed; {HOW}"
        rest = re.sub(r"(^|\s)(-s\s+\S+|-\d+|-[A-Za-z]+)(?=\s|$)", " ", rest) if verb == "kill" else rest
        pids = re.findall(r"\b\d+\b", rest)
        if not pids:
            return f"{verb} without an explicit PID is not allowed; {HOW}"
        base = project_base(payload)
        try:
            ours = set((base / ".talos" / "pids").read_text(encoding="utf-8").split())
        except OSError:
            ours = set()
        strangers = [p for p in pids if p not in ours]
        if strangers:
            return f"PID {', '.join(strangers)} is not one the company started; {HOW}"
    return None


AT_START = r"(?:^|[;&|(\n]|\bsudo\s)\s*"
GIT_WRITES = re.compile(AT_START + r"git\s+((?:-C\s+(\"[^\"]+\"|\S+)\s+)?)(?:-c\s+\S+\s+)*(commit|merge|rebase|cherry-pick|revert|pull|am|reset)\b", re.M)
CD = re.compile(AT_START + r"cd\s+(\"[^\"]+\"|\S+)", re.M)
SUITES = re.compile(AT_START + r"(?:\S*python\S*\s+-m\s+pytest|(?:\S*[/\\])?pytest|npm\s+(?:run\s+)?test|yarn\s+test|pnpm\s+test|npx\s+(?:jest|vitest)|go\s+test|cargo\s+test|make\s+test|tox)\b", re.M)


def project_base(payload: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")


def protected_problem(cmd: str, payload: dict) -> str | None:
    """Why this changes a protected branch, or None. The named forms are always refused; the rest depend on what the directory has checked out."""
    if re.search(r"\btalos(\.py)?\s+protect\b.*--off", cmd):
        return "only the CEO lifts a branch rule"
    try:
        names = json.loads((project_base(payload) / "company" / "state.json").read_text(encoding="utf-8")).get("protected") or []
    except (OSError, ValueError):
        return None
    if not names:
        return None
    alt = "|".join(re.escape(n) for n in names)
    named = (rf"git\s+push\b.*(\s|:|refs/heads/)({alt})(\s|$)", rf"git\s+branch\s+(-f|--force|-M|-m|-D|-d)\b.*\b({alt})(\s|$)",
             rf"git\s+update-ref\s+\S*\b({alt})(\s|$)", rf"git\s+(checkout\s+-B|switch\s+-C)\s+({alt})(\s|$)", rf"git\s+fetch\b.*:\S*\b({alt})(\s|$)")
    if any(re.search(p, cmd, re.M) for p in named) or (re.search(r"\bgit\s", cmd) and "--no-verify" in cmd):
        return f"{', '.join(names)} is protected: the company never changes it. Work on a branch from `tools/talos/talos base`"
    for m in GIT_WRITES.finditer(cmd):
        where = (m.group(2) or "").strip('"')
        if not where:
            cds = [c for c in CD.finditer(cmd[:m.start()])]
            where = cds[-1].group(1).strip('"') if cds else ""
        at = Path(where) if where and Path(where).is_absolute() else Path(payload.get("cwd") or ".") / where
        try:
            head = subprocess.run(["git", "-C", str(at), "symbolic-ref", "--short", "-q", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if head in names:
            return f"this checkout is on {head}, which is protected: the company never changes it. Work on a branch from `tools/talos/talos base`"
    return None


def suite_problem(cmd: str, payload: dict) -> str | None:
    """A suite that names real hosts can reach them. `talos test` blocks the network and strips credentials."""
    if not SUITES.search(cmd):
        return None
    try:
        inv = json.loads((project_base(payload) / "company" / "knowledge" / "inventory.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    hosts = [h.get("host") for h in inv.get("hosts_in_tests") or []]
    if not hosts:
        return None
    return (f"this project's tests name real hosts ({', '.join(hosts[:3])}), and a suite run in the open can reach them. "
            "Run `tools/talos/talos test --where <checkout>` from the main checkout: it blocks the network and strips credentials")


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        # Malformed payload: fall back to a raw-text check for the one thing we must never allow.
        if re.search(r"company[\\/]+(ledger\.jsonl|state\.json)", raw) and re.search(r'"tool_name"\s*:\s*"(Edit|Write|MultiEdit|NotebookEdit)"', raw):
            print("talos guard: the company ledger/state files are owned by the talos CLI.", file=sys.stderr)
            return 2
        return 0
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path", "")).replace("\\", "/")
        if "/.git/hooks/" in path or path.endswith("/.git/talos-protected"):
            print("talos guard: the repo's git hooks are not the company's to edit.", file=sys.stderr)
            return 2
        for p in PROTECTED:
            if path.endswith(p):
                print(f"talos guard: {p} is append-only and owned by the talos CLI. "
                      f"Use `tools/talos/talos log|item|cycle ...` instead.", file=sys.stderr)
                return 2
        return 0

    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        problem = kill_problem(cmd, payload) or protected_problem(cmd, payload) or suite_problem(cmd, payload)
        if problem:
            print(f"talos guard: {problem}", file=sys.stderr)
            return 2
        for pattern, reason in BASH_DENY:
            if re.search(pattern, cmd):
                print(f"talos guard: {reason}", file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
