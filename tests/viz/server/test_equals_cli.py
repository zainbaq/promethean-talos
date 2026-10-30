"""The snapshot equals what the CLI says about the same record (ADR-0003 point 2)."""
from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from viz import snapshot as S

from .conftest import REPO, cli


def oracle(root):
    status = cli(root, "status", "--no-spend")
    assert status.returncode == 0, status.stderr
    brief = cli(root, "status", "--brief")
    assert brief.returncode == 0, brief.stderr
    out = status.stdout
    cyc = re.search(r"^- Cycle: \*\*(\d+)\*\* \((open|closed)\)", out, re.M)
    backlog = re.search(r"^- Backlog: (.*)$", out, re.M).group(1).strip()
    q = re.search(r"^- Open questions for CEO: \*\*(\d+)\*\* \((\d+) open for other roles\)", out, re.M)
    lessons = re.search(r"^- Lessons recorded: (\d+)", out, re.M)
    head = re.search(r"^talos: cycle (\d+) (open|closed) \| charter (\w+)", brief.stdout, re.M)
    items = {} if backlog == "empty" else {k: int(v) for k, v in re.findall(r"(\w+) (\d+)", backlog)}
    return {
        "cycle": int(cyc.group(1)), "open": cyc.group(2) == "open", "items": items,
        "ceo": int(q.group(1)), "other": int(q.group(2)), "lessons": int(lessons.group(1)),
        "brief_cycle": int(head.group(1)), "brief_open": head.group(2) == "open", "charter": head.group(3),
    }


def check(root):
    """root = directory holding company/. Reads the oracle, then the snapshot, then compares."""
    o = oracle(root)
    now = datetime.now(timezone.utc)
    s = S.build(root, root / "company", now=now, version=1, checked_at=now)
    assert s["errors"] == []
    assert s["cycle"]["number"] == o["cycle"] == o["brief_cycle"]
    assert s["cycle"]["open"] is o["open"] is o["brief_open"]
    nonzero = {k: v for k, v in s["counts"]["items"].items() if v and k != "total"}
    assert nonzero == o["items"]
    assert s["counts"]["items"]["total"] == sum(o["items"].values())
    assert s["counts"]["ceo_questions_open"] == o["ceo"]
    assert s["counts"]["other_questions_open"] == o["other"]
    assert s["counts"]["lessons"] == o["lessons"]
    assert s["charter"]["status"] == o["charter"]

    waiting = {w["key"] for w in s["waiting"] if w["kind"] == "gate"}
    for gate in ("charter", "plan", "design"):
        code = cli(root, "gate", gate).returncode
        assert (f"gate:{gate}" in waiting) == (code == 1), f"gate {gate}: exit {code}, waiting {sorted(waiting)}"
    for it in s["items"]:
        if it["status"] == "verified":
            code = cli(root, "gate", "release", "--ref", it["id"]).returncode
            assert (f"gate:release:{it['id']}" in waiting) == (code == 1), it["id"]
    return s


def test_fixture_copy(record_root):
    s = check(record_root)
    assert {w["key"] for w in s["waiting"]} == {"gate:release:ITEM-0001", "gate:release:ITEM-0002"}


def test_live_record():
    if not (REPO / "company" / "ledger.jsonl").is_file():
        pytest.skip("no company/ record in this checkout (the framework repo is the template)")
    s = check(REPO)
    assert s["project"]["name"]
