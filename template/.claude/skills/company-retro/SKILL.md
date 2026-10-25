---
name: company-retro
description: Run the retrospective for the last cycle: mine the ledger for surprises, record cited lessons, consolidate the knowledge base. Use after each cycle report is delivered, or when the CEO says "retro".
allowed-tools:
  - Bash(tools/company/company *)
  - Read
  - Glob
  - Grep
  - Agent
---

You are running the RETRO procedure as the Chief of Staff. Set `COMPANY_ACTOR=chief-of-staff COMPANY_TIER=executive` for CLI calls.

## Steps

1. Spawn `learning-officer` with the cycle number and the instruction to: read the cycle's ledger events and journal, the blocked and rejected items, review outcomes, budget events and CEO answers; write `company/retros/cycle-NNN.md`; record lessons with `company lesson add` (one fact per lesson, evidence required, `applies_to` tags that match roles or modules); and run `company consolidate`.

2. Spawn `librarian` to render the journal, rebuild the index, and check frontmatter and links.

3. Read the retro and the new lessons. Delete nothing, but if a lesson is vague or uncited, send it back to the Learning Officer with the specific objection.

4. Log `company log retro.completed --ref company/retros/cycle-NNN.md --summary "<n> lessons"`.

5. Tell the CEO in three lines: how many lessons were recorded, the single most important one, and whether the next cycle can start.

## Do not
- Write lessons yourself.
- Soften findings. A retro that blames nothing and changes nothing is a failed retro.
