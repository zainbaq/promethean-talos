#!/usr/bin/env python3
"""
company — the shared project record CLI for the Talos framework.

Standard library only. Every agent in the company writes to the record through
this tool so that entries are consistent, validated and append-only.

Usage (run from the project root):
    tools/talos/talos <command> [options]

Commands:
    init                         create the company/ scaffold
    log EVENT [opts]             append a ledger event
    ask "question" [opts]        file a question for the CEO
    answer Q-0001 "answer"       record the CEO's answer
    item new|set|list|show       backlog items
    spec new                     create a spec file from the template
    decision add                 create an ADR
    lesson add                   record a lesson in knowledge/
    cycle start|end              open or close a cycle
    approve charter|plan|design|design-waiver|release   record a CEO approval (quote the CEO)
    gate charter|plan|design|release|item   exit 1 unless the gate is satisfied
    status                       print the dashboard (markdown)
    report [--cycle N]           write company/reports/cycle-NNN.md
    events [--cycle N]           one line per ledger event
    context ITEM --role R        write the context pack one role needs for one item
    spec lint [SPEC ...]         check specs against the handoff contract
    size [small|medium|large]    print or set the project size (scales planning depth)
    usage [--cycle N] [--by ...] measured token usage from Claude Code transcripts
    journal [--date YYYY-MM-DD]  render ledger to company/journal/
    consolidate                  rebuild knowledge/INDEX.md and flag duplicates

Set TALOS_ACTOR (or pass --actor) so events carry the role that made them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, date
from pathlib import Path

ROOT = Path(os.environ.get("TALOS_ROOT", Path.cwd()))
CO = ROOT / "company"
LEDGER = CO / "ledger.jsonl"
STATE = CO / "state.json"
QUESTIONS = CO / "questions.md"

EVENT_TYPES = {
    "project.kickoff", "charter.proposed", "charter.approved",
    "plan.proposed", "plan.approved",
    "item.created", "item.assigned", "item.started", "item.blocked",
    "item.completed", "item.verified", "item.rejected",
    "question.asked", "question.answered",
    "decision.recorded", "spec.created",
    "review.requested", "review.passed", "review.changes_requested",
    "release.proposed", "release.approved", "release.shipped",
    "lesson.recorded", "budget.consumed",
    "cycle.started", "cycle.ended", "retro.completed",
    "spec.amended", "environment.updated", "followup.raised", "run.completed",
    "design.proposed", "design.approved", "design-waiver.approved", "note",
}

ITEM_STATUSES = ["proposed", "ready", "assigned", "in_progress", "blocked",
                 "completed", "verified", "rejected", "shipped"]

TIERS = {"executive", "review", "execution", "mechanical", "ceo", "unknown"}

RISKS = ["low", "normal", "high"]

# Planning depth scales with the project (charter frontmatter `size`, set with `talos size`).
# spec_lines: lint budget outside code blocks. plan_turns: the launcher's turn cap for the plan phase.
SIZES = {
    "small": {"spec_lines": 60, "plan_turns": 40},
    "medium": {"spec_lines": 120, "plan_turns": 90},
    "large": {"spec_lines": 160, "plan_turns": 120},
}


def project_size() -> str:
    try:
        fm, _ = parse_frontmatter((CO / "charter.md").read_text(encoding="utf-8"))
    except OSError:
        return "medium"
    s = str(fm.get("size") or "medium").strip().lower()
    return s if s in SIZES else "medium"


# ----------------------------------------------------------------- helpers

def write_lf(path, text, encoding="utf-8"):
    """Write text with LF line endings on every platform (Windows would otherwise emit CRLF)."""
    with open(path, "w", encoding=encoding, newline="\n") as f:
        f.write(text)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(msg: str, code: int = 1) -> None:
    print(f"talos: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_scaffold() -> None:
    if not CO.exists():
        die("no company/ directory here. Run `talos init` from the project root.")


def slug(text: str, n: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:n].rstrip("-") or "untitled"


def read_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"cycle": 0, "cycle_open": False, "counters": {}}


def write_state(st: dict) -> None:
    write_lf(STATE, json.dumps(st, indent=2) + "\n", encoding="utf-8")


def next_id(prefix: str) -> str:
    st = read_state()
    n = st["counters"].get(prefix, 0) + 1
    st["counters"][prefix] = n
    write_state(st)
    return f"{prefix}-{n:04d}"


def read_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_event(event: str, *, actor: str | None = None, tier: str | None = None,
                 ref: str | None = None, summary: str = "", evidence: list[str] | None = None,
                 branch: str | None = None, extra: dict | None = None) -> dict:
    if event not in EVENT_TYPES:
        die(f"unknown event type '{event}'. Known: {', '.join(sorted(EVENT_TYPES))}")
    st = read_state()
    actor = actor or os.environ.get("TALOS_ACTOR", "unknown")
    tier = tier or os.environ.get("TALOS_TIER", "unknown")
    if tier not in TIERS:
        die(f"unknown tier '{tier}'. Known: {', '.join(sorted(TIERS))}")
    # Event ids are time-based, not counter-based, so parallel worktrees cannot collide.
    ts = now()
    rec = {
        "id": "EVT-" + ts.replace("-", "").replace(":", "").replace("T", "").replace("Z", "") + "-" + os.urandom(2).hex(),
        "ts": ts,
        "actor": actor,
        "tier": tier,
        "event": event,
        "ref": ref,
        "summary": summary,
        "evidence": evidence or [],
        "branch": branch,
        "cycle": st.get("cycle", 0),
    }
    if extra:
        rec.update(extra)
    with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def parse_frontmatter(text: str) -> tuple[dict, str]:
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


def _fm_scalar(v) -> str:
    """Quote frontmatter scalars that YAML would otherwise misread (colons, leading symbols, quotes)."""
    s = "" if v is None else str(v)
    if s == "" or re.search(r"[:#\[\]{}]|^[\s\-?&*!|>'\"%@`]|\s$", s):
        return json.dumps(s)
    return s


def dump_frontmatter(fm: dict, body: str) -> str:
    lines = ["---"]
    for k, v in fm.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(json.dumps(x) for x in v)}]")
        else:
            lines.append(f"{k}: {_fm_scalar(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.rstrip("\n") + "\n"


# ----------------------------------------------------------------- init

SCAFFOLD_README = {
    "backlog": "One file per work item (`ITEM-0001.md`). Create with `talos item new`. Status moves only through `talos item set`.\n",
    "specs": "Architect-to-engineer handoffs (`SPEC-0001-slug.md`). A spec must have goal, non-goals, files in scope, interfaces, acceptance criteria, budget, and linked ADRs/lessons.\n",
    "decisions": "Architecture Decision Records (`ADR-0001-slug.md`). Create with `talos decision add`.\n",
    "journal": "Human-readable rendering of `ledger.jsonl`, one file per day. Regenerate with `talos journal`.\n",
    "knowledge": "One lesson per file with evidence and `applies_to` tags. `INDEX.md` is rebuilt by `talos consolidate`.\n",
    "reports": "Cycle reports for the CEO (`cycle-001.md`). Generated by `talos report`, then edited by the Chief of Staff.\n",
    "retros": "Retrospective notes per cycle, written by the Learning Officer.\n",
    "research": "Sourced research findings from the Research team.\n",
}


ENVIRONMENT_TEMPLATE = """---
status: not probed
---

