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

CEO messages from the control room go through `/talos-triage`, not here. If this names a CEO rule about a branch ("never touch main"), record it: `talos protect <branch>`.

## Steps

1. Read `company/questions.md` (the `## Open` section) and the latest `company/reports/cycle-*.md`.

2. For each decision in the CEO's words:
   - An answer to a question: `talos answer Q-xxxx "<their words>"`. If the question blocked an item, `talos item set ITEM-xxxx --status ready --summary "unblocked by Q-xxxx"`.
   - Charter or plan approval: `talos approve charter|plan --quote "<their exact words>"`.
   - Release approval for specific items: `talos approve release --ref ITEM-xxxx --quote "<their exact words>"` per item. Then merge right away: `talos gate release --ref ITEM-xxxx` and `talos gate item --ref ITEM-xxxx` must both pass, then merge where `talos base --worktree` says: `git -C "<that path>" merge --no-ff --no-edit <branch>`, and log `release.shipped`. If that path is the developer's checkout and `git status --porcelain` shows changes outside `company/`, do not merge, stash or reset; tell the CEO what is in the way. A branch from `talos protect` is never merged into: when the base is a work branch, say in your confirmation that the work is on it and only the CEO merges further. Approved branches never wait for a later cycle.
   - A rejection or change request: log `talos log note --ref <thing> --summary "CEO: <words>"` and create or re-open the backlog items the change requires via `head-of-product` if scope changed, or `chief-architect` if the design changed.

3. Confirm back to the CEO in two lines what was recorded and what will happen next (`tools/talos/run plan`, `cycle` or `retro`).

## Do not
- Paraphrase the CEO in `--quote`. Use their words.
- Infer approvals. "Looks good" about a report is not release approval unless they say to merge or ship.
- Merge anything whose gates are closed.
