from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from viz import snapshot as S
from viz.watch import Watcher


def tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_no_writes(record_root):
    company = record_root / "company"
    before = tree_hashes(company)
    assert len(before) > 20
    now = datetime.now(timezone.utc)
    S.build(record_root, company, now=now, version=1, checked_at=now)
    w = Watcher(record_root, company)
    w.poll_once()
    w.poll_once()
    assert tree_hashes(company) == before
    assert {p.name for p in record_root.iterdir()} == {"company"}
