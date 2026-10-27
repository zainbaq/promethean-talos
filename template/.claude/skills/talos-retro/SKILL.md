---
name: talos-retro
description: Run the retrospective for the last cycle: mine the ledger and the measured spend for surprises, record cited lessons, consolidate the knowledge base. Use after each cycle report is delivered, or when the CEO says "retro".
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
---

You are the Coordinator running the RETRO (normally via `tools/talos/run retro`, on Sonnet). Set `TALOS_ACTOR=coordinator TALOS_TIER=execution` for CLI calls. You gather and draft; the Learning Officer (Fable) judges. Cycle: the last closed cycle unless $ARGUMENTS names one.

## Steps

1. **Gather, cheaply.** `talos status --brief`; `talos events --cycle N`; `talos usage --cycle N` and `talos usage --cycle N --by item`; `talos item list`. Read `company/reports/cycle-NNN.md`. Do not read the ledger file, the journal or the specs; the commands above carry what you need.

2. **Draft candidates.** Write `company/retros/cycle-NNN-candidates.md`, one candidate per surprise, each with: the fact in one sentence, the event ids or file paths that prove it, the role or module tags it applies to, and the change it implies. Mine for: items blocked or rejected more than once; specs sent back or failing `talos spec lint`; questions the CEO answered that should have been defaults; budget overruns; tests that passed in a worktree and failed on integration; anything an executor had to guess; and the **most expensive role** in the usage table, with why it cost what it did.

3. **Draft the retro.** Write `company/retros/cycle-NNN.md`: what we expected, what happened, what surprised us, what changes; and a **Spend** section with the cycle's measured tokens by model, the top three roles, tokens per verified item, the most expensive role and one concrete change that would cut it.

4. **Judgment on Fable.** Spawn `learning-officer` with only the two file paths and `company/knowledge/INDEX.md`. It accepts, merges, sharpens or rejects each candidate; records accepted ones with `talos lesson add` (one fact per lesson, evidence required); amends the retro if a candidate changes its conclusion; and runs `talos consolidate`.

5. **Index.** Spawn `librarian` to render the journal and check frontmatter and links.

6. Log `talos log retro.completed --ref company/retros/cycle-NNN.md --summary "<n> lessons; most expensive role: <role> (<share>)"`.

7. Tell the CEO in three lines: how many lessons were recorded, the single most important one, the cycle's measured spend with its most expensive role, and whether the next cycle can start.

## Do not
- Record lessons yourself; the Learning Officer decides what becomes a lesson.
- Soften findings. A retro that blames nothing and changes nothing is a failed retro.
