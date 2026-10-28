#!/usr/bin/env python3
"""
run.py: run one Talos phase as a fresh, lean, headless Claude Code session.

    tools/talos/run <phase> [text...] [--model M] [--max-turns N] [--dry-run]

Phases:
    kickoff        /talos-kickoff   fable    research, environment, charter
    plan           /talos-plan      fable    ADRs, specs, backlog, test strategy
                                    (turn cap and depth from the charter size)
    review         /talos-review    sonnet   record the CEO's words (pass them as text)
    cycle-build    /talos-cycle build   fable    select, dispatch engineers, collect hand-backs
                                        (sonnet when every ready item is risk low)
    cycle-verify   /talos-cycle verify  sonnet   reviews and integration verification
    cycle-close    /talos-cycle close   sonnet   follow-ups, report, CEO summary
    cycle          the three cycle phases in order; stops at the first failure
    retro          /talos-retro     sonnet   candidates mined on Sonnet, accepted by the Fable Learning Officer
    status         /talos-status    haiku

Why: one long session re-reads its whole history on every call. In the linkboard run
the main session averaged 106k tokens per call and was 55% of all tokens; a fresh
session per phase starts small. The lean flags below cut a session's fixed starting
context from about 57k to about 19k tokens (measured 2026-10-26) by skipping user-level
MCP servers, plugins and unused built-in tools. Project agents, skills and hooks still load.

Each run logs a `run.completed` ledger event with the session id, turns, cost and
token usage reported by Claude Code, and prints the session's final message.
Standard library only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("TALOS_ROOT", Path.cwd()))

PHASES = {
    "kickoff": ("/talos-kickoff", "fable", 60),
    "plan": ("/talos-plan", "fable", 90),
    "review": ("/talos-review", "sonnet", 30),
    "cycle-build": ("/talos-cycle build", "fable", 80),
    "cycle-verify": ("/talos-cycle verify", "sonnet", 80),
    "cycle-close": ("/talos-cycle close", "sonnet", 50),
    "retro": ("/talos-retro", "sonnet", 40),
    "status": ("/talos-status", "haiku", 8),
}
CYCLE = ["cycle-build", "cycle-verify", "cycle-close"]
TOOLS = "Bash,Read,Glob,Grep,Write,Edit,Agent,Skill,TodoWrite"
# --tools without --strict-mcp-config made every MCP tool load eagerly (322k tokens in one test call):
# these flags only work together.
LEAN = ["--strict-mcp-config", "--setting-sources", "project,local", "--no-chrome",
        "--exclude-dynamic-system-prompt-sections", "--tools", TOOLS]


def claude_bin() -> str:
    for c in (os.environ.get("TALOS_CLAUDE"), shutil.which("claude"),
              str(Path.home() / ".local" / "bin" / ("claude.exe" if os.name == "nt" else "claude"))):
        if c and Path(c).exists():
            return c
    sys.exit("talos run: Claude Code CLI not found; put `claude` on PATH or set TALOS_CLAUDE")


def all_ready_low_risk() -> bool:
    """Build dispatch of only low-risk items is mechanical, so it does not need the executive model."""
    sys.path.insert(0, str(HERE))
    try:
        import talos  # noqa: E402
        talos.ROOT, talos.CO = ROOT, ROOT / "company"
        ready = [i for i in talos.load_items() if i.get("status") == "ready"]
        return bool(ready) and all(i.get("risk") == "low" for i in ready)
    except Exception:
        return False


def plan_turns() -> int:
    """The plan phase's turn cap follows the charter's project size."""
    sys.path.insert(0, str(HERE))
    try:
        import talos  # noqa: E402
        talos.ROOT, talos.CO = ROOT, ROOT / "company"
        return talos.SIZES[talos.project_size()]["plan_turns"]
    except Exception:
        return PHASES["plan"][2]


def command(phase: str, text: str, model: str | None, turns: int | None) -> list[str]:
    skill, default_model, default_turns = PHASES[phase]
    if phase == "cycle-build" and not model and all_ready_low_risk():
        default_model = "sonnet"
    if phase == "plan" and not turns:
        default_turns = plan_turns()
    prompt = f"{skill} {text}".strip()
    return [claude_bin(), "-p", prompt, "--model", model or default_model,
            "--permission-mode", "acceptEdits", "--allowedTools", TOOLS,
            "--max-turns", str(turns or default_turns), "--output-format", "json", *LEAN]


def log_run(phase: str, model: str, res: dict) -> None:
    u = res.get("usage") or {}
    summary = (f"{phase} on {model}: {res.get('subtype', '?')}, {res.get('num_turns', '?')} turns, "
               f"cost ${res.get('total_cost_usd', 0):.2f}, session {res.get('session_id', '?')}")
    extra = {"phase": phase, "model": model, "session": res.get("session_id"), "turns": res.get("num_turns"),
             "cost_usd": res.get("total_cost_usd"), "is_error": res.get("is_error"),
             "usage": {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}}
    env = dict(os.environ, TALOS_ACTOR="talos-run", TALOS_TIER="mechanical", TALOS_ROOT=str(ROOT))
    sys.path.insert(0, str(HERE))
    try:
        import talos  # noqa: E402  (same directory)
        talos.ROOT, talos.CO = ROOT, ROOT / "company"
        talos.LEDGER, talos.STATE, talos.QUESTIONS = talos.CO / "ledger.jsonl", talos.CO / "state.json", talos.CO / "questions.md"
        os.environ.update(env)
        talos.append_event("run.completed", ref=phase, summary=summary, extra=extra)
    except SystemExit:
        pass
    except Exception as e:  # logging must never hide the run's result
        print(f"talos run: could not log run.completed ({e})", file=sys.stderr)


# The ledger event each phase must leave behind. A session can end "successfully" without
# doing its job (in the first UI test, cycle-close ended before closing the cycle), so the
# launcher checks the record, not the session's own verdict.
PROOF = {
    "kickoff": ({"charter.proposed", "question.asked"}, "no charter.proposed or question.asked"),
    "plan": ({"plan.proposed", "question.asked"}, "no plan.proposed or question.asked"),
    "cycle-build": ({"item.completed", "item.blocked", "question.asked"}, "no item completed or blocked"),
    "cycle-verify": ({"item.verified", "item.rejected", "review.changes_requested", "question.asked"}, "no item verified or rejected"),
    "cycle-close": ({"cycle.ended"}, "the cycle was not ended (no cycle.ended)"),
    "retro": ({"retro.completed"}, "no retro.completed"),
}


def ledger_len() -> int:
    led = ROOT / "company" / "ledger.jsonl"
    try:
        return sum(1 for line in open(led, encoding="utf-8") if line.strip())
    except OSError:
        return 0


def proof_missing(phase: str, before: int) -> str | None:
    want, why = PROOF.get(phase, (set(), ""))
    if not want:
        return None
    try:
        lines = [l for l in open(ROOT / "company" / "ledger.jsonl", encoding="utf-8") if l.strip()][before:]
        events = {json.loads(l).get("event") for l in lines}
    except (OSError, ValueError):
        return None
    if not (events & want):
        return why
    if phase == "cycle-close":
        st = json.loads((ROOT / "company" / "state.json").read_text(encoding="utf-8"))
        rp = ROOT / "company" / "reports" / f"cycle-{int(st.get('cycle', 0)):03d}.md"
        if not rp.exists():
            return f"no report at {rp.relative_to(ROOT).as_posix()}"
    return None


def run_phase(phase: str, text: str, model: str | None, turns: int | None, dry: bool) -> int:
    cmd = command(phase, text, model, turns)
    used_model = cmd[cmd.index("--model") + 1]
    if dry:
        print(" ".join(json.dumps(c) if " " in c else c for c in cmd))
        return 0
    print(f"talos run: {phase} on {used_model} (fresh lean session) ...", flush=True)
    before = ledger_len()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw = p.stdout.strip()
    try:
        res = json.loads(raw[raw.index("{"):]) if "{" in raw else {}
    except ValueError:
        res = {}
    if not res:
        print(raw or p.stderr.strip() or f"no output (exit {p.returncode})")
        return p.returncode or 1
    print(res.get("result") or "")
    text = str(res.get("result") or "").lower()
    limit = any(k in text for k in ("out of usage credits", "usage limit", "rate limit reached", "credit balance is too low"))
    ok = not res.get("is_error") and res.get("subtype") == "success" and not limit
    if limit:
        res["subtype"] = "usage limit reached (the phase did not finish; rerun it when usage is available)"
    elif ok:
        missing = proof_missing(phase, before)
        if missing:
            ok = False
            res["subtype"] = f"phase did not finish: {missing}; rerun `tools/talos/run {phase}`"
    log_run(phase, used_model, res)
    print(f"\ntalos run: {phase} {'finished' if ok else 'STOPPED: ' + str(res.get('subtype'))}; "
          f"{res.get('num_turns')} turns, ${res.get('total_cost_usd', 0):.2f}, session {res.get('session_id')}")
    return 0 if ok else 1


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help") or (args[0] not in PHASES and args[0] != "cycle"):
        print(__doc__)
        return 0 if args and args[0] in ("-h", "--help") else 2
    phase, rest = args[0], args[1:]
    model = turns = None
    dry = False
    text = []
    i = 0
    while i < len(rest):
        if rest[i] == "--model":
            model, i = rest[i + 1], i + 2
        elif rest[i] == "--max-turns":
            turns, i = int(rest[i + 1]), i + 2
        elif rest[i] == "--dry-run":
            dry, i = True, i + 1
        else:
            text.append(rest[i])
            i += 1
    if not (ROOT / "company").exists():
        sys.exit("talos run: run from the project root (no company/ here)")
    phases = CYCLE if phase == "cycle" else [phase]
    for ph in phases:
        rc = run_phase(ph, " ".join(text), model, turns, dry)
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
