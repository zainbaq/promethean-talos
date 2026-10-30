# Cycle 1 retro candidates

Drafted by the Coordinator from `talos events/usage --cycle 1`. Judgment belongs to the Learning Officer.

Verdicts (learning-officer, 2026-10-28): C1+C2+C3 merged into lesson-0001 and lesson-0002; C5 accepted as lesson-0003; C6 reversed and sharpened into lesson-0004; C7 accepted as lesson-0005; C4, C8, C9 rejected.

## C1. No cycle report file exists for cycle 1
- Fact: `cycle-close` ran (EVT-20261028175110-942b, $5.58) but `company/reports/` holds only `README.md` and `evidence/cycle-1.txt`; there is no `cycle-001.md`.
- Proof: `ls company/reports`; `find company -name "cycle-0*"` returns nothing.
- Tags: coordinator, cycle-close, reports.
- Implies: cycle-close must fail loudly (or `talos` must lint) when the report file is missing; the retro cannot cite the report.
- Verdict: ACCEPTED, sharpened. Verified: no report file, and also no `cycle.closed` event; `talos status --brief` says "cycle 1 open". Close step 4 (`talos cycle end`, `talos report`) never ran. Merged with C2 and C3 into lesson-0001.

## C2. Chief-architect was the most expensive role
- Fact: chief-architect used 1.52M tokens (35.8%, fable, 20 calls, 1.37M cache read), more than both ui-engineers combined (0.74M) in a cycle whose ledger shows no architect events.
- Proof: `talos usage --cycle 1`; no chief-architect events in `talos events --cycle 1`.
- Tags: chief-architect, spec, plan.
- Implies: unclear what the 20 calls were (likely plan/spec authoring and executing acceptance criteria, which the handoff contract requires). Needs per-call attribution to an item or phase; 52.8% of tokens sit under "several" and 23.6% under "-", so item-level cost is not actionable.
- Verdict: ACCEPTED, cause corrected. The "likely plan/spec work" guess was wrong. Transcripts: all 20 calls are subagent agent-aeb94a92 (agentType chief-architect) under session 5f93c509, the cycle-close session of EVT-20261028175110-942b, 17:41:06-17:50:29Z, prompted by close step 2 to spec ITEM-0003..0007. It made 20 tool calls, wrote four files to its scratchpad, nothing under `company/`, logged nothing. lesson-0001 (root cause) and lesson-0002 (attribution method).

## C3. Fable spend on orchestration
- Fact: main session on fable (0.34M) plus cycle-build at $1.64 and cycle-close at $5.58 on sonnet (the priciest phase) mean the mechanical phases cost more than the cycle-verify ($1.80).
- Proof: run.completed events EVT-...172902-e66e, ...173616-cb01, ...175110-942b.
- Tags: coordinator, launcher.
- Implies: close is the costliest mechanical phase; check what it re-reads.
- Verdict: MERGED into lesson-0001. Close cost $5.58 because it spawned the architect (1.52M fable tokens) in step 2 and produced no report; it is not a re-reading problem.

## C4. Test passed in worktree as "skipped", resolved on integration
- Fact: `test_saved_focus_reaches_timer` skipped on vc/item-0002 alone (depends on app/index.html from ITEM-0001) and passed on the integration branch (18 passed, 0 skipped, twice).
- Proof: EVT-20261028172653-c636; EVT-20261028173407-b7e0; company/reports/evidence/cycle-1.txt.
- Tags: test-engineer, spec, cross-item dependency.
- Implies: cross-item tests should be declared in the spec as integration-only so a skip is expected, not a surprise. This worked as designed; no defect.
- Verdict: REJECTED. SPEC-0002 acceptance line for `test_saved_focus_reaches_timer` already declares the skip and that it runs on the integration worktree; the implied change is already in place and nothing went wrong.

## C5. ADR/SPEC contradiction found only at review
- Fact: ADR-0002 and SPEC-0002 disagree on how Settings displays a validation error; the code reviewer found it, not spec lint.
- Proof: EVT-20261028173027-fac6; ITEM-0006.
- Tags: chief-architect, spec lint, ADR.
- Implies: specs must cite the ADR sections they rely on and the architect should diff spec against linked ADRs before handoff.
- Verdict: ACCEPTED as lesson-0003, with the origin: the architect's reconciliation EVT-20261028045605-6af3 ("help text becomes the error text") changed what ADR-0002 states ("inline error paragraph, role=alert") and did not amend the ADR.

## C6. Mockups drifted from spec
- Fact: ui-engineer followed the spec ranges (focus 1-120, break 1-60) over the mockup's (1-90, 1-30), and the mockup carried a dead selector and a `div.app` wrapper absent from the spec DOM.
- Proof: EVT-20261028172653-ddd1; ITEM-0007; EVT-20261028172846-a974 (break-ready state unscreenshotted).
- Tags: ux-designer, head-of-design, ui-engineer.
- Implies: mockups should be produced after, or checked against, spec data ranges; specs should list every state requiring a capture.
- Verdict: REVERSED and sharpened into lesson-0004. `company/design/mockups/settings.html` reads 1 to 120 and 1 to 60 and was last written 04:58:32Z (EVT-20261028045913-078d), three minutes after SPEC-0002's last write (04:55:40Z). The mockup did not drift; the spec's sentence about the mockup went stale and was repeated by the ui-engineer, by Head of Product in ITEM-0007 and by this draft without the file being opened. ITEM-0007's first criterion is already met. The dead selector in timer-break.html stands (ITEM-0007, second criterion); the `div.app` wrapper is a spec DOM omission, no lesson.

## C7. Design critique only saw default states
- Fact: head-of-design passed both items on default-state shots only; break-ready was never captured, leaving ITEM-0003 as follow-up.
- Proof: EVT-20261028173608-87f6, -9994; ITEM-0003.
- Tags: design-qa, head-of-design.
- Implies: design-qa capture list should come from the spec's states, not the executor's choice.
- Verdict: ACCEPTED as lesson-0005, with the cause located in SPEC-0001: Goal names timer-break.html, the capture criterion captures only index.html as loaded and signs against timer.html only.

## C8. Real-time test cost
- Fact: ITEM-0001's suite includes a real 1-minute focus test; the suite took 70 s.
- Proof: EVT-20261028172846-3660.
- Tags: test-engineer, ui-engineer, timer.
- Implies: acceptable once, but repeated twice on integration; consider a clock-injection hook for non-acceptance runs (ADR-0002 uses wall-clock end timestamps).
- Verdict: REJECTED. The 1-minute wall-clock test is charter criterion 1 (ADR-0002 Context); a clock-injection run would not satisfy it, and 70 s is inside the spec's stated ~75 s.

## C9. Two code-review nits declined by product
- Fact: Head of Product declined two nits as out of scope or already resolved, and created five follow-ups (ITEM-0003..0007), all P2/P3 and low risk.
- Proof: EVT-20261028174039-1828, -4500; EVT-...174013..174015.
- Tags: head-of-product, code-reviewer.
- Implies: working as designed; the review-to-backlog path produced no rejected or blocked items this cycle (0 blocked, 0 rejected, 0 CEO questions).
- Verdict: REJECTED. No change implied; a candidate that reports the process working is not a lesson.
