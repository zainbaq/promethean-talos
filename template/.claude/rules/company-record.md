---
paths:
  - "company/**"
---

# Rules for the company record

- `company/ledger.jsonl` and `company/state.json` are owned by the CLI. Never edit them by hand; use `tools/company/company log|item|cycle|approve ...`.
- Every file in `company/backlog/`, `company/specs/`, `company/decisions/` and `company/knowledge/` starts with YAML frontmatter containing at least `id` and `title`. Items also carry `status`; lessons carry `applies_to`, `evidence`, `confidence`.
- Item status changes go through `company item set` so the ledger records the transition. Editing the `status:` line by hand is not a status change.
- Questions for the CEO go in `company/questions.md` through `company ask`, never inline in other files.
- Lessons require evidence. If you cannot cite a ledger event, file, or test output, it is an observation, not a lesson; put it in the retro instead.
- Reports in `company/reports/` are for a reader on a phone: decisions first, then evidence, then detail.
- Agents running in worktrees do not write here at all. They hand back; the Chief of Staff logs.
