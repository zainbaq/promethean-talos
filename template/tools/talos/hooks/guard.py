#!/usr/bin/env python3
"""PreToolUse guard for the Talos template.

Blocks (exit 2 with a reason on stderr):
  - direct edits to company/ledger.jsonl or company/state.json (use the talos CLI)
  - shell redirection into those files
  - destructive git: force push, hard reset, history rewrite, deleting main/master
  - rm -rf of / or the home directory
  - killing a process the company did not start (only PIDs in .talos/pids; never by name or port)

Everything else is allowed (exit 0, no output). Standard library only.
"""
import json
import os
import re
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
        base = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
        try:
            ours = set((base / ".talos" / "pids").read_text(encoding="utf-8").split())
        except OSError:
            ours = set()
        strangers = [p for p in pids if p not in ours]
        if strangers:
            return f"PID {', '.join(strangers)} is not one the company started; {HOW}"
    return None


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
        for p in PROTECTED:
            if path.endswith(p):
                print(f"talos guard: {p} is append-only and owned by the talos CLI. "
                      f"Use `tools/talos/talos log|item|cycle ...` instead.", file=sys.stderr)
                return 2
        return 0

    if tool in ("Bash", "PowerShell"):
        cmd = str(inp.get("command", ""))
        problem = kill_problem(cmd, payload)
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
