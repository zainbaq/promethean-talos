---
name: talos-cycle
description: Run one execution cycle in three phases (build, verify, close): dispatch engineers in parallel worktrees, review, verify from a fresh integration worktree, and report to the CEO. Use after the plan is approved, when the CEO says "run a cycle" or "continue", or on a schedule.
argument-hint: "[build|verify|close] [budget, e.g. '60 minutes' or '3 items']"
allowed-tools:
  - Bash(tools/talos/talos *)
  - Bash(git *)
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
---

Arguments: $ARGUMENTS

A cycle has three phases. Each normally runs in its own fresh session through `tools/talos/run cycle-build|cycle-verify|cycle-close` (or `tools/talos/run cycle` for all three), because one long session re-reads its whole history on every call. If the first argument is `build`, `verify` or `close`, run only that phase. With no phase argument, run the three in order in this session.

**Subagents run in the foreground.** Spawn every subagent as a normal (foreground) Agent call and wait for its result before you continue. Never start one in the background: a headless phase ends when your turn ends, and a background agent is cut off with its work lost (in the first UI test a background architect spent 1.5M tokens and wrote nothing).

**Start every phase the same way:** `tools/talos/talos status --brief`, then the lines of `company/environment.md` you need (base branch, test command). Do not read the rest of `company/`; the CLI and the context packs give you what you need. End every phase with the phase hand-back at the bottom of this file and nothing else.

Roles: **build** is run by the Chief of Staff (Fable; `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive`), or by the Coordinator on Sonnet when every ready item is risk low, because then dispatch decides nothing. **verify** and **close** are run by the Coordinator (Sonnet; `TALOS_ACTOR=coordinator TALOS_TIER=execution`), who follows these steps exactly and escalates every judgment call: technical ones to a `chief-architect` subagent, scope ones as `talos ask --for ceo`.

## Phase: build

1. **Gate and open.** `talos gate plan` and, when the design team is staffed, `talos gate design` (closed: stop and ask the CEO). `talos cycle start --budget "<budget>"`; the budget comes from the arguments or the charter and covers review and verification, not only engineering.
2. **Select.** `talos item list --status ready`. Choose up to the charter's parallelism of items whose specs do not overlap in files and do not depend on each other; P0 first. Run `talos spec lint <SPEC>` for each; a spec that fails goes to `chief-architect` to fix, and you pick another item.
3. **Pack and dispatch in parallel.** For each item: `talos item set ITEM-xxxx --status in_progress --owner <role> --branch vc/item-xxxx`, then `talos context ITEM-xxxx --role <role>`, which prints the pack's absolute path. Spawn one `engineer` (or `ui-engineer` for frontend items, `devops-engineer`, `technical-writer`, as the spec requires) per item, all in one message so they run concurrently. Each dispatch prompt is short and names exactly one item: the pack path, the branch name and base branch with the instruction to create the branch inside the worktree the harness provides (`git switch -c vc/<item-id> <base branch>`; never `git worktree add`) and report that worktree's path in NOTES, the rule "no writes to company/", and "return the hand-back block at the end of the pack". Everything else is in the pack; do not paste it.
4. **Collect.** For each hand-back:
   - `completed`: `talos item set ITEM-xxxx --status completed --branch <branch> --commit <hash> --evidence "<EVIDENCE line>"`.
   - `blocked` or `needs_question`: `talos item set ITEM-xxxx --status blocked --summary "<why>"` and one `talos ask` per question. Technical: `--for architect`, spawn `chief-architect` to answer (it logs a decision and amends the spec), close with `talos answer Q-xxxx "<answer>" --by chief-architect`, and re-dispatch once. Scope: `--for ceo`.
   - A hand-back saying a spec criterion is wrong as written is a success: route it to the architect.
5. Log `talos log budget.consumed --summary "build: <elapsed from status> and <measured tokens from the Spend line>"`.

## Phase: verify

1. `talos status --brief`. Items `completed` in this cycle are the input.
2. **Review by risk.** For each completed item read its `risk` (in `talos item show`) and follow it exactly; do not re-judge it. `low`: no Opus review, go to step 3. `normal`: spawn `code-reviewer`. `high`: `code-reviewer` and `security-reviewer`. Give each reviewer the item's context pack (`talos context ITEM-xxxx --role code-reviewer`), the branch, the commit and the base branch. Log `review.requested` first, then `review.passed` or `review.changes_requested` with the reviewer's verdict line.
3. `changes_requested` sends the item to a fresh `engineer` on the same branch with the findings pasted in, then a round-2 review of the fix diff only. A second rejection of the same item stops: spawn `chief-architect` with both reviews; never a third attempt.
4. **Verify.** When every reviewed item has passed, spawn one `test-engineer` with the list of items, branches and commits. It builds a detached integration worktree of the base branch, merges the branches locally, runs everything, and logs `verified` or `rejected` per item itself. A rejected item goes back to an engineer once, then to the architect.
5. **Visual check** for items owned by `ui-engineer`, on an integration worktree (its own detached one if the Test Engineer has removed theirs): spawn `design-qa` with the screens those items touch, then `head-of-design` with only the screenshot folder and `company/design/mockups/shots`. Its critique is the review for visual criteria: `review.passed`, or `review.changes_requested` that sends the item back to a fresh `ui-engineer` once.
6. Log `talos log budget.consumed --summary "verify: <elapsed> and <measured tokens>"`.

## Phase: close

The cycle closes and the report exists before anything else happens in this phase.

1. `talos status --brief`.
2. **Report first.** `talos cycle end --summary "<one line>"`, then `talos report`. Spawn `chief-of-staff` with only the report path to rewrite its Summary into two or three plain sentences for a phone, leading with the one decision the CEO must make. The "Where the product is" section must be right: repository path, base branch, each verified item's branch and commit, nothing on the base branch until release approval, and every URL in both hostname and raw IP form as `company/environment.md` lists them. For UI items, link the phone-width screenshots Design QA filed.
3. **Follow-ups are items, not work.** `talos events --cycle <N> --type review` and `talos events --cycle <N> --type note`: spawn `head-of-product` once to create a `proposed` item for each follow-up with no backlog item, or decline it with a logged reason. Do not spec them. List them in the report under "Proposed next" for the CEO to prioritise.
4. **Keep the queue full only when the charter needs it.** If the charter's success criteria are not all met, `talos size` is medium or large, and `talos item list --status ready` is thin, spawn `chief-architect` to spec the `proposed` items the charter still needs and `head-of-product` to mark them ready. Small projects, and projects whose charter is met, never spec follow-ups without the CEO.
5. Spawn `librarian` to render the journal.
6. **Deliver.** Send the CEO the report file if a file-sending tool exists. Do not merge: merging is the CEO's release approval (`talos approve release --ref ITEM-xxxx --quote "<their words>"`; then `talos gate release` and `talos gate item` must both pass).
7. The retro (`tools/talos/run retro`) runs before the next cycle; a cycle never starts while the previous one has no retro.

## Phase hand-back (the whole final message of a phase)
```
PHASE: build | verify | close
CYCLE: <n>
ITEMS: <id status, one per line>
CEO QUESTIONS: <ids, or none>
SPEND: <elapsed>, <measured tokens>
NEXT: <the next phase, or "report delivered: <path>">
```

## Do not
- Write product code or tests yourself.
- Mark anything `verified` without Test Engineer or Head of QA evidence.
- Give two concurrent engineers overlapping files.
- Decide a technical question yourself. Route it.
- Read files the pack or the CLI already summarises. Every file read is re-read on every later call of this session.
