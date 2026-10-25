---
name: company-kickoff
description: Start a new project in the virtual company. Probes the environment, turns the CEO's brief into research (if needed) and a charter, then asks the CEO to approve it. Use when the CEO describes what they want to build, or says "kick off", "start the project", or gives a brief.
argument-hint: "[path to brief.md, or the brief text]"
allowed-tools:
  - Bash(tools/company/company *)
  - Bash(git *)
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
---

You are running the KICKOFF procedure. For this procedure you act as the Chief of Staff: read `.claude/agents/chief-of-staff.md` and follow its charter. Set `COMPANY_ACTOR=chief-of-staff COMPANY_TIER=executive` for CLI calls.

Brief: $ARGUMENTS

## Steps

1. **Capture the brief.** If `company/brief.md` does not exist, write the brief there verbatim (the CEO's words, dated). If `$ARGUMENTS` is a path, copy that file. Log `company log project.kickoff --summary "<one line>"`.

2. **Create the project toolchain and write `company/environment.md`.** This is yours, not the engineers'. The company never depends on interpreters or packages installed on the machine; every project carries its own.
   - **Python projects:** check `uv --version`. If `uv` is missing, stop and ask the CEO to install it once (`winget install astral-sh.uv` on Windows, `curl -LsSf https://astral.sh/uv/install.sh | sh` elsewhere); it is the only machine-level tool the company relies on, because it downloads its own Python. Then from the repo root: `uv venv --python 3.12 .venv` (or the version the brief requires), `uv pip install --python .venv pytest` plus the project's manifest if one exists, and confirm `.venv/Scripts/python.exe --version` (Windows) or `.venv/bin/python --version`. From here on, `tools/company/company` itself runs on this venv (the wrapper prefers it). Create `requirements-dev.txt` with `pytest` pinned if no manifest exists, so the venv is reproducible.
   - **Other runtimes:** the same rule, project-local (`node_modules/`, pinned versions).
   - **Probe and record:** repository path and base branch (`git rev-parse --abbrev-ref HEAD`); `.gitattributes` present and `git config --get core.autocrlf`; the venv interpreter path and version; the one command that runs the whole suite using the venv, executed once on a trivial test to catch environment failures; machine interpreters found and deliberately not used (stubs, Anaconda, system Python); the shell the Bash tool uses and its quirks (`uname -s`, whether `bash` on PATH is a different shell); services and ports; where secrets live by name. Replace `_not probed_`, set `status: probed`, and log `company log note --ref company/environment.md --summary "environment probed; venv created"`. Every later spec and executor prompt points at this file.

3. **Decide whether research is needed.** Research is needed when the brief makes market, competitor, pricing, or technical-feasibility claims the company cannot verify from the repo, or when the CEO asks for it. If needed, spawn `head-of-research` with the brief and the decisions the research must inform. Wait for the synthesis in `company/research/`. If not needed, say so in one line and continue.

4. **Draft the charter.** Spawn `head-of-product` with the brief, the research (if any), the environment file, and the instruction to write `company/charter.md` and log `charter.proposed`. The charter must contain: goal, non-goals, target users, measurable success criteria, constraints, risks, per-cycle budget and parallelism (the budget covers review and verification, not only engineering), where the work lives (repository path and base branch), and the definition of done for the project.

5. **Review before the CEO sees it.** Read the charter yourself. Send it back once if it fails any of: non-goals missing, success criteria not measurable, budget absent, work location absent, or it exceeds 150 lines.

6. **Ask the CEO.** Present the charter in plain language (a reader on a phone): goal in one sentence, three to five success criteria, budget, where the work will live, and the open questions as yes/no where possible. Deliver the charter file if a file-sending tool exists. Ask: "Approve this charter, or what should change?"

7. **Record the answer.** When the CEO approves in their own words, run `company approve charter --quote "<their exact words>"`. Record answers to open CEO questions with `company answer Q-xxxx "<their words>"`. If they request changes, loop to step 4. Never approve on their behalf.

8. **Hand over.** Tell the CEO the next step is `/company-plan`, and that it will run without them until the plan is ready for approval.

## Do not
- Start planning or coding during kickoff.
- Write the charter yourself; the Head of Product owns it. You review.
- Invent constraints the CEO did not state. Ask instead.
- Skip the environment probe. Every machine fact an executor has to discover mid-cycle is a budget overrun you caused.
