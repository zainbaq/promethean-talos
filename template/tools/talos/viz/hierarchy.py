"""The Canopy block (/api/hierarchy): who did the work and who handed it to whom.

Standard library only, plus tools/talos/usage.py as the one transcript reader. Read-only. Dispatches and their cost come
from the transcripts (each subagent's .meta.json and usage records), and the item handoffs from the ledger. Without
transcripts the block falls back to the ledger alone: roles and handoffs, no cost.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from . import activity as A

ITEM_RE = re.compile(r"\bITEM-\d{4}\b")
# The roles that make the thing an item delivers: their leaves carry the item's outcome. Everything else (planning,
# review, the record) is work around it, so its leaves stay neutral.
BUILD_ROLES = frozenset({"engineer", "ui-engineer", "devops-engineer", "technical-writer", "ux-designer"})
QUESTION_EVENTS = frozenset({"question.asked"})
# Only a gap ending in one of these was the company waiting on the CEO. A gap before the CEO's own new instruction was not.
CEO_DECISIONS = frozenset({"charter.approved", "design.approved", "plan.approved", "release.approved", "launch.approved",
                           "charter.rejected", "design.rejected", "plan.rejected", "release.rejected", "question.answered"})
WAIT_MIN_SECONDS = 600

_cache: dict = {}  # transcript path -> ((mtime_ns, size), summary). A finished transcript is never parsed twice.
_cache_mu = threading.Lock()


def _scan_file(usage, path: Path, role: str) -> dict:
    """{tokens, model, start, end} for one transcript, cached on (mtime, size)."""
    st = path.stat()
    stamp = (st.st_mtime_ns, st.st_size)
    with _cache_mu:
        hit = _cache.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    recs: list = []
    usage._scan(path, role, "-", set(), recs)
    stamps = [r["ts"] for r in recs if r["ts"]]
    models = [usage.family(r["model"]) for r in recs]
    out = {"tokens": sum(usage.total(r) for r in recs), "start": min(stamps) if stamps else None,
           "end": max(stamps) if stamps else None,
           "model": max(set(models), key=models.count) if models else None}
    with _cache_mu:
        _cache[path] = (stamp, out)
    return out


def _meta(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {}


def _item_of_event(e: dict):
    item = e.get("item")
    if isinstance(item, str) and ITEM_RE.fullmatch(item):
        return item
    ref = e.get("ref")
    return ref if isinstance(ref, str) and ITEM_RE.fullmatch(ref) else None


def _says_ceo(e: dict) -> bool:
    """A note the Chief of Staff wrote down in the CEO's words counts as the CEO speaking."""
    return e.get("event") == "note" and str(e.get("summary") or "").startswith("CEO:")


def _ts(e) -> str:
    return (e or "")[:19]


def _item_outcomes(ledger: list) -> tuple[dict, dict]:
    """(item -> final state, item -> timestamps of changes requested)."""
    state, sent_back = {}, {}
    for e in ledger:
        it = _item_of_event(e)
        if not it:
            continue
        ev = e.get("event")
        if ev == "review.changes_requested":
            sent_back.setdefault(it, []).append(_ts(e.get("ts")))
        if ev in ("item.verified", "release.shipped"):
            state[it] = "shipped" if ev == "release.shipped" or state.get(it) == "shipped" else "verified"
        elif ev in ("item.blocked", "item.rejected") and state.get(it) not in ("verified", "shipped"):
            state[it] = "blocked"
    return state, sent_back


def _outcome(task: dict, state: dict, sent_back: dict) -> str:
    """The leaf's state. Only build roles carry an item's outcome (see BUILD_ROLES)."""
    if not task["finished"]:
        return "abandoned"
    if task["role"] not in BUILD_ROLES:
        return "support"
    for it in task["items"]:
        if any(ts >= (task["start"] or "") for ts in sent_back.get(it, [])):
            return "sent_back"
    states = [state.get(it) for it in task["items"]]
    if "blocked" in states:
        return "blocked"
    return "verified" if any(s in ("verified", "shipped") for s in states) else "open"


def _transcript_tasks(usage, dirs: list) -> tuple[list, list]:
    sessions, tasks = [], []
    for d in dirs:
        for main in sorted(d.glob("*.jsonl")):
            scan = _scan_file(usage, main, usage.MAIN)
            phase = A.phase_name(usage._first_prompt(main))
            sessions.append({"id": main.stem, "phase": phase or "interactive", "model": scan["model"],
                             "tokens": scan["tokens"], "start": scan["start"], "end": scan["end"]})
            for sub in sorted((d / main.stem / "subagents").glob("agent-*.jsonl")):
                m = _meta(sub.with_suffix(".meta.json"))
                role = m.get("agentType") or "?"
                desc = m.get("description") or ""
                s = _scan_file(usage, sub, role)
                items = sorted(set(ITEM_RE.findall(desc)))
                if not items and role in A.ITEM_ROLES:
                    only = usage._item_of(usage._first_prompt(sub))
                    items = [only] if ITEM_RE.fullmatch(only or "") else []
                tasks.append({"id": sub.stem, "role": role, "desc": desc, "items": items, "session": main.stem,
                              "phase": phase or "interactive", "depth": m.get("spawnDepth", 1),
                              "branch": m.get("worktreeBranch"), "finished": m.get("finished", True),
                              "tokens": s["tokens"], "model": s["model"], "start": s["start"], "end": s["end"]})
    tasks.sort(key=lambda t: t["start"] or "")
    return sessions, tasks


