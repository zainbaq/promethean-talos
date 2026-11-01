---
id: LESSON-0001
title: Acceptance commands not executed before handoff were wrong 4 of 4 times in cycle 1
applies_to: ["process", "testing"]
confidence: high
evidence: ["EVT-20261025183833-d730", "EVT-20261025183940-961a", "EVT-20261025184329-6965", "EVT-20261025162839-36df"]
recorded: 2026-10-25T21:41:40Z
author: learning-officer
---

# Acceptance commands not executed before handoff were wrong 4 of 4 times in cycle 1

The SPEC-0003 ADR-0007 amendment was written mid-cycle without a spike and all three of its new criteria were wrong as literally written (w/crlf count holds only in a fresh checkout; .pyc pathspec matched 1 of 4 files; git worktree add needs --detach). SPEC-0001 8.1 row 5 greps an accented literal that SPEC-0002 forbids in the ASCII test file. The four specs whose commands the Chief Architect had executed in a scratch spike before handoff (EVT-20261025162839-36df) produced zero wrong criteria. Executors found every error by running the command, not reviewers by reading it.

**Why:** A criterion that has never been run is a guess with a checkbox; it costs a question round (Q-0004) and a correction decision inside the cycle budget.

**How to apply:** Before any spec or amendment hands to an executor, its author runs every acceptance command once on the current tree and cites the run in the handoff note. Amendments are not exempt; they are the most likely to be wrong.
---
id: LESSON-0002
title: Docstrings copied from a contract lose backslash escapes; check repr of __doc__ not the source
applies_to: ["engineering", "core"]
confidence: high
evidence: ["EVT-20261025182829-d983", "EVT-20261025183032-51d2", "EVT-20261025183117-7a23"]
recorded: 2026-10-25T21:41:40Z
author: learning-officer
---

# Docstrings copied from a contract lose backslash escapes; check repr of __doc__ not the source

ITEM-0001 round 1 was rejected because wordstat/core.py lines 48, 62 and 64 had a real newline inside non-raw docstrings where SPEC-0002 and CONTRACT section 2 have the two characters backslash-n. The engineer pasted the contract text; Python interpreted the escape. The fix d4e314a changed exactly 3 lines and was proven by printing the repr of format_json.__doc__, not by reading the file.

**Why:** A spec that requires docstrings to be character-identical to a contract containing escape sequences is ambiguous to a copy-paste author; source that looks identical in an editor can differ in bytes.

**How to apply:** When a contract docstring or string literal contains a backslash sequence, the spec states whether the file must contain the escape (write a double backslash or a raw string) and the reviewer check is python -c print(repr(obj.__doc__)) compared with the contract text. Put this check in the spec acceptance list, not only in the reviewer notes.
---
id: LESSON-0003
title: Byte-exact fixtures on a core.autocrlf=true machine need .gitattributes in the first commit
applies_to: ["devops", "engineering"]
confidence: high
evidence: ["EVT-20261025182749-daf1", "EVT-20261025183243-0605", "EVT-20261025183604-47b5", "company/decisions/ADR-0007-line-endings-gitattributes-forces-lf-checkouts-b.md"]
recorded: 2026-10-25T21:41:40Z
author: learning-officer
---

# Byte-exact fixtures on a core.autocrlf=true machine need .gitattributes in the first commit

This machine has core.autocrlf=true. The repo stamped by the framework had no .gitattributes, so a fresh worktree or clone checks text files out as CRLF while every committed blob is LF; the SPEC-0003 byte check on examples/sample.txt would fail on a clean checkout even though the commit is correct. Discovered by the Technical Writer at hand-back and independently by the Code Reviewer. Fixing it mid-cycle cost ADR-0007, a SPEC-0003 amendment, a second dispatch of the writer, a second review and a Q-0004 correction, about 8 of the 18 ledger minutes of the cycle.

**Why:** Line-ending conversion is a per-machine git setting; a repo whose tests or README assert exact bytes must carry the rule itself so every clone gives the same bytes.

