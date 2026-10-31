"""Record reader: re-implements the Talos CLI's file-format rules (ADR-0003) as pure functions.

Standard library only. `talos.py` is never imported. Nothing here writes anywhere; the only I/O is
reading the paths a function is given.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ITEM_STATUSES = ["proposed", "ready", "assigned", "in_progress", "blocked",
                 "completed", "verified", "rejected", "shipped"]

STANDARD_KEYS = ("id", "ts", "actor", "tier", "event", "ref", "summary", "evidence", "branch", "cycle")

_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS_FORMAT)


def _parse_ts(text: str) -> datetime:
    return datetime.strptime(text, _TS_FORMAT).replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------ frontmatter

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Same rules as talos.parse_frontmatter: `---` block, `key: value`, JSON strings, `[a, b]` lists."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n---", 2)
    if len(parts) < 2:
        return {}, text
    head = parts[0][3:]
    body = parts[1][1:] if len(parts) == 2 else parts[1] + "\n---" + parts[2]
    fm: dict = {}
    for line in head.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip('"') for x in v[1:-1].split(",") if x.strip()]
            elif len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                try:
                    v = json.loads(v)
                except Exception:
                    v = v[1:-1]
            fm[k.strip()] = v
    return fm, body.lstrip("\n")


# ------------------------------------------------------------------ ledger

def read_ledger(path: Path) -> tuple[list[dict], list[dict]]:
    """Events in file order and `errors` entries. A malformed line is skipped and reported."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return [], [{"block": "ledger", "reason": f"company/ledger.jsonl unreadable: {exc.strerror or exc}"}]
    events: list[dict] = []
    errors: list[dict] = []
    text = raw.decode("utf-8", errors="replace")
    for n, line in enumerate(text.split("\n"), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            errors.append({"block": "ledger-line", "reason": f"line {n}: {exc}"})
            continue
        if not isinstance(obj, dict):
            errors.append({"block": "ledger-line", "reason": f"line {n}: not a JSON object"})
            continue
        events.append(obj)
    return events, errors


def derive_runs(ledger: list[dict]) -> list[tuple[str | None, str | None]]:
    """(phase, run) per event in file order: the first run.completed at or after it in the same cycle."""
    out: list[tuple[str | None, str | None]] = [(None, None)] * len(ledger)
    nxt: dict = {}
    for i in range(len(ledger) - 1, -1, -1):
        e = ledger[i]
        c = e.get("cycle")
        if e.get("event") == "run.completed":
            nxt[c] = (e.get("phase") or e.get("ref"), e.get("id"))
        out[i] = nxt.get(c, (None, None))
    return out


# ------------------------------------------------------------------ items

def _none_if_empty(v):
    return None if v is None or v == "" else v


def read_items(backlog: Path) -> list[dict]:
    items = []
    for p in sorted(Path(backlog).glob("ITEM-*.md"), key=lambda q: q.name):
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8", errors="replace"))
        cycle = fm.get("cycle")
        try:
            cycle = int(str(cycle).strip())
        except (TypeError, ValueError):
            cycle = None
        items.append({
            "id": _none_if_empty(fm.get("id")) or p.stem,
            "title": _none_if_empty(fm.get("title")) or "",
            "status": _none_if_empty(fm.get("status")),
            "owner": _none_if_empty(fm.get("owner")),
            "spec": _none_if_empty(fm.get("spec")),
            "branch": _none_if_empty(fm.get("branch")),
            "commit": _none_if_empty(None if fm.get("commit") is None else str(fm.get("commit"))),
            "priority": _none_if_empty(fm.get("priority")),
            "risk": _none_if_empty(fm.get("risk")),
            "cycle": cycle,
            "created": _none_if_empty(fm.get("created")),
            "updated": _none_if_empty(fm.get("updated")),
            "path": f"company/backlog/{p.name}",
        })
    return items


# ------------------------------------------------------------------ questions

_BLOCK_RE = re.compile(r"^### (Q-\d+) — (.*?)$(.*?)(?=^### |\Z)", re.S | re.M)


def _field(block: str, name: str) -> str:
    m = re.search(rf"^- {name}: (.*)$", block, re.M)
    return m.group(1).strip() if m else ""


def read_questions(path: Path) -> tuple[list[dict], int]:
    """(waiting entries of kind "question" for the CEO, number of open questions for other roles)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    open_part = text.split("## Answered")[0]
    all_open = len(re.findall(r"^### Q-\d+", open_part, re.M))
    waiting = []
    for m in _BLOCK_RE.finditer(open_part):
        qid, title, rest = m.group(1), m.group(2).strip(), m.group(3)
        if not (re.search(r"^- for: ceo", rest, re.M) or not re.search(r"^- for: ", rest, re.M)):
            continue
        asked_by = asked_at = ref = None
        parts = [x.strip() for x in _field(rest, "asked by").split(" · ")]
        if parts and parts[0]:
            asked_by = parts[0]
        for part in parts[1:]:
            if _ISO_RE.match(part):
                asked_at = part
            elif part.startswith("ref: "):
                ref = part[5:].strip() or None
        waiting.append({
            "kind": "question", "key": qid, "id": qid, "title": title,
            "context": _field(rest, "context"), "options": _field(rest, "options"),
            "asked_by": asked_by, "asked_at": asked_at, "ref": ref,
            "command": f'tools/talos/run review "{qid}: <your answer>"',
        })
    waiting.sort(key=lambda w: w["id"])
    return waiting, all_open - len(waiting)


# ------------------------------------------------------------------ gates

def _latest_index(ledger: list[dict], kind: str, ref: str | None = None) -> int | None:
    for i in range(len(ledger) - 1, -1, -1):
        e = ledger[i]
        if e.get("event") == kind and (ref is None or e.get("ref") == ref):
            return i
    return None


def read_inbox(path: Path, ledger: list[dict]) -> list[dict]:
    """The CEO's messages, oldest first, each with its acknowledgement if any. A malformed line is skipped."""
    acks = {e.get("ref"): {"by": e.get("actor"), "summary": e.get("summary"), "ts": e.get("ts")}
            for e in ledger if e.get("event") == "message.acknowledged"}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if isinstance(m, dict) and m.get("id"):
            out.append({"id": m["id"], "ts": m.get("ts") or "", "kind": m.get("kind"), "text": m.get("text") or "", "ack": acks.get(m["id"])})
    return out


def read_runner(path: Path, now: float, fresh_seconds: float = 20.0) -> dict:
    """Whether `talos work` is alive, from the heartbeat it keeps."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        beat = float(d.get("beat"))
    except (OSError, ValueError, TypeError):
        return {"active": False, "doing": None, "phase": None}
    active = now - beat < fresh_seconds
    return {"active": active, "doing": d.get("doing") if active else None, "phase": d.get("phase") if active else None}


def preset_block(ledger: list[dict]) -> dict:
    """The current preset, and each preset's measured dollars per verified item in the cycles it ran."""
    current = "medium"
    for e in ledger:
        if e.get("event") == "preset.changed" and e.get("preset") in ("lite", "medium", "heavy"):
            current = e["preset"]
    rows = []
    for name in ("lite", "medium", "heavy"):
        runs = [e for e in ledger if e.get("event") == "run.completed" and e.get("preset") == name]
        cycles = {e.get("cycle") for e in runs}
        verified = sum(1 for e in ledger if e.get("event") == "item.verified" and e.get("cycle") in cycles)
        cost = sum(float(e.get("cost_usd") or 0) for e in runs)
        rows.append({"name": name, "usd_per_item": round(cost / verified, 2) if verified and cost else None})
    return {"preset": current, "presets": rows}


def gates(ledger: list[dict], state: dict, items: list[dict]) -> list[dict]:
    """Waiting entries of kind "gate": charter, plan, design, then release by item id."""
    out: list[dict] = []

    def proposed_gate(name: str, label: str) -> None:
        p = _latest_index(ledger, f"{name}.proposed")
        if p is None:
            return
        a = _latest_index(ledger, f"{name}.approved")
        r = _latest_index(ledger, f"{name}.rejected")
        if (a is not None and a > p) or (r is not None and r > p):
            return
        ev = ledger[p]
        out.append({
            "kind": "gate", "key": f"gate:{name}", "gate": name, "ref": None,
            "title": f"{label} gate: {ev.get('summary', '')}",
            "proposed_event": ev.get("id"), "proposed_at": ev.get("ts"),
            "command": f'tools/talos/run review "<your words approving the {name}>"',
        })

    proposed_gate("understanding", "Understanding")
    proposed_gate("charter", "Charter")
    proposed_gate("plan", "Plan")
    teams = (state or {}).get("teams") or []
    skip_design = bool(teams) and "design" not in teams
    if not skip_design and _latest_index(ledger, "design-waiver.approved") is None:
        proposed_gate("design", "Design")

    approved_refs = {e.get("ref") for e in ledger if e.get("event") in ("release.approved", "release.rejected")}
    for it in sorted(items, key=lambda i: str(i.get("id"))):
        if it.get("status") != "verified" or it.get("id") in approved_refs:
            continue
        v = _latest_index(ledger, "item.verified", it["id"])
        ev = ledger[v] if v is not None else None
        out.append({
            "kind": "gate", "key": f"gate:release:{it['id']}", "gate": "release", "ref": it["id"],
            "title": f"Release {it['id']}: {it.get('title') or ''}",
            "proposed_event": ev.get("id") if ev else None, "proposed_at": ev.get("ts") if ev else None,
            "command": f'tools/talos/run review "<your words approving the release of {it["id"]}>"',
        })
    return out


# ------------------------------------------------------------------ cycle, report, names

def cycle_block(state: dict, ledger: list[dict], now: datetime) -> dict:
    state = state if isinstance(state, dict) else {}
    try:
        number = int(state.get("cycle", 0) or 0)
    except (TypeError, ValueError):
        number = 0
    is_open = bool(state.get("cycle_open"))
    budget = state.get("budget")
    block = {"number": number, "open": is_open, "budget": budget if isinstance(budget, str) else "",
             "started_at": None, "ended_at": None, "elapsed_minutes": None}
    if number <= 0:
        return block
    ref = f"cycle-{number:03d}"
    si = _latest_index(ledger, "cycle.started", ref)
    ei = None if is_open else _latest_index(ledger, "cycle.ended", ref)
    if si is None:
        return block
    block["started_at"] = ledger[si].get("ts")
    if ei is not None:
        block["ended_at"] = ledger[ei].get("ts")
    try:
        t0 = _parse_ts(ledger[si]["ts"])
        t1 = _parse_ts(ledger[ei]["ts"]) if ei is not None else now.astimezone(timezone.utc)
        block["elapsed_minutes"] = int((t1 - t0).total_seconds() // 60)
    except (KeyError, ValueError, TypeError):
        block["elapsed_minutes"] = None
    return block


def latest_report(reports: Path) -> dict | None:
    """The lexically last cycle-*.md in company/reports/, or None."""
    files = sorted(Path(reports).glob("cycle-*.md"), key=lambda q: q.name)
    if not files:
        return None
    p = files[-1]
    m = re.match(r"cycle-(\d+)\.md$", p.name)
    return {
        "path": f"company/reports/{p.name}",
        "cycle": int(m.group(1)) if m else None,
        "modified_at": iso(datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)),
        "markdown": p.read_text(encoding="utf-8", errors="replace"),
    }


def charter_title(charter_text: str) -> str:
    _, body = parse_frontmatter(charter_text)
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or "Charter"
    return "Charter"


def display_name(charter_text: str, folder: str) -> str:
    """Charter H1 minus a leading `Charter:`; the folder name when that is empty, missing or the init placeholder."""
    _, body = parse_frontmatter(charter_text)
    h1 = None
    for line in body.splitlines():
        if line.startswith("# "):
            h1 = line[2:].strip()
            break
    if h1 is None:
        return folder
    if h1.startswith("Charter:"):
        h1 = h1[len("Charter:"):]
    h1 = h1.strip()
    if not h1 or h1 == "Charter":
        return folder
    return h1