# Environment

_not probed_

The Chief of Staff fills this in during kickoff by running the probe commands, and every spec and every
executor prompt points here instead of restating machine facts. Update it whenever a role discovers a quirk.

## Repository
- Path:
- Base branch (`git rev-parse --abbrev-ref HEAD`):
- Line endings: `.gitattributes` present? `core.autocrlf` value? (`git config --get core.autocrlf`)

## Toolchain (project-local, never the machine's)
- Python venv: `.venv/` at the repo root, created at kickoff with `uv venv --python <version> .venv` (uv downloads its own Python; nothing on the machine is used). Interpreter: `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (POSIX). Version:
- Dependency manifest: `pyproject.toml` or `requirements.txt` + `requirements-dev.txt`; installed with `uv pip install -r ...` into the venv. Pytest lives in the venv.
- Node / other runtimes: project-local too (`node_modules/`, version pinned in `.nvmrc` or `package.json` engines).
- Machine interpreters found and deliberately NOT used (stubs, Anaconda, system Python):

## Test runner
- The one command that runs the whole suite from the repo root, using the venv (e.g. `.venv/Scripts/python -m pytest -q`):
- Known quirks (environment variables, plugins to disable, slow tests):

## Shell
- Shell the Bash tool uses (`echo $SHELL`, `uname -s`):
- Quirks (e.g. `bash` on PATH resolves to WSL; quoting of backslashes; path style):

## Services and ports
- Databases, containers, dev servers available and how to start them:

## Access from other devices
- Every URL the CEO may open from a phone is listed in BOTH forms: the hostname (e.g. `http://myhost:8000`, needs MagicDNS) and the raw address (e.g. `http://100.x.y.z:8000`). Reports copy both. In the first live run the CEO reached the product only by the form the report had not given.
- Tailscale node name and IPv4 (`tailscale status`), or other tunnel/ingress:

## Secrets
- Where they live, by name only (never values):
"""


def cmd_init(args) -> None:
    CO.mkdir(exist_ok=True)
    for d, readme in SCAFFOLD_README.items():
        (CO / d).mkdir(exist_ok=True)
        rp = CO / d / "README.md"
        if not rp.exists():
            write_lf(rp, f"# {d}\n\n{readme}", encoding="utf-8")
    if not (CO / "charter.md").exists():
        write_lf((CO / "charter.md"), 
            "---\nstatus: draft\napproved_event: null\nsize: medium\n---\n\n# Charter\n\n"
            "_Not yet written. The Head of Product drafts this from the CEO brief during kickoff._\n",
            encoding="utf-8")
    if not QUESTIONS.exists():
        write_lf(QUESTIONS, "# Questions\n\nOpen questions first, answered ones below. Each question names who must answer it (`for:`); only `for: ceo` questions need the CEO.\n\n## Open\n\n## Answered\n\n", encoding="utf-8")
    if not (CO / "environment.md").exists():
        write_lf((CO / "environment.md"), ENVIRONMENT_TEMPLATE, encoding="utf-8")
    if not (CO / "knowledge" / "INDEX.md").exists():
        write_lf((CO / "knowledge" / "INDEX.md"), "# Knowledge index\n\n_No lessons yet._\n", encoding="utf-8")
    if not LEDGER.exists():
        LEDGER.touch()
    if not STATE.exists():
        write_state({"cycle": 0, "cycle_open": False, "counters": {}})
    if getattr(args, "teams", None):
        st = read_state()
        st["teams"] = [t.strip() for t in args.teams.split(",") if t.strip()]
        write_state(st)
    if not (CO / "brief.md").exists() and getattr(args, "brief", None):
        write_lf((CO / "brief.md"), Path(args.brief).read_text(encoding="utf-8"), encoding="utf-8")
    print(f"talos: scaffold ready at {CO}")


# ----------------------------------------------------------------- log / ask / answer

def cmd_log(args) -> None:
    ensure_scaffold()
    rec = append_event(args.event, actor=args.actor, tier=args.tier, ref=args.ref,
                       summary=args.summary or "", evidence=args.evidence, branch=args.branch)
    print(rec["id"])


AUDIENCES = ["ceo", "architect", "product", "qa", "chief-of-staff"]


def cmd_ask(args) -> None:
    ensure_scaffold()
    qid = next_id("Q")
    text = QUESTIONS.read_text(encoding="utf-8")
    block = (f"### {qid} — {args.question}\n"
             f"- for: {args.audience}\n"
             f"- asked by: {args.actor or os.environ.get('TALOS_ACTOR', 'unknown')} · {now()}"
             + (f" · ref: {args.ref}" if args.ref else "") + "\n"
             + (f"- context: {args.context}\n" if args.context else "")
             + (f"- options: {args.options}\n" if args.options else "")
             + "- answer: _pending_\n\n")
    text = text.replace("## Open\n\n", "## Open\n\n" + block, 1)
    write_lf(QUESTIONS, text, encoding="utf-8")
    append_event("question.asked", actor=args.actor, tier=args.tier, ref=qid,
                 summary=args.question, extra={"blocks": args.ref, "audience": args.audience})
    print(qid)


def cmd_answer(args) -> None:
    ensure_scaffold()
    text = QUESTIONS.read_text(encoding="utf-8")
    m = re.search(rf"(### {re.escape(args.qid)} — .*?)(?=\n### |\n## Answered|\Z)", text, re.S)
    if not m:
        die(f"{args.qid} not found in questions.md")
    block = m.group(1)
    by = args.by or "ceo"
    tier = args.tier or ("ceo" if by == "ceo" else "executive")
    answered = block.replace("- answer: _pending_", f"- answer ({now()}, by {by}): {args.answer}")
    text = text.replace(block, "", 1)
    text = text.replace("## Answered\n\n", "## Answered\n\n" + answered.rstrip("\n") + "\n\n", 1)
    write_lf(QUESTIONS, text, encoding="utf-8")
    append_event("question.answered", actor=by, tier=tier, ref=args.qid, summary=args.answer)
    print(f"{args.qid} answered by {by}")


def open_ceo_questions() -> list[str]:
    """Return the ids of open questions whose audience is the CEO."""
    if not QUESTIONS.exists():
        return []
    open_part = QUESTIONS.read_text(encoding="utf-8").split("## Answered")[0]
    ids = []
    for m in re.finditer(r"^### (Q-\d+) — .*?(?=^### |\Z)", open_part, re.S | re.M):
        if re.search(r"^- for: ceo", m.group(0), re.M) or not re.search(r"^- for: ", m.group(0), re.M):
            ids.append(m.group(1))
    return ids


# ----------------------------------------------------------------- items

def item_path(item_id: str) -> Path:
    p = CO / "backlog" / f"{item_id}.md"
    if not p.exists():
        die(f"{item_id} not found")
    return p


def cmd_item_new(args) -> None:
    ensure_scaffold()
    iid = next_id("ITEM")
    fm = {
        "id": iid, "title": args.title, "status": "proposed",
        "owner": args.owner or "", "spec": args.spec or "", "branch": "",
        "priority": args.priority or "P2", "risk": args.risk or "normal", "cycle": read_state().get("cycle", 0),
        "created": now(), "updated": now(),
    }
    body = "## Description\n\n" + (args.description or "_TBD_") + "\n\n## Acceptance criteria\n\n"
    body += "\n".join(f"- [ ] {a}" for a in (args.acceptance or ["_TBD_"])) + "\n\n## Evidence\n\n_none yet_\n"
    write_lf((CO / "backlog" / f"{iid}.md"), dump_frontmatter(fm, body), encoding="utf-8")
    append_event("item.created", actor=args.actor, tier=args.tier, ref=iid, summary=args.title)
    print(iid)


TRANSITION_EVENT = {
    "assigned": "item.assigned", "in_progress": "item.started", "blocked": "item.blocked",
    "completed": "item.completed", "verified": "item.verified", "rejected": "item.rejected",
}


def cmd_item_set(args) -> None:
    ensure_scaffold()
    p = item_path(args.item_id)
    fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    changed = []
    if args.status:
        if args.status not in ITEM_STATUSES:
            die(f"bad status; one of {ITEM_STATUSES}")
        if args.status in ("completed", "verified") and not args.evidence and "_none yet_" in body:
            die(f"refusing to mark {args.item_id} {args.status} without --evidence (principle: evidence or it did not happen)")
        fm["status"] = args.status
        changed.append(f"status={args.status}")
    for k in ("owner", "spec", "branch", "priority", "commit", "risk"):
        v = getattr(args, k, None)
        if v:
            fm[k] = v
            changed.append(f"{k}={v}")
    if args.acceptance:
        marker = "## Evidence"
        new_lines = "".join(f"- [ ] {a}\n" for a in args.acceptance)
        if marker in body:
            head, tail = body.split(marker, 1)
            body = head.rstrip("\n") + "\n" + new_lines + "\n" + marker + tail
        else:
            body = body.rstrip("\n") + "\n\n## Acceptance criteria\n\n" + new_lines
        changed.append(f"acceptance+{len(args.acceptance)}")
    if args.evidence:
        body = body.replace("_none yet_", "").rstrip("\n") + "\n" + "\n".join(f"- {e} ({now()})" for e in args.evidence) + "\n"
    fm["updated"] = now()
    write_lf(p, dump_frontmatter(fm, body), encoding="utf-8")
    ev = TRANSITION_EVENT.get(args.status or "", "note")
    append_event(ev, actor=args.actor, tier=args.tier, ref=args.item_id,
                 summary=args.summary or ", ".join(changed), evidence=args.evidence, branch=args.branch)
    print(f"{args.item_id}: {', '.join(changed) or 'noted'}")


def load_items() -> list[dict]:
    items = []
    for p in sorted((CO / "backlog").glob("ITEM-*.md")):
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        items.append(fm)
    return items


def cmd_item_list(args) -> None:
    ensure_scaffold()
    for fm in load_items():
        if args.status and fm.get("status") != args.status:
            continue
        print(f"{fm['id']}  {fm.get('status', ''):<12} {fm.get('priority', ''):<3} {fm.get('owner', '') or '-':<16} {fm.get('title', '')}")


def cmd_item_show(args) -> None:
    ensure_scaffold()
    print(item_path(args.item_id).read_text(encoding="utf-8"))


# ----------------------------------------------------------------- spec / decision / lesson

SPEC_TEMPLATE = """---
id: {sid}
title: {title}
item: {item}
status: draft
author: {actor}
created: {ts}
---

