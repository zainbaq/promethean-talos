---
id: LESSON-0005
title: SPEC-0001 named two mockups but required a capture of one state; break-ready shipped unseen by design
applies_to: ["architecture", "ux", "testing"]
confidence: high
evidence: ["EVT-20261028172846-a974", "EVT-20261028173608-87f6", "company/specs/SPEC-0001-timer-screen-wall-clock-countdown-with-start-pau.md"]
recorded: "2026-10-28T17:57:39Z"
author: learning-officer
---

# SPEC-0001 named two mockups but required a capture of one state; break-ready shipped unseen by design

The SPEC-0001 Goal says the Timer matches mockups/timer.html (idle) and mockups/timer-break.html (break ready), but its capture criterion runs screens.py only on index.html as loaded (idle) and Design QA signs 4 PNGs against timer.html only. The ui-engineer did not capture break-ready because the spec asks only for the idle capture (EVT-20261028172846-a974); head-of-design passed both items on default-state shots only (EVT-20261028173608-87f6); the state became follow-up ITEM-0003.

**Why:** Design QA captures what the spec lists. A state the spec names in Goal but not in the capture criterion gets no visual review, and the design gate passes without having seen it.

**How to apply:** For every mockup or state the spec names, the capture criterion names one capture and the steps to reach the state (seed, click or wait). Design QA derives its capture list from the spec state table; a named state with no capture line is a spec lint failure or a question to the architect before dispatch.
