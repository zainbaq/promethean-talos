"""Activity and spend blocks of the snapshot (ADR-0003 points 3 to 5, ADR-0007).

Standard library only, plus tools/talos/usage.py loaded by path as the one transcript reader.
Read-only: nothing is opened for writing, and nothing outside the record handed in by the
caller, the transcript folders and usage.py is read. Fails soft: callers get an
"unavailable" block with a reason, never an exception.
"""
from __future__ import annotations

import importlib.util
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

WINDOW_SECONDS = 120   # active: wrote within the last 120 s
RECENT_SECONDS = 300   # recent: wrote within the last 300 s
TAIL_BYTES = 64 * 1024
# Launcher sessions (tools/talos/run.py) start with a slash command. Claude Code records it either literally
# ("/talos-cycle close ...") or rendered as three lines: <command-message>talos-cycle</command-message>,
# <command-name>/talos-cycle</command-name>, <command-args>close ...</command-args>. Both give one phase name (ADR-0009).
LITERAL_RE = re.compile(r"^/talos-(kickoff|plan|review|retro|status|cycle)\b(?:\s+(build|verify|close)\b)?")
LAUNCHER_RE = re.compile(r"<command-name>/talos-(kickoff|plan|review|retro|status|cycle)</command-name>\s*"
                         r"(?:<command-args>\s*(build|verify|close)\b)?")
# Only these roles are dispatched for one backlog item, so only their transcripts name the item they work on
# (ADR-0010). Every other role (executives, reviewers, librarian, main session) quotes item ids in passing.
ITEM_ROLES = frozenset({"engineer", "ui-engineer", "test-engineer", "design-qa", "research-analyst",
                        "ux-designer", "devops-engineer", "technical-writer"})
ITEM_FALLBACK_RE = re.compile(r"\bITEM-\d{4}\b")
WORKTREE_MARKERS = ("--claude-worktrees-", "-wt-")
USAGE_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


class _Unavailable(Exception):
    pass