# {title}

## Goal

## Non-goals

## Files and modules in scope
_Only these may be touched. Anything else is a question, not a change._

## Interfaces and data shapes

## Acceptance criteria
_Each must be executable by the Test Engineer._
- [ ]

## Budget
- Max wall-clock:
- Max parallelism:

## Constraints from the record
- ADRs:
- Lessons:

## Open questions
_File with `talos ask` and reference this spec._
"""


def cmd_spec_new(args) -> None:
    ensure_scaffold()
    sid = next_id("SPEC")
    name = f"{sid}-{slug(args.title)}.md"
    write_lf((CO / "specs" / name), SPEC_TEMPLATE.format(
        sid=sid, title=args.title, item=args.item or "", actor=args.actor or os.environ.get("TALOS_ACTOR", "unknown"), ts=now()), encoding="utf-8")
    append_event("spec.created", actor=args.actor, tier=args.tier, ref=sid, summary=args.title, extra={"item": args.item})
    if args.item:
        p = item_path(args.item)
        fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        fm["spec"] = sid
        write_lf(p, dump_frontmatter(fm, body), encoding="utf-8")
    print(f"company/specs/{name}")


def cmd_decision_add(args) -> None:
    ensure_scaffold()
    aid = next_id("ADR")
    name = f"{aid}-{slug(args.title)}.md"
    body = (f"---\nid: {aid}\ntitle: {args.title}\nstatus: {args.status}\nauthor: {args.actor or os.environ.get('TALOS_ACTOR', 'unknown')}\ncreated: {now()}\n---\n\n"
            f"# {args.title}\n\n## Context\n\n{args.context or ''}\n\n## Decision\n\n{args.decision or ''}\n\n## Consequences\n\n{args.consequences or ''}\n\n## Alternatives considered\n\n{args.alternatives or ''}\n")
    write_lf((CO / "decisions" / name), body, encoding="utf-8")
    append_event("decision.recorded", actor=args.actor, tier=args.tier, ref=aid, summary=args.title)
    print(f"company/decisions/{name}")


def cmd_lesson_add(args) -> None:
    ensure_scaffold()
    if not args.evidence:
        die("a lesson needs --evidence (ledger event ids, file paths, or test output). Vague lessons are not kept.")
    lid = next_id("LESSON")
    name = f"{lid.lower()}-{slug(args.title)}.md"
    fm = {
        "id": lid, "title": args.title, "applies_to": args.applies_to or ["general"],
        "confidence": args.confidence, "evidence": args.evidence,
        "recorded": now(), "author": args.actor or os.environ.get("TALOS_ACTOR", "unknown"),
    }
    body = f"# {args.title}\n\n{args.body}\n\n**Why:** {args.why or ''}\n\n**How to apply:** {args.apply or ''}\n"
    write_lf((CO / "knowledge" / name), dump_frontmatter(fm, body), encoding="utf-8")
    append_event("lesson.recorded", actor=args.actor, tier=args.tier, ref=lid, summary=args.title, evidence=args.evidence)
    rebuild_index()
    print(f"company/knowledge/{name}")


def rebuild_index() -> list[str]:
    lines = ["# Knowledge index", "", "One line per lesson. Load the lessons whose `applies_to` matches your role before you start.", ""]
    seen_titles: dict[str, str] = {}
    dupes = []
    for p in sorted((CO / "knowledge").glob("lesson-*.md")):
        fm, _ = parse_frontmatter(p.read_text(encoding="utf-8"))
        tags = fm.get("applies_to", [])
        if isinstance(tags, str):
            tags = [tags]
        key = slug(fm.get("title", ""))[:30]
        if key in seen_titles:
            dupes.append((seen_titles[key], p.name))
        seen_titles[key] = p.name
        lines.append(f"- [{fm.get('title', p.stem)}]({p.name}) — tags: {', '.join(tags)} · confidence: {fm.get('confidence', '?')}")
    if len(lines) == 4:
        lines.append("_No lessons yet._")
    write_lf((CO / "knowledge" / "INDEX.md"), "\n".join(lines) + "\n", encoding="utf-8")
    return [f"possible duplicate: {a} ~ {b}" for a, b in dupes]


def cmd_consolidate(args) -> None:
    ensure_scaffold()
    warnings = rebuild_index()
    print("knowledge/INDEX.md rebuilt")
    for w in warnings:
        print(w)


# ----------------------------------------------------------------- cycle / approve / gate

def cycle_elapsed(st: dict, ev: list[dict]) -> str:
    """Wall-clock since the current cycle's cycle.started event, measured from the ledger, not guessed."""
    if not st.get("cycle"):
        return "n/a"
    started = latest(ev, "cycle.started", f"cycle-{st['cycle']:03d}")
    if not started:
        return "unknown"
    t0 = datetime.strptime(started["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    end_ev = latest(ev, "cycle.ended", f"cycle-{st['cycle']:03d}") if not st.get("cycle_open") else None
    t1 = datetime.strptime(end_ev["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if end_ev else datetime.now(timezone.utc)
    mins = int((t1 - t0).total_seconds() // 60)
    return f"{mins // 60}h{mins % 60:02d}m"


def cmd_cycle(args) -> None:
    ensure_scaffold()
    st = read_state()
    if args.action == "start":
        if st.get("cycle_open"):
            die(f"cycle {st['cycle']} is still open; end it first")
        st["cycle"] = st.get("cycle", 0) + 1
        st["cycle_open"] = True
        st["budget"] = args.budget or ""
        write_state(st)
        append_event("cycle.started", actor=args.actor, tier=args.tier, ref=f"cycle-{st['cycle']:03d}", summary=f"budget: {args.budget or 'unspecified'}")
        print(f"cycle {st['cycle']} started")
    else:
        if not st.get("cycle_open"):
            die("no open cycle")
        elapsed = cycle_elapsed(st, read_ledger())
        st["cycle_open"] = False
        write_state(st)
        append_event("cycle.ended", actor=args.actor, tier=args.tier, ref=f"cycle-{st['cycle']:03d}",
                     summary=(args.summary or "") + f" [elapsed {elapsed}, budget {st.get('budget') or 'unspecified'}]")
        print(f"cycle {st['cycle']} ended after {elapsed} (budget: {st.get('budget') or 'unspecified'})")


def cmd_approve(args) -> None:
    ensure_scaffold()
    if not args.quote:
        die("--quote is required: paste the CEO's words that constitute approval")
    ev = append_event(f"{args.what}.approved", actor="ceo", tier="ceo", ref=args.ref,
                      summary=args.quote, extra={"recorded_by": os.environ.get("TALOS_ACTOR", "unknown")})
    if args.what == "charter":
        p = CO / "charter.md"
        fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
        fm["status"] = "approved"
        fm["approved_event"] = ev["id"]
        write_lf(p, dump_frontmatter(fm, body), encoding="utf-8")
    print(ev["id"])


def latest(events: list[dict], kind: str, ref: str | None = None) -> dict | None:
    for e in reversed(events):
        if e["event"] == kind and (ref is None or e.get("ref") == ref):
            return e
    return None


def cmd_gate(args) -> None:
    ensure_scaffold()
    ev = read_ledger()
    if args.what in ("charter", "plan"):
        proposed = latest(ev, f"{args.what}.proposed")
        approved = latest(ev, f"{args.what}.approved")
        if not approved or (proposed and ev.index(approved) < ev.index(proposed)):  # ledger order, not 1-second timestamps
            die(f"GATE CLOSED: {args.what} not approved by CEO since last proposal", 1)
        print(f"gate open: {args.what} approved at {approved['ts']} ({approved['id']})")
    elif args.what == "design":
        teams = read_state().get("teams") or []
        if teams and "design" not in teams:
            print("gate open: no design team staffed (no user interface)")
            return
        waiver = latest(ev, "design-waiver.approved")
        if waiver:
            print(f"gate open: CEO waived the design gate ({waiver['id']}: {waiver.get('summary', '')})")
            return
        proposed = latest(ev, "design.proposed")
        approved = latest(ev, "design.approved")
        if not approved or (proposed and ev.index(approved) < ev.index(proposed)):  # ledger order, not 1-second timestamps
            die("GATE CLOSED: design direction and key screens not approved by CEO since last proposal", 1)
        print(f"gate open: design approved at {approved['ts']} ({approved['id']})")
    elif args.what == "release":
        approved = latest(ev, "release.approved", args.ref)
        if not approved:
            die(f"GATE CLOSED: release {args.ref or ''} not approved by CEO", 1)
        print(f"gate open: release approved {approved['id']}")
    elif args.what == "item":
        if not args.ref:
            die("--ref ITEM-xxxx required")
        verified = latest(ev, "item.verified", args.ref)
        if not verified or not verified.get("evidence"):
            die(f"GATE CLOSED: {args.ref} has no verification evidence from QA", 1)
        print(f"gate open: {args.ref} verified {verified['id']}")


# ----------------------------------------------------------------- lean context: brief status, events, context packs, spec lint

def status_brief(st: dict, ev: list[dict]) -> None:
    """A few lines a fresh phase session can start from instead of reading the record."""
    items = load_items()
    fm, _ = parse_frontmatter((CO / "charter.md").read_text(encoding="utf-8"))
    env_ok = (CO / "environment.md").exists() and "_not probed_" not in (CO / "environment.md").read_text(encoding="utf-8")
    plan = latest(ev, "plan.approved")
    by: dict[str, list[str]] = {}
    for it in items:
        by.setdefault(it.get("status", "?"), []).append(it["id"] + ("" if it.get("risk", "normal") == "normal" else f"({it['risk']})"))
    print(f"talos: cycle {st.get('cycle', 0)} {'open' if st.get('cycle_open') else 'closed'} | charter {fm.get('status', 'draft')} | "
          f"plan {'approved' if plan else 'not approved'} | environment {'probed' if env_ok else 'NOT probed'} | size {project_size()} | teams {','.join(st.get('teams') or ['all'])}")
    print("items: " + (" | ".join(f"{s} {', '.join(by[s])}" for s in ITEM_STATUSES if s in by) or "none"))
    print("CEO questions open: " + (", ".join(open_ceo_questions()) or "none"))
    for e in ev[-3:]:
        print(f"last: {e['ts'][5:16]} {e['actor']} {e['event']} {e.get('ref') or ''}".rstrip())


def cmd_size(args) -> None:
    """Print or set the project size that scales planning depth."""
    ensure_scaffold()
    if not args.size:
        s = project_size()
        print(f"{s} (spec budget {SIZES[s]['spec_lines']} lines, plan turn cap {SIZES[s]['plan_turns']})")
        return
    p = CO / "charter.md"
    fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    old = fm.get("size") or "medium"
    fm["size"] = args.size
    write_lf(p, dump_frontmatter(fm, body), encoding="utf-8")
    append_event("note", actor=args.actor, tier=args.tier, ref="company/charter.md", summary=f"project size {old} -> {args.size}")
    print(f"size: {args.size}")


def cmd_events(args) -> None:
    """One line per ledger event, for retros and phase sessions (cheaper than reading ledger.jsonl)."""
    ensure_scaffold()
    for e in read_ledger():
        if args.cycle is not None and e.get("cycle") != args.cycle:
            continue
        if args.type and not e["event"].startswith(args.type):
            continue
        ev = f" [evidence: {'; '.join(e['evidence'])}]" if e.get("evidence") else ""
        print(f"{e['id']} {e['ts'][5:16]} {e['actor']} {e['event']} {e.get('ref') or '-'}: {e.get('summary', '')}{ev}")


# Lesson tags each role should see, besides its own name, 'general' and the item id.
ROLE_TAGS = {
    "engineer": ["engineering", "implementation", "code"],
    "devops-engineer": ["devops", "infrastructure", "docker", "deploy"],
    "test-engineer": ["testing", "qa", "verification"],
    "technical-writer": ["docs", "documentation"],
    "ux-designer": ["ux", "design", "frontend"],
    "code-reviewer": ["review", "engineering", "code"],
    "security-reviewer": ["security", "review"],
    "chief-architect": ["architecture", "specs", "engineering"],
    "head-of-qa": ["testing", "qa"],
}

HANDBACK = """```
ITEM: {item}
STATUS: completed | blocked | needs_question
BRANCH: vc/{item_lower}
COMMIT: <hash>
CHANGED: <files>
EVIDENCE: <test command and result, or artefact path>
QUESTIONS: <none, or exact questions with options>
NOTES: <anything the reviewer must know>
```"""


def _demote(text: str) -> str:
    """Push embedded headings one level down so the pack keeps one outline."""
    return re.sub(r"^(#{1,4}) ", lambda m: "##" + m.group(1) + " ", text.strip(), flags=re.M)


def _file_for(folder: str, ident: str) -> Path | None:
    hits = sorted((CO / folder).glob(f"{ident}*.md")) or sorted((CO / folder).glob(f"{ident.lower()}*.md"))
    return hits[0] if hits else None


def cmd_context(args) -> None:
    """Write one file holding exactly what a role needs for one item."""
    ensure_scaffold()
    ip = item_path(args.item_id)
    item_text = ip.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(item_text)
    parts = [f"# Context pack: {args.item_id} for {args.role}", "",
             f"_Generated {now()} by `talos context`. Work from this file; do not read the rest of `company/`. "
             "If something you need is missing, say so in your hand-back instead of searching for it._", "",
             "## Item", "", _demote(parse_frontmatter(item_text)[1]), ""]
    spec_text = ""
    sp = None
    ref = str(fm.get("spec") or "")
    if ref and (ROOT / ref).is_file():
        sp = ROOT / ref
    elif re.search(r"SPEC-\d{4}", ref):
        sp = _file_for("specs", re.search(r"SPEC-\d{4}", ref).group(0))
    if not sp:
        sp = next((p for p in sorted((CO / "specs").glob("SPEC-*.md"))
                   if parse_frontmatter(p.read_text(encoding="utf-8"))[0].get("item") == args.item_id), None)
    if sp:
        if True:
            spec_text = sp.read_text(encoding="utf-8")
            parts += [f"## Spec ({sp.relative_to(ROOT).as_posix()})", "", _demote(parse_frontmatter(spec_text)[1]), ""]
    adrs = sorted(set(re.findall(r"\bADR-\d{4}\b", item_text + spec_text)))
    if adrs:
        parts += ["## Decisions referenced", ""]
    for a in adrs:
        ap = _file_for("decisions", a)
        if ap:
            afm, abody = parse_frontmatter(ap.read_text(encoding="utf-8"))
            m = re.search(r"^## Decision\s*\n(.*?)(?=^## |\Z)", abody, re.M | re.S)
            ruling = (m.group(1).strip() if m else abody.strip()).replace("\n#", "\n####")
            parts += [f"### {a}: {afm.get('title', '')}", "", ruling, f"_(full record: {ap.relative_to(ROOT).as_posix()})_", ""]
    envp = CO / "environment.md"
    if envp.exists():
        parts += ["## Environment", "", _demote(parse_frontmatter(envp.read_text(encoding="utf-8"))[1]), ""]
    want = {args.role, "general", args.item_id.lower(), args.item_id} | set(ROLE_TAGS.get(args.role, []))
    rank = {"high": 0, "medium": 1, "low": 2}
    lessons = []
    for p in (CO / "knowledge").glob("lesson-*.md"):
        lfm, lbody = parse_frontmatter(p.read_text(encoding="utf-8"))
        tags = lfm.get("applies_to") or []
        tags = [tags] if isinstance(tags, str) else tags
        if want & {t.strip().lower() for t in tags} or args.item_id in lbody:
            lessons.append((rank.get(lfm.get("confidence"), 3), lfm.get("recorded", ""), lbody.strip()))
    lessons.sort(key=lambda x: (x[0], [-ord(c) for c in x[1]]))
    if lessons:
        parts += ["## Lessons that apply", ""] + [b + "\n" for _, _, b in lessons[:args.max_lessons]]
    if args.role in ("engineer", "devops-engineer", "technical-writer", "ux-designer"):
        parts += ["## Hand-back (return exactly this block)", "", HANDBACK.format(item=args.item_id, item_lower=args.item_id.lower()), ""]
    out = Path(args.out) if args.out else CO / ".context" / f"{args.item_id}-{args.role}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_lf(out, "\n".join(parts).rstrip("\n") + "\n", encoding="utf-8")
    words = len(" ".join(parts).split())
    print(f"{out.resolve().as_posix()} ({words} words, {len(adrs)} decisions, {min(len(lessons), args.max_lessons)} lessons)")


SPEC_SECTIONS = ["## Goal", "## Non-goals", "## Files and modules in scope", "## Acceptance criteria"]
RESULT_WORDS = re.compile(r"\b(prints?|exits?|returns?|passe[sd]|fails?|shows?|contains?|equals?|outputs?|responds?|status)\b|->|→|=>", re.I)


def lint_spec(path: Path, max_lines: int = 120) -> tuple[list[str], list[str]]:
    """Mechanical checks of the handoff contract. Returns (errors, warnings)."""
    text = path.read_text(encoding="utf-8")
    errors, warnings = [], []
    _, body = parse_frontmatter(text)
    for sec in SPEC_SECTIONS:
        if not re.search(rf"^{re.escape(sec)}\b", body, re.M):
            errors.append(f"missing section '{sec}'")
    prose, fence = 0, False
    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence and line.strip():
            prose += 1
    if prose > max_lines:
        errors.append(f"{prose} non-blank lines outside code blocks; the budget is {max_lines} (move detail into verbatim blocks or split the item)")
    sections = re.split(r"^(## .+)$", body, flags=re.M)
    sec = {sections[i].strip(): sections[i + 1] for i in range(1, len(sections) - 1, 2)}
    acc = next((v for k, v in sec.items() if k.startswith("## Acceptance")), "")
    lines = [l.strip() for l in acc.splitlines() if re.match(r"\s*- \[[ x]\]", l)]
    if not lines or all(re.fullmatch(r"- \[[ x]\]\s*", l) for l in lines):
        errors.append("no acceptance criteria")
    executed_note = bool(re.search(r"(?<![a-z])executed\b", acc, re.I))  # "_Executed by ..." counts; "UNEXECUTED" does not
    for n, l in enumerate(lines, 1):
        if re.fullmatch(r"- \[[ x]\]\s*", l):
            continue
        if "UNEXECUTED" in l:
            continue
        if "`" not in l:
            errors.append(f"acceptance line {n} has no command or test name in backticks: {l[:70]}")
        elif not RESULT_WORDS.search(l):
            errors.append(f"acceptance line {n} names no expected result (prints, exits, returns, passes ...): {l[:70]}")
    if lines and not executed_note and not all("UNEXECUTED" in l for l in lines if not re.fullmatch(r"- \[[ x]\]\s*", l)):
        errors.append("acceptance section does not say the architect executed the lines; mark each line it could not run UNEXECUTED")
    scope = next((v for k, v in sec.items() if k.startswith("## Files and modules")), "")
    for l in scope.splitlines():
        low = l.lower()
        if "do not touch" in low or "not touch" in low or re.search(r"\bnew\b", low):
            continue
        for tok in re.findall(r"`([^`]+)`", l):
            if ("/" in tok or re.search(r"\.\w{1,5}$", tok)) and not re.search(r"[*?<>{}\s]", tok) and not (ROOT / tok).exists():
                warnings.append(f"file in scope does not exist and is not marked new: {tok}")
    for ref in sorted(set(re.findall(r"\bADR-\d{4}\b", body))):
        if not _file_for("decisions", ref):
            errors.append(f"references {ref}, which is not in company/decisions/")
    for ref in sorted(set(re.findall(r"\bLESSON-\d{4}\b", body))):
        if not _file_for("knowledge", ref):
            errors.append(f"references {ref}, which is not in company/knowledge/")
    return errors, warnings


def cmd_spec_lint(args) -> None:
    ensure_scaffold()
    targets = []
    for s in args.specs or ["all"]:
        if s == "all":
            targets += sorted(p for p in (CO / "specs").glob("SPEC-*.md"))
        else:
            p = Path(s) if Path(s).exists() else _file_for("specs", s)
            if not p:
                die(f"spec {s} not found")
            targets.append(p)
    bad = 0
    for p in targets:
        errors, warnings = lint_spec(p, args.max_lines or SIZES[project_size()]["spec_lines"])
        mark = "FAIL" if errors else "ok"
        print(f"{mark}  {p.relative_to(ROOT).as_posix() if p.is_absolute() and ROOT in p.parents else p}")
        for e in errors:
            print(f"   error: {e}")
        for w in warnings:
            print(f"   warn:  {w}")
        bad += bool(errors)
    if bad:
        sys.exit(1)


# ----------------------------------------------------------------- usage (token spend)

def load_usage(cycle: int | None = None):
    """Usage records from Claude Code transcripts, tagged with their cycle. Fails soft."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import usage as U
    recs, why = U.collect(ROOT, os.environ.get("TALOS_TRANSCRIPTS"))
    if recs:
        U.assign_cycles(recs, read_ledger())
        if cycle is not None:
            recs = [r for r in recs if r["cycle"] == cycle]
            if not recs:
                why = f"no usage recorded in cycle {cycle}"
    return U, recs, why


def verified_count(cycle: int | None) -> int:
    return len({e["ref"] for e in read_ledger()
                if e["event"] == "item.verified" and e.get("ref") and (cycle is None or e.get("cycle") == cycle)})


def spend_lines(cycle: int | None) -> list[str]:
    """The Spend section of a cycle report: measured tokens, never an estimate."""
    U, recs, why = load_usage(cycle)
    if why:
        return [f"- _Usage unavailable: {why}._"]
    grand = sum(U.total(r) for r in recs)
    t = {f: sum(r[f] for r in recs) for f in U.FIELDS}
    pct = lambda n: f"{100 * n / grand:.0f}%" if grand else "0%"
    by_model = U.summarize(recs, lambda r: U.family(r["model"]))
    by_role = U.summarize(recs, lambda r: r["role"])
    n_ver = verified_count(cycle)
    lines = [f"- Tokens processed: **{U.millions(grand)}M** (cache read {U.millions(t['read'])}M, cache write {U.millions(t['write'])}M, "
             f"fresh input {U.millions(t['fresh'])}M, output {U.millions(t['out'])}M) over {len(recs)} model calls.",
             "- By model: " + ", ".join(f"{g['key']} {pct(g['total'])}" for g in by_model) + ".",
             "- Top roles: " + ", ".join(f"{g['key']} {pct(g['total'])}" for g in by_role[:3]) + ".",
             f"- Per verified item: " + (f"{U.millions(grand // n_ver)}M ({n_ver} verified)." if n_ver else "_no items verified_.")]
    if cycle is not None:
        retro_done = any(e["event"] == "retro.completed" and e.get("cycle") == cycle for e in read_ledger())
        if not retro_done:
            lines[0] = lines[0].replace("- Tokens processed:", "- Tokens processed **at close, before the retro** (provisional):")
        lines.append(f"- Cycle {cycle} counts from its start to the next cycle's start, so it includes its retro; kickoff and planning are cycle 0. "
                     f"The retro records the final figure and the budget verdict. Details: `talos usage --cycle {cycle}`.")
    return lines


def cmd_usage(args) -> None:
    ensure_scaffold()
    U, recs, why = load_usage(args.cycle)
    if why:
        print(f"talos usage: {why}")
        return
    keys = {
        "role": (lambda r: (r["role"], U.family(r["model"])), ["Role", "Model"]),
        "model": (lambda r: (U.family(r["model"]),), ["Model"]),
        "item": (lambda r: (r["item"],), ["Item"]),
        "cycle": (lambda r: (str(r["cycle"]),), ["Cycle"]),
    }
    keyf, heads = keys[args.by]
    rows = U.summarize(recs, keyf)
    grand = sum(g["total"] for g in rows)
    if args.json:
        for g in rows:
            g["key"] = list(g["key"])
        print(json.dumps({"cycle": args.cycle, "by": args.by, "total": grand, "verified_items": verified_count(args.cycle), "rows": rows}, indent=2))
        return
    scope = f"cycle {args.cycle}" if args.cycle is not None else "all cycles"
    print(f"# Token usage, {scope}, by {args.by} (millions of tokens, measured from transcripts)\n")
    print("| " + " | ".join(heads + ["Calls", "Cache read", "Cache write", "Fresh in", "Output", "Total", "Share"]) + " |")
    print("|" + "---|" * len(heads) + "---:|" * 7)
    for g in rows:
        share = f"{100 * g['total'] / grand:.1f}%" if grand else "0%"
        print("| " + " | ".join(list(g["key"]) + [str(g["calls"]), U.millions(g["read"]), U.millions(g["write"]),
                                                    U.millions(g["fresh"]), U.millions(g["out"]), U.millions(g["total"]), share]) + " |")
    print(f"| **Total** |" + " |" * (len(heads) - 1) + f" {sum(g['calls'] for g in rows)} | {U.millions(sum(g['read'] for g in rows))} | "
          f"{U.millions(sum(g['write'] for g in rows))} | {U.millions(sum(g['fresh'] for g in rows))} | {U.millions(sum(g['out'] for g in rows))} | {U.millions(grand)} | 100% |")
    n_ver = verified_count(args.cycle)
    if n_ver:
        print(f"\nPer verified item: {U.millions(grand // n_ver)}M tokens ({n_ver} verified in {scope}).")
    print("\nCache reads are billed far below fresh input; compare runs on the same columns, not on Total alone.")


# ----------------------------------------------------------------- status / report / journal

def cmd_status(args) -> None:
    ensure_scaffold()
    st = read_state()
    ev = read_ledger()
    items = load_items()
    if args.brief:
        status_brief(st, ev)
        return
    fm, _ = parse_frontmatter((CO / "charter.md").read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for it in items:
        counts[it.get("status", "?")] = counts.get(it.get("status", "?"), 0) + 1
    ceo_q = open_ceo_questions()
    all_open = len(re.findall(r"^### Q-\d+", QUESTIONS.read_text(encoding="utf-8").split("## Answered")[0], re.M)) if QUESTIONS.exists() else 0
    plan = latest(ev, "plan.approved")
    env_ok = (CO / "environment.md").exists() and "_not probed_" not in (CO / "environment.md").read_text(encoding="utf-8")
    print("# Company status\n")
    print(f"- Charter: **{fm.get('status', 'draft')}**")
    print(f"- Plan: **{'approved ' + plan['ts'] if plan else 'not approved'}**")
    print(f"- Environment: **{'probed' if env_ok else 'NOT probed (run the kickoff environment step)'}**")
    print(f"- Cycle: **{st.get('cycle', 0)}** ({'open' if st.get('cycle_open') else 'closed'}), budget: {st.get('budget') or 'n/a'}, elapsed (from ledger): {cycle_elapsed(st, ev)}")
    if not args.no_spend:
        U, recs, why = load_usage(st.get("cycle", 0))
        if why:
            print(f"- Spend this cycle: _unavailable: {why}_")
        else:
            grand = sum(U.total(r) for r in recs)
            fams = U.summarize(recs, lambda r: U.family(r["model"]))
            print(f"- Spend this cycle (measured): **{U.millions(grand)}M tokens**, " + ", ".join(f"{g['key']} {100 * g['total'] / grand:.0f}%" for g in fams if grand))
    print(f"- Backlog: " + (", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "empty"))
    print(f"- Open questions for CEO: **{len(ceo_q)}** ({all_open - len(ceo_q)} open for other roles)")
    lessons = len(list((CO / "knowledge").glob("lesson-*.md")))
    print(f"- Lessons recorded: {lessons}")
    print("\n## Blocked items\n")
    blocked = [i for i in items if i.get("status") == "blocked"]
    print("\n".join(f"- {i['id']} {i['title']} (owner: {i.get('owner') or '-'})" for i in blocked) or "_none_")
    print("\n## Last 10 events\n")
    for e in ev[-10:]:
        print(f"- `{e['ts']}` {e['actor']} · {e['event']} · {e.get('ref') or ''} — {e.get('summary', '')}")


def cmd_report(args) -> None:
    ensure_scaffold()
    st = read_state()
    cycle = args.cycle or st.get("cycle", 0)
    ev = [e for e in read_ledger() if e.get("cycle") == cycle]
    items = {i["id"]: i for i in load_items()}
    name = CO / "reports" / f"cycle-{cycle:03d}.md"

    def refs(kind):
        return sorted({e["ref"] for e in ev if e["event"] == kind and e.get("ref")})

    lines = [f"# Cycle {cycle} report", "", f"_Generated {now()} by `talos report`. The Chief of Staff edits the summary; the lists below come from the ledger._", "",
             "## Summary", "", "_Chief of Staff: two or three sentences on what this cycle achieved and what needs the CEO._", "",
             "## Needs your decision", ""]
    # Open questions are listed regardless of the cycle they were asked in: an unanswered
    # CEO question from cycle 1 still needs an answer in cycle 3.
    all_ev = read_ledger()
    answered = {e["ref"] for e in all_ev if e["event"] == "question.answered"}
    asked = {e["ref"]: e for e in all_ev if e["event"] == "question.asked"}
    open_ceo = set(open_ceo_questions())
    qs = [asked[q] for q in sorted(open_ceo) if q in asked]
    lines += [f"- **{e['ref']}** {e['summary']}" for e in qs] or ["_none_"]
    other_q = [e for r, e in sorted(asked.items()) if r not in answered and r not in open_ceo]
    if other_q:
        lines += ["", "_Open for other roles (no action from you):_ " + ", ".join(f"{e['ref']} ({e.get('audience')})" for e in other_q)]
    lines += ["", "## Ready to merge (verified by QA)", ""]
    for r in refs("item.verified"):
        it = items.get(r, {})
        lines.append(f"- {r} {it.get('title', '')} — branch `{it.get('branch') or '?'}`" + (f" @ `{it['commit']}`" if it.get("commit") else ""))
    if not refs("item.verified"):
        lines.append("_none_")
    lines += ["", "## Where the product is", ""]
    try:
        base = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
        if base in ("", "HEAD"):  # detached or unborn: fall back to the symbolic ref name
            base = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip() or "?"
    except Exception:
        base = "?"
    lines.append(f"- Repository: `{ROOT}` (base branch `{base}`). Verified work is on the branches above and is **not** on `{base}` until you approve the release.")
    lines.append("- How to run and test it: see `company/environment.md`.")
    lines += ["", "## Completed, awaiting verification", ""]
    pending = [r for r in refs("item.completed") if r not in refs("item.verified")]
    lines += [f"- {r} {items.get(r, {}).get('title', '')}" for r in pending] or ["_none_"]
    lines += ["", "## Blocked", ""]
    lines += [f"- {r} {items.get(r, {}).get('title', '')}" for r in refs("item.blocked") if items.get(r, {}).get("status") == "blocked"] or ["_none_"]
    lines += ["", "## Decisions recorded", ""]
    lines += [f"- {e['ref']} {e['summary']}" for e in ev if e["event"] == "decision.recorded"] or ["_none_"]
    lines += ["", "## Lessons recorded", ""]
    lines += [f"- {e['ref']} {e['summary']}" for e in ev if e["event"] == "lesson.recorded"] or ["_none_"]
    lines += ["", "## Budget", ""]
    lines.append(f"- Elapsed (from ledger): {cycle_elapsed(st, all_ev)}; budget: {st.get('budget') or 'unspecified'}")
    lines += [f"- {e['summary']}" for e in ev if e["event"] == "budget.consumed"] or ["- _no budget.consumed events logged_"]
    lines += ["", "## Spend (measured from transcripts)", ""]
    lines += spend_lines(cycle)
    write_lf(name, "\n".join(lines) + "\n", encoding="utf-8")
    print(name.relative_to(ROOT).as_posix())


def cmd_journal(args) -> None:
    ensure_scaffold()
    ev = read_ledger()
    days: dict[str, list[dict]] = {}
    for e in ev:
        d = e["ts"][:10]
        if args.date and d != args.date:
            continue
        days.setdefault(d, []).append(e)
    for d, evs in days.items():
        lines = [f"# Journal — {d}", ""]
        for e in evs:
            ref = f" `{e['ref']}`" if e.get("ref") else ""
            evid = "".join(f"\n  - evidence: {x}" for x in e.get("evidence", []))
            lines.append(f"- **{e['ts'][11:19]}** {e['actor']} ({e['tier']}) — {e['event']}{ref}: {e.get('summary', '')}{evid}")
        write_lf((CO / "journal" / f"{d}.md"), "\n".join(lines) + "\n", encoding="utf-8")
    print(f"journal: {len(days)} day(s) rendered")


# ----------------------------------------------------------------- argparse

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="talos", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--actor", help="role making the entry (default: $TALOS_ACTOR)")
        sp.add_argument("--tier", choices=sorted(TIERS), help="role tier (default: $TALOS_TIER)")

    s = sub.add_parser("init"); s.add_argument("--brief"); s.add_argument("--teams", help="comma-separated teams staffed (recorded by init.py)"); s.set_defaults(fn=cmd_init)

    s = sub.add_parser("log"); common(s)
    s.add_argument("event"); s.add_argument("--ref"); s.add_argument("--summary"); s.add_argument("--evidence", action="append"); s.add_argument("--branch")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("ask"); common(s)
    s.add_argument("question"); s.add_argument("--ref"); s.add_argument("--context"); s.add_argument("--options")
    s.add_argument("--for", dest="audience", default="ceo", choices=AUDIENCES, help="who must answer (default ceo); technical questions go to architect")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("answer"); s.add_argument("qid"); s.add_argument("answer")
    s.add_argument("--by", help="who answered (default ceo). Use the role name for non-CEO questions, e.g. chief-architect")
    s.add_argument("--tier", choices=sorted(TIERS))
    s.set_defaults(fn=cmd_answer)

    it = sub.add_parser("item"); itsub = it.add_subparsers(dest="sub", required=True)
    s = itsub.add_parser("new"); common(s)
    s.add_argument("--title", required=True); s.add_argument("--description"); s.add_argument("--owner"); s.add_argument("--spec")
    s.add_argument("--priority", choices=["P0", "P1", "P2", "P3"]); s.add_argument("--acceptance", action="append")
    s.add_argument("--risk", choices=RISKS, help="review depth: low skips the Opus reviewers (default normal)")
    s.set_defaults(fn=cmd_item_new)
    s = itsub.add_parser("set"); common(s)
    s.add_argument("item_id"); s.add_argument("--status", choices=ITEM_STATUSES); s.add_argument("--owner"); s.add_argument("--spec")
    s.add_argument("--branch"); s.add_argument("--commit", help="commit hash the evidence refers to"); s.add_argument("--priority")
    s.add_argument("--risk", choices=RISKS)
    s.add_argument("--acceptance", action="append", help="append an acceptance criterion (repeatable)")
    s.add_argument("--evidence", action="append"); s.add_argument("--summary")
    s.set_defaults(fn=cmd_item_set)
    s = itsub.add_parser("list"); s.add_argument("--status"); s.set_defaults(fn=cmd_item_list)
    s = itsub.add_parser("show"); s.add_argument("item_id"); s.set_defaults(fn=cmd_item_show)

    sp = sub.add_parser("spec"); spsub = sp.add_subparsers(dest="sub", required=True)
    s = spsub.add_parser("new"); common(s); s.add_argument("--title", required=True); s.add_argument("--item"); s.set_defaults(fn=cmd_spec_new)
    s = spsub.add_parser("lint", help="check specs against the handoff contract; exit 1 on errors"); s.add_argument("specs", nargs="*", help="SPEC ids or paths (default all)")
    s.add_argument("--max-lines", type=int, help="default: from the project size (small 60, medium 120, large 160)"); s.set_defaults(fn=cmd_spec_lint)
    s = sub.add_parser("size", help="print or set the project size (scales planning depth)"); common(s)
    s.add_argument("size", nargs="?", choices=list(SIZES)); s.set_defaults(fn=cmd_size)

    d = sub.add_parser("decision"); dsub = d.add_subparsers(dest="sub", required=True)
    s = dsub.add_parser("add"); common(s)
    s.add_argument("--title", required=True); s.add_argument("--status", default="proposed", choices=["proposed", "accepted", "superseded"])
    s.add_argument("--context"); s.add_argument("--decision"); s.add_argument("--consequences"); s.add_argument("--alternatives")
    s.set_defaults(fn=cmd_decision_add)

    le = sub.add_parser("lesson"); lesub = le.add_subparsers(dest="sub", required=True)
    s = lesub.add_parser("add"); common(s)
    s.add_argument("--title", required=True); s.add_argument("--body", required=True); s.add_argument("--why"); s.add_argument("--apply")
    s.add_argument("--applies-to", dest="applies_to", action="append"); s.add_argument("--evidence", action="append")
    s.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    s.set_defaults(fn=cmd_lesson_add)

    s = sub.add_parser("cycle"); common(s); s.add_argument("action", choices=["start", "end"]); s.add_argument("--budget"); s.add_argument("--summary"); s.set_defaults(fn=cmd_cycle)

    s = sub.add_parser("approve"); s.add_argument("what", choices=["charter", "plan", "release", "design", "design-waiver"]); s.add_argument("--ref"); s.add_argument("--quote", required=True)
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("gate"); s.add_argument("what", choices=["charter", "plan", "design", "release", "item"]); s.add_argument("--ref"); s.set_defaults(fn=cmd_gate)

    s = sub.add_parser("status"); s.add_argument("--no-spend", action="store_true", help="skip reading transcripts (used by the session hook)")
    s.add_argument("--brief", action="store_true", help="four lines: state, items by status, CEO questions, last events"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("events", help="one line per ledger event"); s.add_argument("--cycle", type=int); s.add_argument("--type", help="event type prefix, e.g. review or item.")
    s.set_defaults(fn=cmd_events)
    s = sub.add_parser("context", help="write a context pack: what one role needs for one item"); s.add_argument("item_id"); s.add_argument("--role", required=True)
    s.add_argument("--out", help="output path (default company/.context/<item>-<role>.md)"); s.add_argument("--max-lessons", type=int, default=8); s.set_defaults(fn=cmd_context)
    s = sub.add_parser("usage", help="measured token usage from Claude Code transcripts")
    s.add_argument("--cycle", type=int, help="only this cycle (0 = kickoff and planning)")
    s.add_argument("--by", choices=["role", "model", "item", "cycle"], default="role")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_usage)
    s = sub.add_parser("report"); s.add_argument("--cycle", type=int); s.set_defaults(fn=cmd_report)
    s = sub.add_parser("journal"); s.add_argument("--date"); s.set_defaults(fn=cmd_journal)
    s = sub.add_parser("consolidate"); s.set_defaults(fn=cmd_consolidate)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
