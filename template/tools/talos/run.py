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
    resume         continue the last phase that stopped (the rest of the cycle too, if it was a cycle phase)

Why: one long session re-reads its whole history on every call. In the linkboard run
the main session averaged 106k tokens per call and was 55% of all tokens; a fresh
session per phase starts small. The lean flags below cut a session's fixed starting
context from about 57k to about 19k tokens (measured 2026-10-26) by skipping user-level
MCP servers, plugins and unused built-in tools. Project agents, skills and hooks still load.

Each run logs a `run.completed` ledger event with the session id, turns, cost and
token usage reported by Claude Code, and prints the session's final message. A run that
did not finish also logs `run.stopped` with the reason, and any uncommitted worktree work
is saved to a wip/ branch.
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


def load_talos():
    sys.path.insert(0, str(HERE))
    import talos  # noqa: E402  (same directory)
    talos.ROOT, talos.CO = ROOT, ROOT / "company"
    talos.LEDGER, talos.STATE, talos.QUESTIONS = talos.CO / "ledger.jsonl", talos.CO / "state.json", talos.CO / "questions.md"
    return talos


def log_event(event: str, phase: str, summary: str, extra: dict | None = None) -> None:
    os.environ.update(TALOS_ACTOR="talos-run", TALOS_TIER="mechanical", TALOS_ROOT=str(ROOT))
    try:
        load_talos().append_event(event, ref=phase, summary=summary, extra=extra)
    except SystemExit:
        pass
    except Exception as e:  # logging must never hide the run's result
        print(f"talos run: could not log {event} ({e})", file=sys.stderr)


def log_run(phase: str, model: str, res: dict) -> None:
    u = res.get("usage") or {}
    summary = (f"{phase} on {model}: {res.get('subtype', '?')}, {res.get('num_turns', '?')} turns, "
               f"cost ${res.get('total_cost_usd', 0):.2f}, session {res.get('session_id', '?')}")
    extra = {"phase": phase, "model": model, "session": res.get("session_id"), "turns": res.get("num_turns"),
             "cost_usd": res.get("total_cost_usd"), "is_error": res.get("is_error"),
             "usage": {k: u.get(k) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}}
    log_event("run.completed", phase, summary, extra)


LIMIT_WORDS = ("out of usage credits", "usage limit", "rate limit reached", "credit balance is too low", "hit your limit")


def stop_reason(res: dict) -> str | None:
    """Why the session did not finish, in words; None when it says it did. Never reports "success" as a stop."""
    text = str(res.get("result") or "")
    if any(k in text.lower() for k in LIMIT_WORDS):
        return "usage limit reached (the phase did not finish; `tools/talos/run resume` continues it when usage is available)"
    subtype = res.get("subtype")
    if subtype == "error_max_turns":
        return f"turn cap reached after {res.get('num_turns', '?')} turns; `tools/talos/run resume` continues it"
    if res.get("is_error") or subtype != "success":
        first = text.strip().splitlines()[0][:200] if text.strip() else ""
        said = first or (subtype if subtype and subtype != "success" else "no reason given")
        return f"the session ended with an error: {said}"
    return None


