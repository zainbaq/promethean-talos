#!/usr/bin/env python3
"""SessionStart hook: inject a short company status into the session context.

Prints nothing if the project has no company/ record. Never fails the session.
"""
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cwd = Path(payload.get("cwd") or ".")
    except Exception:
        cwd = Path(".")
    cli = cwd / "tools" / "company" / "company.py"
    if not (cwd / "company").exists() or not cli.exists():
        return 0
    try:
        out = subprocess.run([sys.executable, str(cli), "status"], cwd=cwd, capture_output=True, text=True, timeout=20)
        if out.returncode == 0 and out.stdout.strip():
            print("<virtual-company-status>\n" + out.stdout.strip() + "\n</virtual-company-status>\n"
                  "This project runs as a virtual company. Read the CLAUDE.md section 'Virtual Company' before acting. "
                  "If the CEO gives decisions, run /company-review; if they ask where things stand, /company-status.")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
