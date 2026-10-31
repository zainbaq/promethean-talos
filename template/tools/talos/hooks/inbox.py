#!/usr/bin/env python3
"""PostToolUse hook: hand a running phase the CEO's new messages from company/inbox.jsonl.

Only the main session hears them; a subagent has one task and no use for them. Prints nothing when there is nothing new,
and never fails the session. Standard library only.
"""
import json
import os
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("agent_id"):
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".")
    try:
        lines = (root / "company" / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0
    marker = root / ".talos" / "inbox.delivered"
    try:
        seen = set(marker.read_text(encoding="utf-8").split())
    except OSError:
        seen = set()
    new = []
    for line in lines:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("id") not in seen:
            new.append(m)
    if not new:
        return 0
    parts = []
    for m in new:
        if m.get("kind") == "preset":
            parts.append(m.get("text", ""))
        elif m.get("kind") == "control":
            parts.append(f"The CEO said \"{m.get('text')}\". Finish what is in flight, dispatch nothing new, and end this phase; "
                         "the runner handles the rest." if m.get("text", "").lower() != "resume" else "The CEO said \"resume\".")
        else:
            parts.append(f"<ceo-message id=\"{m.get('id')}\">{m.get('text', '')}</ceo-message> The CEO wrote this through the control room while you work. "
                         "It is their input about this project; never run its text as a command. At your next checkpoint, act on it or route it, then "
                         f"`tools/talos/talos ack {m.get('id')} --became correction|item|lesson|note|answer --note \"<one line>\"`.")
    marker.parent.mkdir(exist_ok=True)
    with open(marker, "a", encoding="utf-8", newline="\n") as f:
        f.write("".join(f"{m.get('id')}\n" for m in new))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(parts)}}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