def git(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")


def save_worktrees() -> list[str]:
    """Commit each dirty worktree's work to a wip/ branch, leaving the worktree exactly as it was. Deletes nothing."""
    listed = git("worktree", "list", "--porcelain")
    paths = [l[len("worktree "):] for l in listed.stdout.splitlines() if l.startswith("worktree ")][1:]
    saved = []
    for path in paths:
        if not git("status", "--porcelain", cwd=path).stdout.strip():
            continue
        name = "wip/" + Path(path).name
        git("add", "-A", cwd=path)
        tree = git("write-tree", cwd=path).stdout.strip()
        head = git("rev-parse", "HEAD", cwd=path).stdout.strip()
        commit = git("commit-tree", tree, "-p", head, "-m", "wip: saved by the launcher when a phase stopped", cwd=path).stdout.strip()
        git("reset", "-q", cwd=path)  # unstage only; the working files stay
        if commit and not git("branch", "-f", name, commit, cwd=path).returncode:
            saved.append(f"{name} ({path})")
        else:
            print(f"talos run: could not save the work in {path}; it is still there, uncommitted", file=sys.stderr)
    return saved


# The ledger event each phase must leave behind. A session can end "successfully" without
# doing its job (in the first UI test, cycle-close ended before closing the cycle), so the
# launcher checks the record, not the session's own verdict.
PROOF = {
    "kickoff": ({"charter.proposed", "question.asked"}, "no charter.proposed or question.asked"),
    "plan": ({"plan.proposed", "question.asked"}, "no plan.proposed or question.asked"),
    "cycle-build": ({"item.completed", "item.blocked", "question.asked"}, "no item completed or blocked"),
    "cycle-verify": ({"item.verified", "verify.blocked"}, "no item verified and no verify.blocked"),
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


def close_refused() -> str | None:
    """Close reports on what verify proved, so it does not run when verify proved nothing."""
    try:
        cycle = json.loads((ROOT / "company" / "state.json").read_text(encoding="utf-8")).get("cycle", 0)
        events = [json.loads(l) for l in open(ROOT / "company" / "ledger.jsonl", encoding="utf-8") if l.strip()]
    except (OSError, ValueError):
        return None
    if any(e.get("cycle") == cycle and e.get("event") in ("item.verified", "item.blocked", "verify.blocked") for e in events):
        return None
    return f"nothing is verified or blocked in cycle {cycle}; run `tools/talos/run cycle-verify` first"


def stopped(phase: str, reason: str) -> int:
    saved = save_worktrees()
    note = f"; uncommitted work saved to {', '.join(saved)}" if saved else ""
    log_event("run.stopped", phase, reason + note)
    print(f"\ntalos run: {phase} STOPPED: {reason}{note}")
    return 1


def run_phase(phase: str, text: str, model: str | None, turns: int | None, dry: bool) -> int:
    if phase == "cycle-close" and not dry:
        refused = close_refused()
        if refused:
            return stopped(phase, refused)
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
        said = raw or p.stderr.strip() or f"no output (exit {p.returncode})"
        print(said)
        return stopped(phase, f"the session gave no result: {said[:200]}")
    print(res.get("result") or "")
    reason = stop_reason(res)
    if not reason:
        missing = proof_missing(phase, before)
        if missing:
            reason = f"phase did not finish: {missing}; `tools/talos/run resume` continues it"
    log_run(phase, used_model, res)
    print(f"\ntalos run: {phase} {res.get('num_turns')} turns, ${res.get('total_cost_usd', 0):.2f}, session {res.get('session_id')}")
    if reason:
        return stopped(phase, reason)
    print(f"talos run: {phase} finished")
    return 0


def resume_plan(extra: str) -> tuple[list[str], str] | None:
    """(phases to run, text for the first) for the last stopped phase; None when nothing is stopped."""
    stop = load_talos().pending_stop()
    if not stop:
        return None
    phase = stop["ref"]
    saved = save_worktrees()
    wip = [l.strip(" *+") for l in git("branch", "--list", "wip/*").stdout.splitlines()]
    trees = [l[len("worktree "):] for l in git("worktree", "list", "--porcelain").stdout.splitlines() if l.startswith("worktree ")][1:]
    note = (f"Resume: an earlier run of this phase stopped ({stop.get('summary', '')}). Do not redo finished work: "
            "read company/handbacks/ and `talos status --brief`, and pick up only what has no hand-back. "
            f"Worktrees still there: {', '.join(trees) or 'none'}. Work saved on branches: {', '.join(wip) or 'none'}. {extra}").strip()
    if saved:
        print(f"talos run: saved uncommitted work to {', '.join(saved)}")
    return (CYCLE[CYCLE.index(phase):] if phase in CYCLE else [phase]), note


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help") or (args[0] not in PHASES and args[0] not in ("cycle", "resume")):
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
    words = " ".join(text)
    if phase == "resume":
        plan = resume_plan(words)
        if plan is None:
            print("talos run: nothing to resume; no phase is stopped")
            return 0
        phases, words = plan
    else:
        phases = CYCLE if phase == "cycle" else [phase]
    for i, ph in enumerate(phases):
        rc = run_phase(ph, words if i == 0 or phase != "resume" else "", model, turns, dry)
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
