#!/usr/bin/env python3
"""Stop hook: remind the session to log to the company record when files changed
but nothing was logged recently. Non-blocking; emits a systemMessage only.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cwd = Path(payload.get("cwd") or ".")
    except Exception:
        return 0
    ledger = cwd / "company" / "ledger.jsonl"
    if not ledger.exists():
        return 0
    try:
        st = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, timeout=10)
        changed = [l for l in st.stdout.splitlines() if l.strip() and " company/" not in l and not l[3:].startswith("company/")]
    except Exception:
        return 0
    if not changed:
        return 0
    last_ts = None
    try:
        lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            last_ts = datetime.strptime(json.loads(lines[-1])["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    stale = last_ts is None or datetime.now(timezone.utc) - last_ts > timedelta(minutes=30)
    if stale:
        print(json.dumps({"systemMessage": f"promethean-talos: {len(changed)} file(s) changed outside company/ and nothing was logged to the record in the last 30 minutes. If this was company work, log it (`tools/talos/talos log ...` or `item set`)."}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
