---
name: talos-plan
description: Plan an approved project at the depth its size calls for: ADRs, specs, backlog with acceptance criteria and risk, test strategy, then ask the CEO to approve the plan. Use after the charter is approved, or when the CEO asks to re-plan.
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Agent
---

You are running the PLAN procedure as the Chief of Staff (read `.claude/agents/chief-of-staff.md`). Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls.

## Gate and size
`tools/talos/talos gate charter` (closed: stop and tell the CEO). Then `talos status --brief` and `talos size`. **The size sets the depth of everything below.** In the first replay test a two-item tool got a medium-depth plan: 36 tests and detailed specs for a temperature converter, and the plan cost two thirds of the whole run. Plan only as deep as the size says.

| | small | medium | large |
|---|---|---|---|
| Pre-mortem | only if `company/knowledge/` has lessons | Learning Officer writes it | Learning Officer writes it |
| Architecture and specs | one `chief-architect` session does ADRs, breakdown, specs, risk and lint together | separate architecture pass, then specs | as medium, plus interface contracts between every pair of parallel items |
| ADRs | only choices a reviewer could get wrong (one or two) | every significant choice | every significant choice |
| Tests in specs | one test per behaviour the charter names; no exhaustive boundary matrices | behaviours plus the boundaries that matter | as medium |
| Test strategy | none; acceptance lines in the specs are the strategy | `head-of-qa` writes it | `head-of-qa` writes it |
| Spec length (lint) | 60 lines outside code blocks | 120 | 160 |

## Steps

1. **Pre-mortem** (per the table). Spawn `learning-officer` to write `company/retros/pre-mortem-plan.md`: the lessons most likely to bite this plan and what they threaten.

2. **Backlog.** Spawn `head-of-product` with the charter. It creates each item with `talos item new`, priority and one acceptance line per charter success criterion. Items are small enough for one engineer in one cycle.

3. **Architecture and specs.** Spawn `chief-architect` with the charter path, the project size, the item ids, the pre-mortem if any, and the table row for this size. It records ADRs (`talos decision add`), writes one spec per item (`talos spec new --item ITEM-xxxx`), executes every acceptance command it can, marks the rest UNEXECUTED, sets `--risk` on every item and runs `talos spec lint` until every spec passes. For medium and large, run this as two sessions: architecture and breakdown first, specs second. An item that cannot be specced until earlier work lands says what it waits for and stays `proposed`; everything else is `ready` before the plan gate.

3a. **Design** (when the design team is staffed). Spawn `head-of-design` with the charter, the size and the item list. It writes `company/design/direction.md`, `tokens.css`, `components.md` and mockups of the two or three key screens (small: two), screenshots them, and logs `design.proposed`. Specs for UI items reference the mockups and tokens by path. The CEO approves the design together with the plan unless the charter quotes the CEO waiving the design gate (`talos approve design-waiver --quote ...`).

4. **Test strategy** (medium and large). Spawn `head-of-qa` to write the test strategy spec and attach acceptance lines to each ready item, executing them as the architect did.

5. **Your review.** `talos spec lint` and `talos item list --status ready`. Read a spec in full only where lint fails or the risk rating looks wrong. Check that no two concurrent specs touch the same files and that the budget covers review and verification.

6. **Propose.** `talos log plan.proposed --summary "<n> items, <m> ADRs, size <size>, first cycle: <ids>"`.

7. **Ask the CEO.** When the design team is staffed, first send the phone-width light and dark mockup images (a file-sending tool if one exists, otherwise their paths) with the direction's one distinctive idea in a sentence. Then on one screen: the architecture in at most five lines, the first cycle's items one line each with their risk, the ADRs by title, the top risks and how the specs address them, and the budget. Ask for approval or changes.

8. **Record.** `talos approve plan --quote "<CEO's exact words>"` on approval, and `talos approve design --quote ...` when the design was part of what they approved, then tell the CEO the first cycle runs next (`tools/talos/run cycle`).

## Do not
- Plan deeper than the size calls for. A small project that gets a medium plan has wasted the CEO's budget.
- Let an item into `ready` without a spec that passes lint.
- Approve the plan on the CEO's behalf.
- Begin implementation.
