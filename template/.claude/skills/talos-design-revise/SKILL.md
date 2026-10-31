---
name: talos-design-revise
description: Revise the design only, from the CEO's feedback, and re-open the design gate. Use when the CEO rejects or wants changes to the design direction or mockups. The plan stays as it is unless the revision changes what an item must build.
argument-hint: "[the CEO's feedback, in their words]"
allowed-tools:
  - Bash(tools/talos/talos *)
  - Read
  - Glob
  - Grep
  - Agent
---

You run the DESIGN REVISION as the Chief of Staff (`TALOS_ACTOR=chief-of-staff TALOS_TIER=executive`). This is the cheap path: it exists so a design rejection does not rerun the plan. A plan rerun cost $18 to $40 on a real project; stay well under a fifth of that.

The CEO said: $ARGUMENTS

**Subagents run in the foreground.** Spawn each as a normal Agent call and wait for it.

## Steps
1. `talos status --brief`. If `company/design/direction.md` does not exist, there is nothing to revise: say so and stop.
2. Spawn `head-of-design` with the CEO's words quoted exactly, `company/design/direction.md` and the mockups folder. It revises the direction, tokens and mockups the feedback touches, screenshots them, and leaves the rest alone. If the feedback asks for a different direction altogether, it redoes the direction rather than patching it.
3. Only if screen copy or a flow changed, spawn `ux-designer` for those screens.
4. **Plan impact.** Ask the Head of Design one thing in its hand-back: does this change what any ready item must build? If yes, spawn `chief-architect` with only those items and the changed mockups to amend their specs (`talos spec lint` must pass). If no, do not touch the plan.
5. `talos log design.proposed --summary "revised: <what changed, one line>"`. This re-opens the gate.
6. Tell the CEO on one screen: what changed, the phone-width light and dark images, and whether the plan moved.

## Do not
- Rerun the plan, the backlog or the test strategy.
- Approve the design. Only the CEO's words open the gate.