**How to apply:** The framework stamp (init.py) commits .gitattributes containing the lines * text=auto eol=lf and *.pyc binary before any product file exists. The pre-mortem for any project with byte-exact fixtures names checkout line endings explicitly, not only test-side normalisation (pre-mortem 12 covered assertions, not fixtures).
---
id: LESSON-0004
title: After .gitattributes lands, stale worktrees keep CRLF copies and git checkout -- . does not refresh them
applies_to: ["testing", "devops"]
confidence: high
evidence: ["EVT-20261025183940-961a", "EVT-20261025184329-6965", "company/reports/evidence/cycle-1-verification.txt"]
recorded: 2026-10-25T21:41:41Z
author: learning-officer
---

# After .gitattributes lands, stale worktrees keep CRLF copies and git checkout -- . does not refresh them

A worktree created before .gitattributes existed keeps its CRLF working copies (64 files on vc-live-wt/item-0002, 65 in the verification worktree after merging) because git treats them as stat-clean; the index column is LF. git checkout -- . and git checkout -f -- . were both no-ops. Deleting the stale files and then running git checkout -- . produced w/crlf count 0. Also: git worktree add <path> <branch> fails with already-checked-out while an engineer worktree holds the branch; use --detach.

**Why:** A w/crlf count in an old worktree is not evidence of a defect, and a no-op checkout is not evidence of a fix; both mislead the Test Engineer.

**How to apply:** Verify line endings only inside a fresh git worktree add --detach of the merged commit; the three-file ls-files --eol check is the only eol check an engineer runs in their own worktree. If a stale worktree must be refreshed, delete the affected files first, then git checkout -- .
---
id: LESSON-0005
title: Do not file non-CEO questions with company ask; its answer command attributes to the CEO
applies_to: ["process"]
confidence: high
evidence: ["EVT-20261025183833-d730", "EVT-20261025184014-1505", "company/reports/cycle-001.md"]
recorded: 2026-10-25T21:41:41Z
author: learning-officer
---

# Do not file non-CEO questions with company ask; its answer command attributes to the CEO

Q-0004 was a spec-wording question from the Technical Writer for the Chief Architect. It was filed with company ask, the architect resolved it with a decision.recorded event at 18:39:40, but company answer would have recorded the CEO as answering, so it was left open. It then appeared in the cycle-1 CEO report under Needs your decision with a sentence telling the CEO to ignore it.

**Why:** A question list that mixes CEO decisions with internal routing makes the CEO read and dismiss items that are not theirs, and leaves resolved questions open in questions.md.

**How to apply:** In this CLI version: internal questions go to company log note --ref <SPEC or ITEM> naming the addressee, and are closed by the addressee with decision.recorded or a note. Reserve company ask for questions only the CEO can answer. In CLI versions with ask --for and answer --by, use those and keep questions.md filtered to the questions of the CEO.
---
id: LESSON-0006
title: Cycle 1 budget went to review and decision rounds, and the 30-minute ceiling was declared at 13 ledger minutes
applies_to: ["process"]
confidence: medium
evidence: ["EVT-20261025182513-feef", "EVT-20261025183834-580f", "EVT-20261025184329-1e22"]
recorded: 2026-10-25T21:41:41Z
author: learning-officer
---

# Cycle 1 budget went to review and decision rounds, and the 30-minute ceiling was declared at 13 ledger minutes

By ledger timestamps: cycle.started 18:25:13; executor work 2m08s (ITEM-0001) + 2m33s (ITEM-0002) + 1m17s fix round + 2m29s amendment round, about 8.5 minutes; four reviews about 3.5 minutes; ADR-0007, spec amendment and routing gaps about 6 minutes; verification 2m40s. budget.consumed said at or past the 30-minute ceiling at 18:38:34, which is 13m21s after cycle.started; cycle.ended at 18m16s. The ceiling figure was not derived from the ledger.

**Why:** A budget that is estimated rather than measured cannot be trusted either way: it stopped dispatch early here and could overrun silently elsewhere. Per-item framework overhead (review, decision, re-dispatch) was 2 to 3 times the engineering time.

**How to apply:** The Chief of Staff computes elapsed time as now minus the cycle.started timestamp and logs the minutes in every budget.consumed event. At plan time, budget one review and one fix round per item explicitly; a second fix round or an ADR inside a cycle is a logged budget event, not a surprise.
---
id: LESSON-0007
title: This machine: python on PATH is a stub; use C:/Users/you/anaconda3/python.exe 3.7.6 with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 in Git Bash on branch master
applies_to: ["devops", "testing", "engineering"]
confidence: high
evidence: ["company/specs/SPEC-0001-test-strategy.md", "company/specs/SPEC-0005-constraint-tests-imports-syntax-size.md", "EVT-20261025162839-36df", "EVT-20261025155512-cb7f"]
recorded: 2026-10-25T21:41:42Z
author: learning-officer
---

