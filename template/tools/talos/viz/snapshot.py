"""Builds the ADR-0007 snapshot from a record directory. Read-only; each block fails soft into `errors`."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import record as R

try:  # ITEM-0002 contract (ADR-0005 amendment): the whole activity and spend blocks come from viz.activity
    from . import activity as _activity
except ImportError:  # pragma: no cover - depends on the checkout
    _activity = None

_NO_TRANSCRIPTS = "no Claude Code transcripts for this project yet"


def have_activity() -> bool:
    return _activity is not None


def _activity_unavailable(reason: str, checked_at: str) -> dict:
    return {
        "status": "unavailable", "reason": reason, "checked_at": checked_at,
        "window_seconds": 120, "recent_seconds": 300, "transcript_dirs": [],
        "phase": {"status": "unknown", "name": None, "session": None, "since": None},
        "agents": [], "last_run": None,
    }


def _spend_events_only(cycle: int, events: dict | None = None) -> dict:
    zero = {"runs": 0, "cost_usd": 0.0, "tokens": 0, "input_tokens": 0, "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0, "output_tokens": 0, "by_phase": []}
    return {"cycle": cycle, "source": "events-only", "events": events or zero,
            "transcripts": {"available": False, "reason": _NO_TRANSCRIPTS, "tokens": None, "calls": None, "by_role": []}}


def _posix(p: Path) -> str:
    return Path(p).resolve().as_posix()


def build(project_root: Path, record: Path, *, now: datetime, version: int, checked_at: datetime,
          transcripts: str | None = None, talos_dir: str | None = None) -> dict:
    project_root, record = Path(project_root), Path(record)
    errors: list[dict] = []
    checked_iso = R.iso(checked_at)

    def soft(block: str, fn, empty):
        try:
            return fn()
        except Exception as exc:  # fail soft per block (ADR-0007)
            errors.append({"block": block, "reason": f"{type(exc).__name__}: {exc}"})
            return empty

    # ledger
    ledger_path = record / "ledger.jsonl"
    if ledger_path.exists():
        ledger, ledger_errors = R.read_ledger(ledger_path)
        errors += ledger_errors
    else:
        ledger = []
        errors.append({"block": "ledger", "reason": "company/ledger.jsonl not found"})

    # state
    def read_state() -> dict:
        st = json.loads((record / "state.json").read_text(encoding="utf-8"))
        if not isinstance(st, dict):
            raise ValueError("state.json is not a JSON object")
        return st
    state = soft("state", read_state, {})

    # charter
    charter_text = ""
    charter_fm: dict = {}
    try:
        charter_text = (record / "charter.md").read_text(encoding="utf-8", errors="replace")
        charter_fm, _ = R.parse_frontmatter(charter_text)
    except Exception as exc:
        errors.append({"block": "charter", "reason": f"company/charter.md unreadable: {exc}"})
    approved_event = charter_fm.get("approved_event")
    if approved_event in (None, "", "null", "None"):
        approved_event = None
    charter = {"status": charter_fm.get("status") or "draft",
               "title": R.charter_title(charter_text) if charter_text else "Charter",
               "approved_event": approved_event}

    # items
    if (record / "backlog").is_dir():
        items = soft("items", lambda: R.read_items(record / "backlog"), [])
    else:
        items = []
        errors.append({"block": "items", "reason": "company/backlog/ not found"})

    # questions
    if (record / "questions.md").exists():
        waiting_q, other_open = soft("questions", lambda: R.read_questions(record / "questions.md"), ([], 0))
    else:
        waiting_q, other_open = [], 0
        errors.append({"block": "questions", "reason": "company/questions.md not found"})

    # report
    report = None
    if (record / "reports").is_dir():
        report = soft("report", lambda: R.latest_report(record / "reports"), None)
    else:
        errors.append({"block": "report", "reason": "company/reports/ not found"})

    cycle = R.cycle_block(state, ledger, now)
    waiting = waiting_q + soft("items", lambda: R.gates(ledger, state, items), [])

    # events, newest first
    runs = R.derive_runs(ledger)
    events = []
    for e, (phase, run) in zip(ledger, runs):
        ev = {
            "id": e.get("id"), "ts": e.get("ts"), "actor": e.get("actor"), "tier": e.get("tier"),
            "event": e.get("event"), "ref": e.get("ref"), "summary": e.get("summary", ""),
            "evidence": e.get("evidence") if isinstance(e.get("evidence"), list) else [],
            "branch": e.get("branch"), "cycle": e.get("cycle", 0), "phase": phase, "run": run,
            "extra": {k: v for k, v in e.items() if k not in R.STANDARD_KEYS},
        }
        events.append(ev)
    events.reverse()
    event_types = sorted({str(e["event"]) for e in events if e["event"] is not None})
    actors = sorted({str(e["actor"]) for e in events if e["actor"] is not None})

    counts_items = {s: 0 for s in R.ITEM_STATUSES}
    for it in items:
        if it["status"] in counts_items:
            counts_items[it["status"]] += 1
    counts_items["total"] = len(items)
    try:
        lessons = len(list((record / "knowledge").glob("lesson-*.md")))
    except OSError:
        lessons = 0
    counts = {"items": counts_items, "events": len(events), "event_types": len(event_types),
              "ceo_questions_open": len(waiting_q), "other_questions_open": other_open, "lessons": lessons}

    folder = record.resolve().name if record.resolve().name != "company" else record.resolve().parent.name
    project = {
        "name": R.display_name(charter_text, folder), "folder": folder,
        "root": _posix(project_root), "record": _posix(record),
        "size": charter_fm.get("size") or "medium",
        "teams": state.get("teams") if isinstance(state.get("teams"), list) else [],
    }

    shown_cycle = cycle["number"]
    if _activity is not None:
        try:
            activity = _activity.derive(project_root, record, ledger, shown_cycle, transcripts, talos_dir=talos_dir)
        except Exception as exc:
            errors.append({"block": "activity", "reason": f"{type(exc).__name__}: {exc}"})
            activity = _activity_unavailable(f"activity failed: {exc}", checked_iso)
        try:
            spend = _activity.spend(ledger, shown_cycle, project_root, transcripts, talos_dir=talos_dir)
        except Exception as exc:
            errors.append({"block": "spend", "reason": f"{type(exc).__name__}: {exc}"})
            spend = _spend_events_only(shown_cycle)
    else:
        activity = _activity_unavailable("viz.activity not installed", checked_iso)
        spend = _spend_events_only(shown_cycle)

    return {
        "schema": 1, "generated_at": R.iso(now), "checked_at": checked_iso, "version": version,
        "project": project, "charter": charter, "cycle": cycle, "counts": counts,
        "waiting": waiting, "events": events, "event_types": event_types, "actors": actors,
        "items": items, "report": report, "activity": activity, "spend": spend, "errors": errors,
    }
