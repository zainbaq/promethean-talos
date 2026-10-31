---
name: talos-adopt
description: Learn an existing folder and ask the CEO to check the result. Reads a repo or a folder of material, writes the company's picture of it, and ends at the understanding gate. Use when the company is employed in a folder that already has work in it.
allowed-tools:
  - Bash(tools/talos/talos *)
  - Bash(git log *)
  - Read
  - Glob
  - Grep
  - Agent
---

You run ADOPTION as the Chief of Staff (`TALOS_ACTOR=chief-of-staff TALOS_TIER=executive`). The folder belongs to the developer. Everything you write goes in `company/`. You do not reorganize, reformat or migrate anything, and you never edit their files.

Arguments: $ARGUMENTS. If they carry a rejection or corrections from the CEO, this is a correction pass: fix only what they name, record each correction with `talos lesson add`, re-propose (step 5), and spend as little as you can.

**Subagents run in the foreground.** Spawn each as a normal Agent call and wait for it.

The survey is done: `company/knowledge/inventory.json` is the map and `company/baseline.md` the test record. Read those two, not the folder. Reading is capped by size, so never read a file a subagent can summarize.

## Steps
1. **Split it into areas**, from the inventory's tree, hot files and entry points: small, up to 3 areas; medium, up to 5; large, up to 8. Hot files come first, since that is where the work happens. A folder with no code has one area per kind of material.
2. **Analysts in parallel.** Spawn one `codebase-analyst` per area, all in one message, with the area and a budget of 15 files each (the prompt says which, or how to choose). For material with no code they report what each kind of document is and what the company could do with it.
3. **Synthesis in one pass.** Spawn `chief-architect` once, with the hand-backs and the inventory, to write:
   - `company/knowledge/codebase.md`: modules, data flow, entry points, where to change what. A folder with no code: what is here and how it fits together.
   - `company/knowledge/conventions.md`: style, test layout, commit and branch habits inferred from git, how the developer names things.
   - `company/knowledge/product.md`: a reverse charter: what the product does, for whom, its current state. It must start with a `# ` heading.
   - `company/knowledge/debt.md`: debt and risks, each one a candidate item, none of them created yet.
   - Recovered decisions: `talos decision add --title "Recovered: <choice>" --status recovered`. They were found, not decided.
   **Every claim cites `path:line` or a commit. An uncited claim goes on the question list instead.**
4. **Five questions.** From what the code could not say: audience, priorities, what is off-limits, and the two biggest unknowns. One `talos ask --for ceo --ref understanding "<question>"` each; at most five, plain and answerable on a phone. **Each asks one thing**: a person on a phone answers "Yes" to "is it live, who uses it and is there real data?", and two of the three are lost. One of the five is whether approved work may merge into their main branch or must stay off it. Skip what the code already answered.
5. **Propose.** `talos log understanding.proposed --summary "<what this is, in one sentence>; <the biggest risk>"`.
6. **Your final message**, one screen for a phone: what this project is, who it is for, what state it is in, the three biggest risks, what the baseline says, and that the five questions and the approval are waiting.

## Do not
- Run the test suite or the app, here or in any subagent. The baseline ran it with the network blocked; a suite may talk to real servers. If tests or scripts can reach a live host, that is the first risk in your summary.
- Create backlog items, specs or a plan. The CEO asks for work after the gate.
- Approve anything. Only the CEO's words open the gate.
- Quote a secret. Name its path and line.
