---
name: talos-task
description: Take one queued ask from spec to a verified branch, outside any cycle. Use for items on the fast or item route, when the runner names one.
argument-hint: "ITEM-xxxx"
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

You run ONE item as the Coordinator (`TALOS_ACTOR=coordinator TALOS_TIER=execution`). You follow these steps exactly and write no product code. There is no cycle, no plan gate and no retro. The only gate is the CEO's release.

**Subagents run in the foreground.** Every dispatch names this one item. Pass the `model` the session's preset note gives for the role.

**Resuming.** When your arguments start with "Resume:", pick the routed item that is `in_progress` or `completed`, read `company/handbacks/`, and do only what has no hand-back yet.

## Steps

1. **Read.** `tools/talos/talos item show ITEM-xxxx`, `tools/talos/talos status --brief`, `tools/talos/talos base`. Its route is in the output.
2. **Catch up.** `tools/talos/talos drift`. It lists files changed outside the company, and with a work branch it brings the developer's changes in. A merge it cannot do is a stop: `talos ask --for ceo --ref ITEM-xxxx`, then finish. If it lists files, do what it says before you read any code: what the company knows about them is out of date. Skip the librarian only if `company/knowledge/codebase.md` does not exist, and still run `tools/talos/talos drift --seen`.
3. **Spec.**
   - Route `fast`: write it inline. `tools/talos/talos item set ITEM-xxxx --acceptance "<criterion>"` for each criterion (one to five, each something a command can show). Read only what you need to name the files. If this turns out to need more than one engineer, or real design decisions, log it with `tools/talos/talos log note --ref ITEM-xxxx --summary "<why>"` and treat it as route `item`.
   - Route `item`: spawn `chief-architect` once, naming this item, to write a spec (`talos spec new --title "<title>" --item ITEM-xxxx`) and set the criteria. `tools/talos/talos spec lint <SPEC>` must pass; a failure goes back to the architect once.
4. **Build.** `tools/talos/talos item set ITEM-xxxx --status in_progress --owner <role> --branch vc/item-xxxx`, then `tools/talos/talos context ITEM-xxxx --role <role>`, which prints the pack's path. Spawn one `engineer` (`ui-engineer` for frontend work, `technical-writer` for docs, `devops-engineer` for infrastructure) with `isolation: worktree`. The prompt is short: the pack path, the branch and the base branch from step 1, "create your branch in the worktree you were given: `git switch -c vc/item-xxxx <base>`", "no writes to company/", "return the hand-back block at the end of the pack". When it returns: `tools/talos/talos handback ITEM-xxxx --role <role> --text "<the whole block>"`, then `tools/talos/talos item set ITEM-xxxx --status completed --branch <branch> --commit <hash> --evidence "<EVIDENCE line>"`. Blocked: `--status blocked --summary "<why>"` and one `talos ask` per question, then finish.
5. **Review by risk**, from the item's `risk`; do not re-judge it. `low`: skip. `normal`: spawn `code-reviewer`. `high`: `code-reviewer` and `security-reviewer`. Give each the pack (`talos context ITEM-xxxx --role code-reviewer`), the branch, the commit and the base. Log `review.requested` first, then `review.passed` or `review.changes_requested`. Changes requested goes to a fresh engineer on the same branch once, then a review of the fix only. A second rejection goes to `chief-architect`, not a third attempt.
6. **Verify.** Spawn one `test-engineer` with the item, branch, commit and base. It uses a detached worktree of the base, merges the branch there, runs the tests and logs `verified` or `rejected`. If `company/baseline.json` exists it also runs `tools/talos/talos baseline --check --where <that worktree>` from the main checkout: a new failure is a regression. Nothing can be verified: `tools/talos/talos log verify.blocked --ref ITEM-xxxx --summary "<why>"`.
7. **Ask for the release.** Nothing merges yet. The verified item appears on the CEO's release card by itself.

## Your final message

Two or three sentences for a phone: what changed, on which branch, what the evidence shows, and that it waits for their release approval. If the guard refused anything, say so.

## Do not
- Merge, push, or change the base branch or any protected branch.
- Run a project's test suite yourself.
- Widen the item. A follow-up you notice is one line in your final message.
