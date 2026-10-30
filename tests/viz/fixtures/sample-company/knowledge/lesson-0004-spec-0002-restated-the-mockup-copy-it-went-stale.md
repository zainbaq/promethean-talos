---
id: LESSON-0004
title: SPEC-0002 restated the mockup copy; it went stale in three minutes and was repeated three times unchecked
applies_to: ["architecture", "product"]
confidence: high
evidence: ["EVT-20261028045913-078d", "EVT-20261028172653-ddd1", "company/specs/SPEC-0002-settings-screen-focus-length-break-length-sound.md"]
recorded: "2026-10-28T17:57:38Z"
author: learning-officer
---

# SPEC-0002 restated the mockup copy; it went stale in three minutes and was repeated three times unchecked

SPEC-0002 (last written 04:55:40Z) says the mockups/settings.html help copy reads 1 to 90 and 1 to 30 and is being aligned, do not ask. The mockup was aligned at 04:58:32Z (EVT-20261028045913-078d) and reads 1 to 120 and 1 to 60. In cycle 1 the ui-engineer reported the mockup ranges as 1-90 and 1-30 (EVT-20261028172653-ddd1), Head of Product created ITEM-0007 from that report, and the retro draft listed it as a surprise (C6); nobody opened the file. The first criterion of ITEM-0007 is already met.

**Why:** A spec sentence that restates the content of another file is a copy nobody updates; executors trust the spec over the file and follow-ups inherit the stale claim.

**How to apply:** Specs point at design files by path and do not restate their copy or ranges. Before creating a follow-up from an engineer or reviewer note about a file, Head of Product opens the file (one rg) and cites the line in the item. ITEM-0007 should drop its first acceptance criterion.