def _ledger_tasks(ledger: list) -> list:
    """No transcripts: one cost-less leaf per role and item, from who wrote events about it."""
    groups: dict = {}
    for e in ledger:
        it, actor = _item_of_event(e), e.get("actor")
        if not it or not isinstance(actor, str) or actor == "ceo":
            continue
        g = groups.setdefault((actor, it), {"n": 0, "start": _ts(e.get("ts")), "end": None})
        g["n"] += 1
        g["end"] = _ts(e.get("ts"))
    return [{"id": f"{actor}/{it}", "role": actor, "desc": f"{it}: {g['n']} recorded events", "items": [it],
             "session": None, "phase": None, "depth": 1, "branch": None, "finished": True, "tokens": 0,
             "model": None, "start": g["start"], "end": g["end"]}
            for (actor, it), g in sorted(groups.items(), key=lambda kv: kv[1]["start"])]


def _item_routes(ledger: list, tasks: list, state: dict, sent_back: dict) -> dict:
    """item -> its handoffs in time order, the CEO's words included, with the wait before each step."""
    steps: dict = {}
    for e in ledger:
        ts = _ts(e.get("ts"))
        it = _item_of_event(e)
        if it:
            steps.setdefault(it, []).append({"ts": ts, "actor": e.get("actor"), "kind": e.get("event"),
                                             "what": str(e.get("summary") or "")[:160], "tokens": None})
        elif _says_ceo(e):
            for said in sorted(set(ITEM_RE.findall(str(e.get("summary"))))):
                steps.setdefault(said, []).append({"ts": ts, "actor": "ceo", "kind": "note",
                                                   "what": str(e.get("summary"))[5:165], "tokens": None})
    for t in tasks:
        for it in t["items"]:
            steps.setdefault(it, []).append({"ts": t["start"] or "", "actor": t["role"], "kind": "task", "what": t["desc"],
                                             "tokens": t["tokens"] or None, "task": t["id"]})
    out = {}
    for it, rows in steps.items():
        rows.sort(key=lambda r: r["ts"])
        prev = None
        for r in rows:
            gap = _seconds(prev, r["ts"]) if prev else 0
            r["wait"] = gap if gap >= WAIT_MIN_SECONDS else 0
            r["on_you"] = bool(r["wait"]) and r["kind"] in CEO_DECISIONS
            prev = r["ts"] or prev
        out[it] = {"state": state.get(it, "open"), "sent_back": len(sent_back.get(it, [])), "steps": rows,
                   "tokens": sum(t["tokens"] for t in tasks if it in t["items"]),
                   "first": rows[0]["ts"] if rows else None, "last": rows[-1]["ts"] if rows else None}
    return out


def _seconds(a: str, b: str) -> int:
    try:
        return max(0, int((datetime.fromisoformat(b[:19]) - datetime.fromisoformat(a[:19])).total_seconds()))
    except ValueError:
        return 0


def build(project_root, record, ledger: list, transcripts=None, talos_dir=None) -> dict:
    sessions, tasks, reason = [], [], None
    usage, why = A.load_usage(talos_dir)
    if usage is None:
        reason = why
    else:
        dirs = usage.transcript_dirs(project_root, transcripts)
        if dirs:
            sessions, tasks = _transcript_tasks(usage, dirs)
        else:
            reason = "no Claude Code transcripts for this project"
    source = "transcripts" if tasks or sessions else "ledger"
    if source == "ledger":
        tasks = _ledger_tasks(ledger)
    state, sent_back = _item_outcomes(ledger)
    for t in tasks:
        t["outcome"] = _outcome(t, state, sent_back)
    runs = {e.get("session"): e for e in ledger if e.get("event") == "run.completed" and e.get("session")}
    for s in sessions:
        run = runs.get(s["id"])
        s["cost_usd"] = run.get("cost_usd") if run else None
        if run and run.get("phase"):
            s["phase"] = run["phase"]
    orchestration = sum(s["tokens"] for s in sessions)
    unattributed = orchestration + sum(t["tokens"] for t in tasks if not t["items"])
    ceo = [{"ts": _ts(e.get("ts")), "event": e.get("event"), "ref": e.get("ref"), "summary": str(e.get("summary") or "")[:160]}
           for e in ledger if e.get("actor") == "ceo" or _says_ceo(e)]
    cycles = [{"n": e.get("cycle"), "ts": _ts(e.get("ts"))} for e in ledger if e.get("event") == "cycle.started"]
    return {
        "source": source, "reason": reason,
        "sessions": sessions, "tasks": tasks, "ceo": ceo, "cycles": cycles,
        "items": _item_routes(ledger, tasks, state, sent_back),
        "totals": {
            "tokens": orchestration + sum(t["tokens"] for t in tasks),
            "orchestration": orchestration, "unattributed": unattributed,
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in runs.values()), 2),
            "questions": sum(1 for e in ledger if e.get("event") in QUESTION_EVENTS),
        },
    }
