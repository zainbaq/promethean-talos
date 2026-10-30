import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"


def test_transcripts_equal_cli(tmp_path, monkeypatch, activity, record_copy, read_ledger, transcripts):
    proj = record_copy(tmp_path)
    cfg = transcripts(tmp_path, "engineer-active", proj, 30)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    ledger = read_ledger(proj)
    s = activity.spend(ledger, 1, proj)
    env = dict(os.environ, TALOS_ROOT=str(proj), CLAUDE_CONFIG_DIR=str(cfg))
    env.pop("TALOS_TRANSCRIPTS", None)
    out = subprocess.run([sys.executable, str(REPO / "talos.py"), "usage", "--cycle", "1", "--json"],
                         env=env, capture_output=True, text=True, check=True, cwd=str(proj))
    cli_total = json.loads(out.stdout)["total"]
    assert cli_total > 0
    tokens = s["transcripts"]["tokens"]
    assert tokens == cli_total
    assert f"{tokens / 1e6:.2f}" == f"{cli_total / 1e6:.2f}"
    assert s["source"] == "events+transcripts" and s["cycle"] == 1
    assert s["transcripts"]["available"] is True and s["transcripts"]["calls"] > 0
    assert {r["role"] for r in s["transcripts"]["by_role"]} == {"main session", "engineer"}


def test_events_only(tmp_path, monkeypatch, activity, record_copy, read_ledger):
    proj = record_copy(tmp_path)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing"))
    s = activity.spend(read_ledger(proj), 1, proj)
    assert s["source"] == "events-only"
    ev = s["events"]
    assert ev["runs"] == 5 and abs(ev["cost_usd"] - 12.888437) < 0.0005 and ev["tokens"] == 542386
    assert f"{ev['cost_usd']:.2f}" == "12.89"
    assert len(ev["by_phase"]) == 4
    costs = [r["cost_usd"] for r in ev["by_phase"]]
    assert costs == sorted(costs, reverse=True)
    # NOTE: SPEC-0002 also asserts by_phase[0] is cycle-build/fable; the ledger and ADR-0007
    # ordering give cycle-close/sonnet (6.66) first. Raised as a question, not asserted.
    t = s["transcripts"]
    assert t["available"] is False and isinstance(t["reason"], str)
    assert t["tokens"] is None and t["calls"] is None and t["by_role"] == []
