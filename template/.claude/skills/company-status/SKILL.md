---
name: company-status
description: Show where the project stands: charter and plan state, cycle, backlog counts, blocked items, open questions, recent events. Use when the CEO asks "where are we", "status", or opens a session after time away.
allowed-tools:
  - Bash(tools/company/company *)
  - Read
---

Run `tools/company/company status` and show the output.

Then add, in at most five lines for a reader on a phone: what the company is waiting on (CEO decision, running cycle, nothing), the single most important blocked item if any, and the one command that moves things forward (`/company-kickoff`, `/company-plan`, `/company-cycle`, `/company-review`, or `/company-retro`).

If `company/` does not exist, say the project has not been initialised and point at `python init.py <project>` from the virtual-company repo.
