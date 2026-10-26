---
name: talos-consolidate
description: Tidy the knowledge base: merge duplicate lessons, retire lessons contradicted by later evidence, rebuild the index, render the journal. Use when the index grows past 100 lines, when lessons conflict, or monthly.
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Agent
---

Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls.

1. Run `tools/talos/talos consolidate` and note the possible duplicates it reports.
2. Spawn `learning-officer` with that list and the instruction to: read each pair, merge into the stronger lesson (keep both evidence lists), delete the weaker file, downgrade `confidence` on lessons whose evidence is older than two cycles with no reconfirmation, and delete lessons contradicted by later ledger evidence (log `note` with the reason for each deletion).
3. Spawn `librarian` to rebuild the index and render the journal.
4. Report: lessons before and after, what was merged or retired, and the index length.
