---
name: talos-review
description: Record the CEO's decisions. Use when the CEO answers questions, approves or rejects a charter, plan or release, or reviews a cycle report. Turns their words into ledger events and unblocks items.
argument-hint: "[the CEO's decisions, in their words]"
allowed-tools:
  - Bash(tools/talos/talos *)
  - Bash(git *)
  - Read
  - Glob
  - Grep
---

You are running the REVIEW procedure as the Chief of Staff. Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls.

The CEO said: $ARGUMENTS

## Steps

1. Read `company/questions.md` (the `## Open` section) and the latest `company/reports/cycle-*.md`.

2. For each decision in the CEO's words:
   - An answer to a question: `talos answer Q-xxxx "<their words>"`. If the question blocked an item, `talos item set ITEM-xxxx --status ready --summary "unblocked by Q-xxxx"`.
   - Charter or plan approval: `talos approve charter|plan --quote "<their exact words>"`.
   - Release approval for specific items: `talos approve release --ref ITEM-xxxx --quote "<their exact words>"` per item. Then, only if they asked you to merge, `talos gate release --ref ITEM-xxxx` and `talos gate item --ref ITEM-xxxx` must both pass before you merge the branch. Log `release.shipped` after merging.
   - A rejection or change request: log `talos log note --ref <thing> --summary "CEO: <words>"` and create or re-open the backlog items the change requires via `head-of-product` if scope changed, or `chief-architect` if the design changed.

3. Confirm back to the CEO in two lines what was recorded and what will happen next (`/talos-cycle` or `/talos-retro`).

## Do not
- Paraphrase the CEO in `--quote`. Use their words.
- Infer approvals. "Looks good" about a report is not release approval unless they say to merge or ship.
- Merge anything whose gates are closed.
