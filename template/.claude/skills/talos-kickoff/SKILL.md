---
name: talos-kickoff
description: Start a new project in the virtual company. Probes the environment, turns the CEO's brief into research (if needed) and a charter, then asks the CEO to approve it. Use when the CEO describes what they want to build, or says "kick off", "start the project", or gives a brief.
argument-hint: "[path to brief.md, or the brief text]"
allowed-tools:
  - Bash(tools/talos/talos *)
  - Bash(git *)
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Agent
---

You are running the KICKOFF procedure. For this procedure you act as the Chief of Staff: read `.claude/agents/chief-of-staff.md` and follow its charter. Set `TALOS_ACTOR=chief-of-staff TALOS_TIER=executive` for CLI calls.

Brief: $ARGUMENTS

## Steps

1. **Make sure the project toolchain exists, then write `company/environment.md`.** This comes first because the record CLI itself runs on the project venv. The company never depends on interpreters or packages installed on the machine; every project carries its own.
   - **Projects with a user interface (design team staffed):** everything stays inside the project. Node goes into the venv (`uv pip install --python .venv nodeenv`, then `.venv/Scripts/nodeenv -p --node=lts --prebuilt`, or `.venv/bin/nodeenv` elsewhere); Playwright and its browser into the venv (`uv pip install --python .venv playwright`, then `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python -m playwright install --only-shell chromium`, about 280MB); axe-core into the project (`npm install --prefix . axe-core@4` with `.venv/Scripts` first on PATH). Record all three in the environment file. Never install Node, browsers or npm packages globally; a tool that cannot be made project-local is a CEO question.
   - **Python projects:** if `.venv/` already exists (init.py creates it when `uv` is available), confirm `.venv/Scripts/python.exe --version` (Windows) or `.venv/bin/python --version`. Otherwise check `uv --version`; if `uv` is missing, stop and ask the CEO to install it once (`winget install astral-sh.uv` on Windows, `curl -LsSf https://astral.sh/uv/install.sh | sh` elsewhere); it is the only machine-level tool the company relies on, because it downloads its own Python. Then from the repo root: `uv venv --python 3.12 .venv` (or the version the brief requires) and `uv pip install --python .venv pytest` plus the project's manifest if one exists. Create `requirements-dev.txt` with `pytest` pinned if no manifest exists, so the venv is reproducible.

2. **Capture the brief.** If `company/brief.md` does not exist, write the brief there verbatim (the CEO's words, dated). If `$ARGUMENTS` is a path, copy that file. Log `talos log project.kickoff --summary "<one line>"` (this is the first CLI call and proves the venv works).

3. **Finish the environment file.**
   - **Other runtimes:** the same rule, project-local (`node_modules/`, pinned versions).
   - **Probe and record:** repository path and base branch (`git rev-parse --abbrev-ref HEAD`); `.gitattributes` present and `git config --get core.autocrlf`; the venv interpreter path and version; the one command that runs the whole suite using the venv, executed once on a trivial test to catch environment failures; machine interpreters found and deliberately not used (stubs, Anaconda, system Python); the shell the Bash tool uses and its quirks (`uname -s`, whether `bash` on PATH is a different shell); services and ports; where secrets live by name. Replace `_not probed_`, set `status: probed`, and log `talos log note --ref company/environment.md --summary "environment probed; venv created"`. Every later spec and executor prompt points at this file.

4. **Decide whether research is needed.** Research is needed when the brief makes market, competitor, pricing, or technical-feasibility claims the company cannot verify from the repo, or when the CEO asks for it. If needed and the research team is staffed (`talos status --brief` shows the teams), spawn `head-of-research`; if it is not staffed, ask the CEO to add it (step 7 gives the command) with the brief and the decisions the research must inform. Wait for the synthesis in `company/research/`. If not needed, say so in one line and continue.

5. **Draft the charter.** Spawn `head-of-product` with the brief, the research (if any), the environment file, and the instruction to write `company/charter.md` and log `charter.proposed`. The charter must contain: goal, non-goals, target users, measurable success criteria, constraints, risks, per-cycle budget and parallelism (the budget covers review and verification, not only engineering), where the work lives (repository path and base branch), the definition of done for the project, **project size** (`small`: a few items, one or two cycles, no new infrastructure; `medium`: the default; `large`: many parallel items or several systems), set with `talos size <size>` because it scales the whole plan, and **teams staffed**: `core` always, plus `research`, `design` (any user interface) and others from `tools/talos/teams.json` only when the work needs them. Every unstaffed role costs nothing; every staffed one adds to each session's context.

6. **Review before the CEO sees it.** Read the charter yourself. Send it back once if it fails any of: non-goals missing, success criteria not measurable, budget absent, work location absent, or it exceeds 150 lines.

7. **Ask the CEO.** Present the charter in plain language (a reader on a phone): goal in one sentence, three to five success criteria, budget, where the work will live, the project size, the teams to staff, and the open questions as yes/no where possible. Deliver the charter file if a file-sending tool exists. Ask: "Approve this charter, or what should change?"

8. **Record the answer.** When the CEO approves in their own words, run `talos approve charter --quote "<their exact words>"`. Record answers to open CEO questions with `talos answer Q-xxxx "<their words>"`. If they request changes, loop to step 5. Never approve on their behalf. If the approved teams differ from those stamped (`talos status --brief`), give the CEO the exact command to run once, interactively or from a shell, because headless sessions cannot write under `.claude/`: `python <path to promethean-talos>/init.py . --teams <list>`.

9. **Hand over.** Tell the CEO the next step is the plan (`tools/talos/run plan`), and that it will run without them until the plan is ready for approval.

## Do not
- Start planning or coding during kickoff.
- Write the charter yourself; the Head of Product owns it. You review.
- Invent constraints the CEO did not state. Ask instead.
- Skip the environment probe. Every machine fact an executor has to discover mid-cycle is a budget overrun you caused.
