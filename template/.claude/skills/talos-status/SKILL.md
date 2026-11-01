---
name: talos-status
description: Show where the project stands: charter and plan state, cycle, backlog counts, blocked items, open questions, recent events. Use when the CEO asks "where are we", "status", or opens a session after time away.
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
---

Run `tools/talos/talos status` and show the output.

Then add, in at most five lines for a reader on a phone: what the company is waiting on (CEO decision, running cycle, nothing), the single most important blocked item if any, and the one command that moves things forward (`tools/talos/run kickoff`, `plan`, `cycle`, `review "<the CEO's words>"` or `retro`, or `talos work --detach`, `talos questions` or `talos say --text "<the ask>"` once the project is under way). If the CEO asks what it cost, add the Spend line from `tools/talos/talos status`.

If `company/` does not exist, say the project has not been initialised and point at `/talos:talos`, or `uv run init.py <project>` from a clone of promethean-talos.
