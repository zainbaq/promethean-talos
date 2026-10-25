# Retro: cycle 1 (wordstat)

**Author:** Learning Officer · **Date:** 2026-10-25 · **Inputs:** ledger EVT-20261025154909-7109 .. EVT-20261025184329-1e22, reports/cycle-001.md, reports/evidence/cycle-1-verification.txt, questions.md, ITEM-0001/0002, ADR-0007, SPEC-0001/0003 Correction sections, retros/pre-mortem-plan.md. Lessons recorded: LESSON-0001 .. LESSON-0009 (knowledge/INDEX.md).

## What we expected

- Two items (ITEM-0001 core, ITEM-0002 README + fixture) built by two Sonnet executors in parallel, reviewed once, verified from a fresh worktree, inside 30 minutes (EVT-20261025182513-feef).
- Specs complete enough that executors never guess: contract signatures verbatim, byte-exact outputs, every acceptance criterion an executable command (pre-mortem 2, 6, 15, 16). The Chief Architect had executed every SPEC-0002..0005 command in a spike before handoff (EVT-20261025162839-36df).
- Pre-mortem 10 named "tests pass in a worktree, fail from a clean checkout" and pre-mortem 12 named line endings in test assertions; neither named line endings of checked-in fixtures.

## What happened

- Both items verified from a fresh detached merge c580a95; 14 tests green three times; adversarial 34/34 (EVT-20261025184252-a26e, EVT-20261025184253-c1fd).
- ITEM-0001 round 1 rejected: three docstrings in core.py had a real newline where the contract has the two characters backslash-n, because the engineer pasted `\n` into non-raw docstrings. Fix d4e314a changed 3 lines; the proof was `format_json.__doc__` repr, not reading the source (EVT-20261025182829-d983, EVT-20261025183032-51d2, EVT-20261025183117-7a23).
- The Technical Writer flagged `core.autocrlf=true` at hand-back; the Code Reviewer checked blob line endings independently. Result: ADR-0007 (.gitattributes `* text=auto eol=lf`), a SPEC-0003 amendment, a second dispatch of the writer, a second review (EVT-20261025182749-daf1, EVT-20261025183243-0605, EVT-20261025183604-47b5, EVT-20261025183904-8e38). ADR-0007 was logged twice and appears twice in the report (EVT-20261025183243-0605, EVT-20261025183335-5ae8).
- The amendment, written mid-cycle without a spike, carried three criteria that were wrong as written; the writer found all three by running them (w/crlf count only holds in a fresh checkout; wrong .pyc pathspec; `git worktree add` needs `--detach`) (EVT-20261025183833-d730, corrected EVT-20261025183940-961a). The Test Engineer found a fourth in SPEC-0001 8.1 row 5: a grep for the accented literal that SPEC-0002 forbids in the ASCII test file (EVT-20261025184329-6965).
- Q-0004 was a spec-text question for the Chief Architect, but it was filed with `company ask`, whose `answer` attributes to the CEO. It was resolved at 18:39:40 and still sits under "Needs your decision" in the CEO report with a sentence telling the CEO to ignore it (EVT-20261025184014-1505, reports/cycle-001.md).
- Budget, by ledger timestamps: engineering 2m08s + 2m33s, fix round 1m17s, amendment round 2m29s (about 8.5 min); four reviews about 3.5 min; ADR + amendment + routing gaps about 6 min; verification 2m40s. `budget.consumed` declared "at or past the 30-minute ceiling" at 18:38:34, 13m21s after `cycle.started`; `cycle.ended` at 18m16s (EVT-20261025183834-580f, EVT-20261025184329-1e22). The ceiling figure was not computed from the ledger.
- Environment facts were rediscovered and restated by hand: `python` on PATH is a stub and the interpreter is `C:/Users/Zain/anaconda3/python.exe` 3.7.6 (SPEC-0001 s5, SPEC-0002 s"Acceptance", SPEC-0003, SPEC-0004, SPEC-0005: five restatements); `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` because Anaconda's pytest-arraydiff imports a numpy whose DLL load fails (Head of QA, SPEC-0001 s5); commands run in Git Bash; the branch is `master` while SPEC-0005 s"Dependency" says "main branch". The bash-to-WSL confusion and the master/main mismatch appear in no ledger event at all. The charter required Python 3.8+ before anyone had run the interpreter; Q-0003 then waited for the CEO from 16:05 to 18:25 (EVT-20261025160520-44fd, EVT-20261025182512-9459).
- After the cycle the CEO asked "where is the output?". `git ls-tree master` shows CLAUDE.md, brief.md and the record only; wordstat/, tests/, README.md and examples/ exist solely on `vc/item-0001` and `vc/item-0002`, which the report lists as "Ready to merge" without a path, a worktree command or a run command.

## What surprised us

1. Both rejections of the cycle (docstring escapes, CRLF) were byte-level, not logic-level. The spike proved the reference implementation; it did not prove that a second author copying the contract would reproduce its bytes.
2. Every wrong acceptance criterion (4 of 4) was in text that had not been executed before handoff; the spiked specs produced none. Executors found them by running the commands, not reviewers by reading them.
3. Pre-mortem 10 predicted the clean-checkout failure class and the specs answered it with a fresh-worktree procedure, yet the fixture-bytes case still cost an ADR mid-cycle. A risk that is "addressed" by a verification step is detected, not prevented.
4. More than half the cycle was executive and review time around two executor tasks that took under three minutes each. The framework's overhead per item, not the engineering, set the cycle length.
5. The record told the CEO everything about the process and nothing about how to see the product.

## What we will do differently

- Framework stamp (`init.py`) adds `.gitattributes` with `* text=auto eol=lf` in the first commit; no project rediscovers CRLF (LESSON-0003).
- Every acceptance command, including ones added by an amendment, is executed once by its author before handoff; the ledger note cites the run (LESSON-0001).
- Specs that require docstrings or strings with backslash sequences say so explicitly and make the reviewer check `repr(obj.__doc__)` (LESSON-0002).
- Line-ending verification runs only in a fresh `git worktree add --detach`; stale worktrees are never evidence and `git checkout -- .` does not refresh them (LESSON-0004).
- Non-CEO questions are not filed with `company ask` in this CLI version; they go to `log note --ref SPEC-xxxx` and are closed by a `decision.recorded`. When the CLI gains `ask --for`/`answer --by`, use that (LESSON-0005).
- The Chief of Staff computes the budget from `cycle.started` to now using ledger timestamps and logs the minutes; review and decision rounds are budgeted at plan time, one fix round per item (LESSON-0006).
- Machine facts live in knowledge/ as one lesson each, recorded at kickoff; specs cite the lesson id instead of restating (LESSON-0007). Charter constraints that depend on the machine are written after the probe, not before (LESSON-0008).
- The cycle report gains a "See it" section: branch, `git worktree add --detach` command, run command, and the exact `company gate release` / `approve` commands the CEO's decision triggers (LESSON-0009).
- Chief Architect, cycle 2: fix SPEC-0001 8.1 row 5 (grep the escaped form) and the re-checkout note; say `master`, not `main`, in SPEC-0005. Log an ADR once.