# This machine: python on PATH is a stub; use C:/Users/you/anaconda3/python.exe 3.7.6 with PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 in Git Bash on branch master

Facts rediscovered by several roles in cycle 1 and restated by hand in five specs (SPEC-0001 s5, SPEC-0002, SPEC-0003, SPEC-0004, SPEC-0005): the python command on PATH is a broken stub; the only interpreter is C:/Users/you/anaconda3/python.exe (CPython 3.7.6, pytest 5.3.5); a bare pytest exits 1 before collection because the Anaconda pytest-arraydiff entry-point plugin imports numpy whose DLL load fails, so every pytest run needs PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 (Head of QA finding); commands in specs are written for Git Bash from the repo root (a bare bash command on this machine routes to WSL); the default branch is master, while SPEC-0005 says main branch. None of this was in knowledge/ when the pre-mortem ran (index empty, EVT-20261025155512-cb7f).

**Why:** Every role that rediscovers an environment fact spends budget and may write it differently; five restatements drifted (main vs master) and one became a CEO question (Q-0003).

**How to apply:** Load this lesson before writing any spec or running any command on this machine. Specs cite LESSON ids for environment facts instead of restating them. New machine facts are recorded here at kickoff by whoever probes the environment, before the charter is written.
---
id: LESSON-0008
title: Charter constraints that depend on the machine were written before the environment probe; Q-0003 cost a CEO round trip
applies_to: ["product", "process"]
confidence: high
evidence: ["EVT-20261025155105-be9e", "EVT-20261025160520-44fd", "EVT-20261025182512-9459"]
recorded: 2026-10-25T21:41:42Z
author: learning-officer
---

# Charter constraints that depend on the machine were written before the environment probe; Q-0003 cost a CEO round trip

The charter (proposed 15:51:05) required Python 3.8+ from the brief. At 16:05:20 the Chief Architect found the only interpreter is 3.7.6 and the Chief of Staff filed Q-0003 for the CEO, who answered at 18:25:12 together with plan approval: verify on 3.7.6, keep code 3.7-compatible. The answer was the proposed default. The kickoff skill is defined as probing the environment, but the probe result did not reach the charter before the CEO approved it.

**Why:** A constraint the machine cannot satisfy is a question the CEO must be asked; asked after charter approval it blocks planning and the answer is almost always the default the executive already proposed.

**How to apply:** Head of Product writes charter constraints about runtime, interpreter and tooling only after the probe has run, and states the probed versions in the charter. If the brief and the machine disagree, the charter proposes the default and the CEO approves it with the charter, not as a separate question later.
---
id: LESSON-0009
title: The cycle report told the CEO nothing about how to see the product; master had no product files
applies_to: ["process", "product"]
confidence: medium
evidence: ["company/reports/cycle-001.md", "EVT-20261025184329-1e22", "EVT-20261025184252-a26e"]
recorded: 2026-10-25T21:41:42Z
author: learning-officer
---

# The cycle report told the CEO nothing about how to see the product; master had no product files

After cycle 1 the CEO asked where the output was. git ls-tree master lists CLAUDE.md, brief.md, company/, tools/ and .claude/ only; wordstat/, tests/, README.md and examples/ exist solely on the unmerged branches vc/item-0001 (d4e314a) and vc/item-0002 (a334866). The report listed the branches under Ready to merge and described reviews, decisions and budget, but gave no worktree command, no run command and no release-gate command. (The CEO question is reported by the Chief of Staff; it is not a ledger event.)

**Why:** The release gate means nothing is on master until the CEO approves, so the CEO can only see the product by checking out a branch; a report that omits that step reads as if there is no product.

**How to apply:** Every cycle report gets a See it section: for each verified item the branch and commit, one git worktree add --detach command, the command that runs the thing (python -m wordstat examples/sample.txt), and the exact company approve release --quote and gate commands that a yes from the CEO triggers. The Chief of Staff pastes this before editing the summary.