def load_usage(talos_dir: str | None = None):
    """Return (module, None) or (None, reason)."""
    here = Path(__file__).resolve()
    candidates = []
    if talos_dir:
        candidates.append(Path(talos_dir) / "usage.py")
    candidates.append(here.parent / "usage.py")
    candidates.append(here.parents[1] / "usage.py")  # stamped: tools/talos/viz/ next to tools/talos/usage.py
    candidates.append(here.parents[1] / "tools" / "talos" / "usage.py")
    for path in candidates:
        if path.is_file():
            try:
                spec = importlib.util.spec_from_file_location("talos_usage", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod, None
            except Exception as e:
                return None, f"usage.py could not be loaded: {type(e).__name__}: {e}"
    return None, "usage.py not found (looked in " + ", ".join(str(c.parent) for c in candidates) + ")"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _posix(p) -> str:
    return str(p).replace("\\", "/")


def _last_run(ledger):
    for e in reversed(ledger or []):
        if isinstance(e, dict) and e.get("event") == "run.completed":
            return {"phase": e.get("phase"), "model": e.get("model"), "ts": e.get("ts"),
                    "event_id": e.get("id"), "cost_usd": e.get("cost_usd"), "turns": e.get("turns")}
    return None


def _unavailable(reason, ledger, checked_at):
    return {
        "status": "unavailable", "reason": reason, "checked_at": checked_at,
        "window_seconds": WINDOW_SECONDS, "recent_seconds": RECENT_SECONDS,
        "transcript_dirs": [],
        "phase": {"status": "unknown", "name": None, "session": None, "since": None},
        "agents": [], "last_run": _last_run(ledger),
    }


def _tail_item(path: Path):
    """Last ITEM-nnnn in the final 64 KB of the file, scanned backwards line by line (raw text)."""
    size = path.stat().st_size
    if size == 0:
        return None
    with open(path, "rb") as f:
        start = max(0, size - TAIL_BYTES)
        f.seek(start)
        data = f.read()
    lines = data.decode("utf-8", errors="replace").splitlines()
    if start > 0 and lines:
        lines = lines[1:]  # first line is cut mid-way
    for line in reversed(lines):
        found = ITEM_FALLBACK_RE.findall(line)
        if found:
            return found[-1]
    return None


def _item(usage, path: Path):
    try:
        found = _tail_item(path)
    except OSError:
        found = None
    if found:
        return found
    first = usage._item_of(usage._first_prompt(path))
    return first if ITEM_FALLBACK_RE.fullmatch(first or "") else None


def _agent_type(meta: Path) -> str:
    """'?' when the meta file is missing; _Unavailable when it is there but malformed."""
    try:
        text = meta.read_text(encoding="utf-8")
    except OSError:
        return "?"
    try:
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError("not an object")
    except ValueError:
        raise _Unavailable("malformed .meta.json")
    return d.get("agentType") or "?"


def phase_name(prompt) -> str | None:
    """kickoff|plan|review|cycle-build|cycle-verify|cycle-close|retro|status from a session's first prompt, else None."""
    prompt = prompt or ""
    m = LAUNCHER_RE.search(prompt) or LITERAL_RE.match(prompt)
    if not m:
        return None
    cmd, arg = m.group(1), m.group(2)
    if cmd == "cycle":
        return f"cycle-{arg}" if arg else None
    return cmd


def _finished_sessions(ledger) -> set:
    """Session ids the launcher has already closed with a run.completed event (ADR-0009 point 1)."""
    return {e.get("session") for e in (ledger or [])
            if isinstance(e, dict) and e.get("event") == "run.completed" and isinstance(e.get("session"), str)}


def _main_phase(usage, path: Path):
    name = phase_name(usage._first_prompt(path))
    since = None
    try:
        with open(path, "rb") as f:
            for raw in f:
                try:
                    d = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("type") == "user":
                    ts = (d.get("timestamp") or "")[:19]
                    since = (ts + "Z") if ts else None
                    break
    except OSError:
        pass
    return name, since


def derive(project_root, record_dir, ledger, cycle, override=None, *, talos_dir=None) -> dict:
    now = time.time()
    checked_at = _iso(now)
    try:
        usage, why = load_usage(talos_dir)
        if usage is None:
            return _unavailable(why, ledger, checked_at)
        dirs = usage.transcript_dirs(project_root, override)
        if not dirs:
            where = override or usage.projects_dir()
            return _unavailable(f"no Claude Code transcripts for this project yet (looked in {_posix(where)})",
                                ledger, checked_at)
        agents, live = [], {}  # live: unfinished launcher sessions -> (newest write of any of their transcripts, main path)
        finished = _finished_sessions(ledger)
        for d in dirs:
            worktree = any(m in d.name.lower() for m in WORKTREE_MARKERS)
            for main in sorted(d.glob("*.jsonl")):
                files = [(main, usage.MAIN)] + [
                    (s, None) for s in sorted((d / main.stem / "subagents").glob("agent-*.jsonl"))]
                for path, role in files:
                    try:
                        mtime = path.stat().st_mtime
                    except OSError:
                        continue
                    age = now - mtime
                    if age >= RECENT_SECONDS:
                        continue
                    if role is None:
                        role = _agent_type(path.with_suffix(".meta.json"))
                        item = _item(usage, path) if role in ITEM_ROLES else None
                    else:
                        item = None
                    entry = {
                        "role": role,
                        "state": "active" if age < WINDOW_SECONDS else "recent",
                        "item": item, "last_write_at": _iso(mtime), "seconds_ago": max(0, int(age)),
                        "session": main.stem, "transcript": path.name, "worktree": worktree,
                    }
                    agents.append((mtime, entry))
                    if entry["state"] == "active" and main.stem not in finished:
                        if main.stem not in live or mtime > live[main.stem][0]:
                            live[main.stem] = (mtime, main)
        agents.sort(key=lambda t: -t[0])
        agents = [e for _, e in agents]
        phase = {"status": "idle", "name": None, "session": None, "since": None}
        for session, (_, path) in sorted(live.items(), key=lambda kv: -kv[1][0]):
            name, since = _main_phase(usage, path)
            if name:  # running only with a named phase; a live session without one is not a run (ADR-0009)
                phase = {"status": "running", "name": name, "session": session, "since": since}
                break
        return {
            "status": "active" if any(a["state"] == "active" for a in agents) else "idle",
            "reason": None, "checked_at": checked_at,
            "window_seconds": WINDOW_SECONDS, "recent_seconds": RECENT_SECONDS,
            "transcript_dirs": [_posix(d) for d in dirs],
            "phase": phase, "agents": agents, "last_run": _last_run(ledger),
        }
    except _Unavailable as e:
        return _unavailable(f"transcripts unreadable: {e}", ledger, checked_at)
    except Exception as e:
        return _unavailable(f"activity unavailable: {type(e).__name__}: {e}", ledger, checked_at)


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _events_spend(ledger, cycle):
    runs = [e for e in (ledger or []) if isinstance(e, dict) and e.get("event") == "run.completed"
            and e.get("cycle") == cycle]
    out = {"runs": len(runs), "cost_usd": 0.0, "tokens": 0}
    out.update({f: 0 for f in USAGE_FIELDS})
    rows = {}
    for e in runs:
        u = e.get("usage") if isinstance(e.get("usage"), dict) else {}
        toks = 0
        for f in USAGE_FIELDS:
            v = int(_num(u.get(f)))
            out[f] += v
            toks += v
        out["tokens"] += toks
        cost = float(_num(e.get("cost_usd")))
        out["cost_usd"] += cost
        r = rows.setdefault((e.get("phase"), e.get("model")),
                            {"phase": e.get("phase"), "model": e.get("model"), "runs": 0,
                             "cost_usd": 0.0, "tokens": 0, "turns": 0})
        r["runs"] += 1
        r["cost_usd"] += cost
        r["tokens"] += toks
        r["turns"] += int(_num(e.get("turns")))
    out["cost_usd"] = round(out["cost_usd"], 6)
    by_phase = sorted(rows.values(), key=lambda r: -r["cost_usd"])
    for r in by_phase:
        r["cost_usd"] = round(r["cost_usd"], 6)
    out["by_phase"] = by_phase
    return out


def _no_transcripts(reason):
    return {"available": False, "reason": reason, "tokens": None, "calls": None, "by_role": []}


def spend(ledger, cycle, project_root, override=None, *, talos_dir=None) -> dict:
    try:
        events = _events_spend(ledger, cycle)
    except Exception as e:
        events = {"runs": 0, "cost_usd": 0.0, "tokens": 0, **{f: 0 for f in USAGE_FIELDS}, "by_phase": []}
        return {"cycle": cycle, "source": "events-only", "events": events,
                "transcripts": _no_transcripts(f"events unreadable: {type(e).__name__}: {e}")}
    try:
        usage, why = load_usage(talos_dir)
        if usage is None:
            transcripts = _no_transcripts(why)
        else:
            recs, reason = usage.collect(project_root, override)
            if reason:
                transcripts = _no_transcripts(reason)
            else:
                usage.assign_cycles(recs, ledger)
                mine = [r for r in recs if r["cycle"] == cycle]
                by_role = [{"role": g["key"][0], "model": g["key"][1], "tokens": g["total"], "calls": g["calls"]}
                           for g in usage.summarize(mine, lambda r: (r["role"], usage.family(r["model"])))]
                transcripts = {"available": True, "reason": None,
                               "tokens": sum(usage.total(r) for r in mine), "calls": len(mine),
                               "by_role": by_role}
    except Exception as e:
        transcripts = _no_transcripts(f"usage unavailable: {type(e).__name__}: {e}")
    return {"cycle": cycle,
            "source": "events+transcripts" if transcripts["available"] else "events-only",
            "events": events, "transcripts": transcripts}
