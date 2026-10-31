"""The control room's writes. Each maps to one Talos CLI command with validated arguments, run without a shell.

This module only records: a press never starts a phase or runs Claude (`talos work` acts on what the record says). Chat text
goes to the CLI as data. An argument that starts with a dash stays an argument, because each is passed as --name=value or
after `--`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

TALOS = Path(__file__).resolve().parent.parent / "talos.py"
GATES = ("understanding", "charter", "plan", "design", "release", "launch")
PRESETS = ("lite", "medium", "heavy")
MAX_TEXT = 4000
ITEM_RE = re.compile(r"^ITEM-\d{4}$")
QUESTION_RE = re.compile(r"^Q-\d{4}$")


class Invalid(ValueError):
    """The request is not one the control room accepts."""


def _text(data: dict, name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f"{name} is required")
    if len(value) > MAX_TEXT or "\x00" in value:
        raise Invalid(f"{name} is too long or malformed")
    return value.strip()


def _gate(data: dict) -> list[str]:
    gate, ref = data.get("gate"), data.get("ref")
    if gate not in GATES:
        raise Invalid("unknown gate")
    if gate == "release":
        if not isinstance(ref, str) or not ITEM_RE.match(ref):
            raise Invalid("a release needs an item id")
        return [gate, f"--ref={ref}"]
    if ref is not None:
        raise Invalid("only a release takes a ref")
    return [gate]


def command(action: str, data: dict) -> list[str]:
    """The CLI arguments for one control-room action. Invalid when the action or its data is not acceptable."""
    if action == "approve":
        return ["approve", *_gate(data), "--quote=Approved in the control room"]
    if action == "reject":
        return ["reject", *_gate(data), f"--reason={_text(data, 'reason')}"]
    if action == "answer":
        qid = data.get("qid")
        if not isinstance(qid, str) or not QUESTION_RE.match(qid):
            raise Invalid("unknown question")
        return ["answer", "--by=ceo", "--unblock", qid, "--", _text(data, "text")]
    if action == "say":
        return ["say", f"--text={_text(data, 'text')}"]
    if action == "preset":
        if data.get("name") not in PRESETS:
            raise Invalid("unknown preset")
        return ["preset", data["name"], "--actor=ceo", "--tier=ceo"]
    raise Invalid("unknown action")


def run(project_root: Path, action: str, data: dict) -> tuple[bool, str]:
    """(ok, what the CLI said). A closed gate or a bad state comes back as a message, not an exception."""
    args = command(action, data)
    env = dict(os.environ, TALOS_ROOT=str(project_root), TALOS_ACTOR="control-room", TALOS_TIER="ceo", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, str(TALOS), *args], cwd=project_root, env=env, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=30)
    said = (p.stdout if p.returncode == 0 else p.stderr or p.stdout).strip()
    return p.returncode == 0, said[:500]
