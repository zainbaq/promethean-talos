# Retro: cycle 1

## Expected
Two P0 items (Timer ITEM-0001, Settings ITEM-0002) built in parallel, reviewed, verified from a fresh integration worktree and design-checked in one cycle.

## What happened
- Both items verified. 18 tests passed, 0 skipped, twice, on the merged integration branch e6d6c68 (company/reports/evidence/cycle-1.txt).
- Zero blocked or rejected items, zero CEO questions, zero spec-lint failures recorded.
- Both reviews passed with nits; the head of design passed both on default-state shots.
- Head of Product turned review output into five low-risk follow-ups (ITEM-0003..0007) and declined two nits with evidence.
- The close phase did not close the cycle. The run (EVT-20261028175110-942b) logged success, but there is no `cycle.closed` event, no `company/reports/cycle-001.md`, and `talos status --brief` reads "cycle 1 open" at retro time. The CEO has received no cycle report.

## What surprised us
- The close run spent its budget on step 2 (spec the next items) and never reached step 4 (cycle end, report). The chief-architect subagent it spawned ran 20 calls over 9.5 minutes, wrote only to its scratchpad and logged nothing. (C1, C2, C3; lesson-0001, lesson-0002)
- ADR-0002 and SPEC-0002 disagreed on validation-error display. The disagreement was created at plan by the architect's own reconciliation (EVT-20261028045605-6af3), which changed the spec and left the ADR; code review found it. (C5; lesson-0003)
- The "mockup drift" was not drift. The settings mockup was aligned at plan (04:58:32Z); SPEC-0002's sentence about it was three minutes older and stale. The ui-engineer, Head of Product (ITEM-0007) and the first draft of this retro repeated it; nobody opened the file. (C6; lesson-0004)
- The break-ready state was never captured or design-reviewed because SPEC-0001 names the break mockup in Goal but its capture criterion covers only the idle page. (C7; lesson-0005)

## What changes
1. Close phase: report first (step 4), queue-filling last (step 2). A cycle-close run with no `company/reports/cycle-NNN.md` and no `cycle.closed` event is a failed run, whatever the exit status. (lesson-0001)
2. When the most expensive role has no ledger events, attribute its calls by transcript parent session to a `run.completed` session id before writing a cause; extend `talos usage` to print spend by spawning phase. (lesson-0002)
3. Spec handoff: a reconciliation that changes behaviour an ADR states amends the ADR in the same step; the spec lists the ADR sentences it overrides. (lesson-0003)
4. Specs point at design files and do not restate their copy or ranges; Head of Product opens the file before creating a follow-up from a note about it. ITEM-0007 drops its first criterion. (lesson-0004)
5. Every mockup or state a spec names gets a capture line with the steps to reach it; Design QA's capture list is derived from the spec. (lesson-0005)

Immediate: the Coordinator must still run close step 4 for cycle 1 (`talos cycle end`, `talos report`, chief-of-staff summary) so the CEO gets the report and the cycle is closed in the ledger before cycle 2 starts.

## Spend
- Measured: 4.35M tokens, 119 calls. By model: fable 2.34M (chief-architect 1.52, main 0.34, head-of-product 0.33, head-of-design 0.14, learning-officer 0.01), sonnet 1.75M (main 0.75, ui-engineer 0.74, test-engineer 0.19, design-qa 0.07), opus 0.26M (code-reviewer).
- Top three roles: chief-architect 35.0%, main session (sonnet) 17.1%, ui-engineer 17.0%.
- Per verified item: 2.18M tokens (2 verified).
- Most expensive role: chief-architect (1.52M, 35.0%, 20 calls, 1.37M cache read). Cause, proven from the transcripts: one subagent (agent-aeb94a92) of the cycle-close session 5f93c509 (EVT-20261028175110-942b), 17:41:06-17:50:29Z, spawned by close step 2 to spec ITEM-0003..0007. It produced no spec, decision or note and no file under `company/`. The 1.52M bought nothing.
- One change to cut it: do not spawn the architect from cycle-close until the report is delivered, and give it one item per spawn with a turn budget; a spawn that ends with nothing logged is a failed spawn and the Coordinator records it as such.
- Run costs: cycle-build $1.64, cycle-verify $1.80, cycle-close $5.58. Close is the highest because it carried the 1.52M-token architect spawn, and it delivered neither the report nor the cycle end.
