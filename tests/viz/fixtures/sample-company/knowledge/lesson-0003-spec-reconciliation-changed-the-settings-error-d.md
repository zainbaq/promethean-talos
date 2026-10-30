---
id: LESSON-0003
title: Spec reconciliation changed the Settings error display without amending ADR-0002
applies_to: ["architecture"]
confidence: high
evidence: ["EVT-20261028045605-6af3", "EVT-20261028173027-fac6", "company/decisions/ADR-0002-timer-state-model-wall-clock-end-timestamp-setti.md"]
recorded: "2026-10-28T17:57:38Z"
author: learning-officer
---

# Spec reconciliation changed the Settings error display without amending ADR-0002

At plan the architect reconciled SPEC-0002 with the mockups so that the help text becomes the error text (EVT-20261028045605-6af3), while the ADR-0002 Decision still says an inline error paragraph with role=alert becomes visible. Nothing re-read the ADR: talos spec lint passed, Head of Product marked ITEM-0002 ready, and the mismatch surfaced at code review 12 hours later (EVT-20261028173027-fac6) as ITEM-0006.

**Why:** spec lint checks the spec sections, not consistency with the ADRs the spec links. A spec that silently overrides an ADR sentence hands the engineer two contradicting sources and the reviewer finds it after the code exists.

**How to apply:** When a spec reconciliation changes any behaviour an ADR states, amend the ADR in the same step and log the decision. In the spec section Constraints from the record, list the ADR sentences the spec overrides so the reviewer checks them instead of discovering them.
