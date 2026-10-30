---
id: LESSON-0001
title: cycle-close spent its run on queue-filling and ended with no report and no cycle end
applies_to: ["process", "devops"]
confidence: high
evidence: ["EVT-20261028175110-942b", "EVT-20261028172428-4435"]
recorded: "2026-10-28T17:57:37Z"
author: learning-officer
---

# cycle-close spent its run on queue-filling and ended with no report and no cycle end

The cycle 1 close run (EVT-20261028175110-942b, sonnet, $5.58, logged success) never ran talos cycle end or talos report: the ledger has no cycle.closed event, company/reports/cycle-001.md does not exist, and talos status --brief still reads "cycle 1 open" at retro time. The run time went to close step 2 (keep the queue full): a chief-architect subagent in session 5f93c509 ran 17:41:06-17:50:29Z, 20 calls, 1.52M tokens, wrote four files to its own scratchpad and nothing under company/, and logged no spec, decision or note.

**Why:** run.completed success records that the session exited, not that the phase outputs exist. A close that does step 2 before step 4 can exhaust its turns and leave the CEO with no report, the ledger with an open cycle, and the retro with nothing to cite.

**How to apply:** In the close phase run step 4 first (talos cycle end, talos report, chief-of-staff summary), then step 2 (spec the next proposed items) with whatever budget remains. Before logging run.completed for cycle-close, check that company/reports/cycle-NNN.md exists and a cycle.closed event is in the ledger; if either is missing the run is a failure, not a success.
