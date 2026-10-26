---
name: talos-plan
description: Plan an approved project: pre-mortem, architecture and ADRs, specs, backlog with acceptance criteria, and test strategy, then ask the CEO to approve the plan. Use after the charter is approved, or when the CEO asks to re-plan.
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Agent
---

You are running the PLAN procedure as the Chief of Staff (read `.claude/agents/chief-of-staff.md`). Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls.

## Gate
Run `tools/talos/talos gate charter`. If it is closed, stop and tell the CEO the charter needs approval first.

## Steps (executive roles, in this order; each reads the record first)

1. **Pre-mortem.** Spawn `learning-officer` to read `company/knowledge/INDEX.md` and past retros and write `company/retros/pre-mortem-plan.md`: the lessons most likely to bite this plan and what they threaten. On a brand-new project with no lessons, it writes the generic risks for this kind of build instead.

2. **Architecture.** Spawn `chief-architect` with the charter, the pre-mortem and the research. It records ADRs for every significant choice (`talos decision add`), defines interface contracts, and proposes the work breakdown: a list of items small enough for one engineer in one cycle and independent enough to run in parallel.

3. **Backlog.** Spawn `head-of-product` with the architect's breakdown. It creates each item with `talos item new`, with priority and at least one executable acceptance criterion, and marks the items for the first cycle `ready`.

4. **Specs for every item, not only the first cycle's.** Spawn `chief-architect` again (or continue it) to write one spec per backlog item with `talos spec new --item ITEM-xxxx`, filling every section. In the first live runs the plan carried specs for only the first cycle, so the next cycle opened with an empty ready queue and engineers sat idle while specs were written. If an item genuinely cannot be specced until earlier work lands, the spec says what it waits for and the item stays `proposed`; everything else is specced and `ready` before the plan gate. Specs must link the ADRs and the pre-mortem lessons that constrain them, reference `company/environment.md` for machine facts instead of restating them, stay within the architect's length budget (about 120 lines for a small item), mark verbatim blocks explicitly, and state that the architect executed every acceptance command before handoff.

5. **Test strategy.** Spawn `head-of-qa` to write the test strategy spec and attach acceptance tests to each ready item.

6. **Your review.** Read every ready item and spec. Apply the handoff contract: goal, non-goals, files in scope, interfaces, executable acceptance criteria, budget, linked ADRs and lessons, and the architect's statement that it executed the acceptance commands. Send back anything that fails. Check that no two concurrent specs touch the same files. Check the budget covers review and verification rounds, not only engineering.

7. **Propose.** Log `talos log plan.proposed --summary "<n> items, <m> ADRs, first cycle: <ids>"`.

8. **Ask the CEO.** Present on one screen: the architecture in five lines, the first cycle's items with one line each, the ADRs by title, the pre-mortem's top three risks and how the specs address them, and the budget. Ask for approval or changes.

9. **Record.** `talos approve plan --quote "<CEO's exact words>"` on approval. Then tell the CEO that `/talos-cycle` will run the first cycle and report back.

## Do not
- Let an item into `ready` without a spec and acceptance tests.
- Approve the plan on the CEO's behalf.
- Begin implementation.
