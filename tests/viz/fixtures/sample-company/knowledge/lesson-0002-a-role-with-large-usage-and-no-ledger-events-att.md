---
id: LESSON-0002
title: "A role with large usage and no ledger events: attribute by parent session before naming a cause"
applies_to: ["process", "devops"]
confidence: high
evidence: ["EVT-20261028175110-942b", "tools/talos/usage.py"]
recorded: "2026-10-28T17:57:38Z"
author: learning-officer
---

# A role with large usage and no ledger events: attribute by parent session before naming a cause

talos usage --cycle 1 charged chief-architect 1.52M tokens (35 percent) while talos events --cycle 1 shows no chief-architect event. The transcripts settle it in one query: all 20 calls are one subagent (agent-aeb94a92, .meta.json agentType chief-architect) under session 5f93c509, which is the session field of the cycle-close run.completed EVT-20261028175110-942b. The retro draft guessed plan and spec work and called the cause unprovable.

**Why:** talos usage reports by role and item and drops the parent session, so a subagent spawned by a mechanical phase is booked to the role, and 76 percent of cycle 1 tokens sat under several or dash. A cost cause that is guessed cannot be acted on.

**How to apply:** When the most expensive role has no events in the cycle, match the subagent parent folder under ~/.claude/projects/<slug>/<session>/subagents/ to the session ids in run.completed events, and name the phase that spawned it. Extend tools/talos/usage.py collect() to record the parent session so talos usage can print spend by phase.
