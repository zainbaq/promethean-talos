"""Fixtures for the activity and spend tests (ADR-0006 points 2 and 3)."""
import importlib.util
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3] / "template" / "tools" / "talos"
USAGE_PY = REPO / "usage.py"
CASES = REPO.parents[2] / "tests" / "viz" / "fixtures" / "transcripts"
RECORD_FIXTURE = REPO.parents[2] / "tests" / "viz" / "fixtures" / "sample-company"

if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_usage():
    spec = importlib.util.spec_from_file_location("talos_usage_tests", USAGE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def usage():
    return _load_usage()


@pytest.fixture
def activity():
    from viz import activity as mod
    return mod


@pytest.fixture
def transcripts(usage):
    """transcripts(tmp_path, case, root, age_seconds, worktree=False) -> CLAUDE_CONFIG_DIR value."""
    def install(tmp_path, case, root, age_seconds, worktree=False) -> Path:
        slug = usage.project_slug(root).lower()
        if worktree:
            slug += "--claude-worktrees-abc123"
        cfg = Path(tmp_path) / "cfg"
        dest = cfg / "projects" / slug
        shutil.copytree(CASES / case, dest)
        when = time.time() - age_seconds
        for p in dest.rglob("*"):
            if p.is_file():
                os.utime(p, (when, when))
        return cfg
    return install


@pytest.fixture
def record_copy():
    """record_copy(tmp_path) -> tmp_path/proj, holding a copy of the fixture record as company/."""
    def copy(tmp_path) -> Path:
        proj = Path(tmp_path) / "proj"
        shutil.copytree(RECORD_FIXTURE, proj / "company")
        return proj
    return copy


@pytest.fixture
def read_ledger():
    def read(proj):
        out = []
        with open(Path(proj) / "company" / "ledger.jsonl", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out
    return read
