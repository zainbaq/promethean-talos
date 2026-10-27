---
name: talos-cycle
description: Run one execution cycle: assign ready items to engineers in parallel worktrees, collect hand-backs, review, verify from a fresh integration worktree, and produce the cycle report for the CEO. Use after the plan is approved, when the CEO says "run a cycle", "continue", or on a schedule.
argument-hint: "[budget, e.g. '4h' or '3 items']"
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

You are running the CYCLE procedure as the Chief of Staff (read `.claude/agents/chief-of-staff.md`). Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls. Budget for this cycle: $ARGUMENTS (default: the charter's per-cycle budget). Read `company/environment.md` first; if it still says `_not probed_`, stop and run the kickoff environment step.

## Gate
`tools/talos/talos gate plan`. Closed means stop and ask the CEO.

## Steps

1. **Open the cycle.** `talos cycle start --budget "<budget>"`. Read `company/charter.md` for parallelism. `talos item list --status ready`. Note the base branch from `company/environment.md` (never assume `main`).

2. **Select.** Choose up to the parallelism limit of `ready` items whose specs do not overlap in files and that do not depend on each other. Prefer P0, then P1. If an item's spec fails the handoff contract, or does not state that the architect executed its acceptance commands, send it to `chief-architect` instead of an engineer and pick another.

3. **Assign and dispatch in parallel.** For each selected item: `talos item set ITEM-xxxx --status assigned --owner <role> --branch vc/item-xxxx`, then `--status in_progress`. Spawn one `engineer` (or `devops-engineer`, `ux-designer`, `technical-writer` as the spec requires) per item, in the same message so they run concurrently. Give each: item id, spec path, branch name, base branch, the worktree command (`git worktree add "../<repo>-wt/<item-id>" -b vc/<item-id>` from the repository root), the relevant lines of `company/environment.md` (interpreter, test command, shell quirks), the lessons that apply (paste them), the rule "no writes to company/", and the hand-back format (ITEM, STATUS, BRANCH, COMMIT, CHANGED, EVIDENCE, QUESTIONS, NOTES).

4. **Collect hand-backs.** For each returned hand-back:
   - `completed`: `talos item set ITEM-xxxx --status completed --branch <branch> --commit <hash> --evidence "<EVIDENCE line>"`.
   - `blocked` or `needs_question`: `talos item set ITEM-xxxx --status blocked --summary "<why>"` and one `talos ask` per question. Technical questions: `--for architect` and spawn `chief-architect` to answer (it logs a decision and amends the spec; close with `talos answer Q-xxxx "<its answer>" --by chief-architect`). Scope questions: `--for ceo`. The CEO never sees a question another role can answer.
   - A hand-back that reports a spec criterion wrong as written is a success of the process: route it to the architect, do not fail the item for it.

5. **Review.** For each completed item spawn `code-reviewer` (base branch from the environment file), and `security-reviewer` when the item touches auth, credentials, ingestion, external APIs or user input. Log `review.requested` first. `changes_requested` sends the item back to a fresh `engineer` on the same branch with the findings pasted in; log the round trip and request a round-2 review of the fix diff. Two rejections of the same item means stop and escalate to the Chief Architect, not a third attempt.

6. **Verify.** When all reviewed items of the wave have passed, spawn one `test-engineer` with the list of items, branches and commits. It builds a detached integration worktree of the base branch, merges the item branches locally, runs everything, and logs `verified` or `rejected` per item itself. Rejected goes back to an engineer once; then escalate.

7. **Budget.** After each wave run `talos status` and log `talos log budget.consumed --summary "<elapsed from the ledger> and <measured tokens from the Spend line>, including review and decision rounds"`. A token budget in the charter is compared with the measured figure only, never an estimate. Stop dispatching when the budget is reached; finish collecting and verifying what is in flight; say plainly in the report that the ceiling was reached.

8. **Keep the queue full and the follow-ups real.** Before closing, check `talos item list --status ready` for the next cycle. If it is empty or thin, spawn `chief-architect` to spec the next `proposed` items and `head-of-product` to mark them ready, inside this cycle's budget, so the next cycle starts with work. Then sweep this cycle's ledger notes and review findings for follow-ups that have no backlog item (hardening notes, doc fixes, "later" remarks): spawn `head-of-product` to create an item for each or decline it with a logged reason. A follow-up that lives only in a note is lost.

9. **Report.** `talos cycle end --summary "<one line>"`, then `talos report`. Edit the Summary into two or three plain sentences. Lead with the one decision the CEO must make. The report's "Where the product is" section must be correct: repository path, base branch, each verified item's branch and commit, and that nothing is on the base branch until release approval. Spawn `librarian` to render the journal and rebuild the index.

10. **Deliver.** Give the CEO the report (send the file if a file-sending tool exists) with: items ready to merge and their branches, blocked items, CEO questions as yes/no, budget used, and where the product lives. Do not merge; merging is the CEO's release approval (`talos approve release --ref ITEM-xxxx --quote "<their words>"`, then `talos gate release` and `talos gate item` must both pass).

11. **Run the retro before the next cycle.** Tell the CEO `/talos-retro` runs next. A cycle never starts while the previous cycle has no retro; the pre-mortem for the next cycle's specs depends on it.

## Do not
- Write product code or tests yourself.
- Mark anything `verified` without Test Engineer or Head of QA evidence.
- Hand two concurrent engineers overlapping files.
- Decide a technical question yourself. Route it.
- Let an engineer guess. A `needs_question` hand-back is a success of the process, not a failure.
