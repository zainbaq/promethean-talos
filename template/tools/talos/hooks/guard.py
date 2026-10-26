#!/usr/bin/env python3
"""PreToolUse guard for the Talos template.

Blocks (exit 2 with a reason on stderr):
  - direct edits to company/ledger.jsonl or company/state.json (use the talos CLI)
  - shell redirection into those files
  - destructive git: force push, hard reset, history rewrite, deleting main/master
  - rm -rf of / or the home directory

Everything else is allowed (exit 0, no output). Standard library only.
"""
import json
import re
import sys

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

    if tool == "Bash":
        cmd = str(inp.get("command", ""))
        for pattern, reason in BASH_DENY:
            if re.search(pattern, cmd):
                print(f"talos guard: {reason}", file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
