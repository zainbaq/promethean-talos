"""
usage.py: token usage per role, model, item and cycle, read from Claude Code transcripts.

Standard library only. Claude Code writes one JSONL transcript per session under
~/.claude/projects/<project-slug>/, and one per subagent under
<session-id>/subagents/agent-*.jsonl with a sibling .meta.json naming the agent
type (the Talos role). Assistant lines carry message.id, message.model and
message.usage. Streaming can repeat a message, so usage is counted once per id.

The transcript layout is not a public contract. Everything here fails soft:
callers get an empty result and a reason, never an exception.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

ITEM_RE = re.compile(r"\bITEM-\d{4}\b")
MAIN = "main session"
FIELDS = ("fresh", "write", "read", "out")


def projects_dir() -> Path:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return Path(base) / "projects"


def project_slug(root) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(root).resolve()))


def transcript_dirs(root, override=None) -> list:
    """The project's transcript folder, plus folders of sessions run inside its worktrees."""
    if override:
        p = Path(override)
        return [p] if p.is_dir() else []
    base = projects_dir()
    if not base.is_dir():
        return []
    slug = project_slug(root).lower()
    out = []
    for d in base.iterdir():
        n = d.name.lower()
        if d.is_dir() and (n == slug or n.startswith(slug + "--claude-worktrees-") or n.startswith(slug + "-wt-")):
            out.append(d)
    return sorted(out)


def family(model: str) -> str:
    m = (model or "").lower()
    for f in ("fable", "mythos", "opus", "sonnet", "haiku"):
        if f in m:
            return f
    return m or "?"


def _first_prompt(path: Path) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") == "user":
                    c = (d.get("message") or {}).get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    return c if isinstance(c, str) else ""
    except OSError:
        pass
    return ""


def _item_of(prompt: str) -> str:
    ids = sorted(set(ITEM_RE.findall(prompt)))
    if len(ids) == 1:
        return ids[0]
    return "several" if ids else "-"


def _scan(path: Path, role: str, item: str, seen: set, out: list) -> None:
    try:
        f = open(path, encoding="utf-8")
    except OSError:
        return
    with f:
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") or {}
            u, mid = m.get("usage"), m.get("id")
            if not isinstance(u, dict) or not mid or mid in seen or m.get("model") == "<synthetic>":
                continue
            seen.add(mid)
            out.append({
                "ts": (d.get("timestamp") or "")[:19],
                "role": role, "model": m.get("model") or "?", "item": item,
                "fresh": int(u.get("input_tokens") or 0),
                "write": int(u.get("cache_creation_input_tokens") or 0),
                "read": int(u.get("cache_read_input_tokens") or 0),
                "out": int(u.get("output_tokens") or 0),
            })


def collect(root, override=None):
    """Return (records, reason). reason is None when transcripts were found."""
    dirs = transcript_dirs(root, override)
    if not dirs:
        return [], f"no Claude Code transcripts for this project yet (looked in {override or projects_dir()})"
    recs, seen = [], set()
    try:
        for d in dirs:
            for main in sorted(d.glob("*.jsonl")):
                _scan(main, MAIN, "-", seen, recs)
                for sub in sorted((d / main.stem / "subagents").glob("*.jsonl")):
                    role = "?"
                    meta = sub.with_suffix(".meta.json")
                    try:
                        role = json.loads(meta.read_text(encoding="utf-8")).get("agentType") or "?"
                    except (OSError, ValueError, AttributeError):
                        pass
                    _scan(sub, role, _item_of(_first_prompt(sub)), seen, recs)
    except Exception as e:  # layout changed in a way we did not expect
        return [], f"usage unavailable: {type(e).__name__}: {e}"
    if not recs:
        return [], "transcripts found but they contain no usage records"
    return recs, None


def assign_cycles(recs: list, ledger: list) -> None:
    """Cycle N runs from its cycle.started event to the next one, so it includes its retro.
    Everything before cycle 1 (kickoff, charter, plan) is cycle 0."""
    starts = sorted((e["ts"][:19], int(e.get("cycle") or 0)) for e in ledger if e.get("event") == "cycle.started")
    for r in recs:
        c = 0
        for ts, n in starts:
            if r["ts"] and r["ts"] >= ts:
                c = n
        r["cycle"] = c


def total(r: dict) -> int:
    return r["fresh"] + r["write"] + r["read"] + r["out"]


def summarize(recs: list, key) -> list:
    """Group records by key(r); rows sorted by total tokens, largest first."""
    groups = {}
    for r in recs:
        k = key(r)
        g = groups.setdefault(k, {"key": k, "calls": 0, "fresh": 0, "write": 0, "read": 0, "out": 0})
        g["calls"] += 1
        for f in FIELDS:
            g[f] += r[f]
    rows = list(groups.values())
    for g in rows:
        g["total"] = sum(g[f] for f in FIELDS)
    rows.sort(key=lambda g: -g["total"])
    return rows


def millions(n: int) -> str:
    return f"{n / 1e6:.2f}"
