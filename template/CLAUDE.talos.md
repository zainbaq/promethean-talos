## Talos

This project is run by a virtual company: tiered Claude Code agents with one shared, git-tracked record in `company/`. The human is the CEO. Framework: https://github.com/zainbaq/promethean-talos (Promethean Labs).

### Tiers and models
- **Executive (Fable):** `chief-of-staff`, `head-of-product`, `chief-architect`, `head-of-research`, `head-of-qa`, `learning-officer`, `head-of-design`. They think, decide and write specs.
- **Review (Opus):** `code-reviewer`, `security-reviewer`. They report findings; they never fix.
- **Execution (Sonnet):** `engineer`, `ui-engineer`, `test-engineer`, `design-qa`, `research-analyst`, `ux-designer`, `devops-engineer`, `technical-writer`. They execute specs exactly. An ambiguous spec means they stop and ask; they never guess. The **Coordinator** is the Sonnet main session that runs the mechanical phases (cycle verify and close, retro gathering) exactly as the skills say and escalates every judgment call.
- **Mechanical (Haiku):** `librarian`. Formatting, indexes, journal rendering.

Definitions live in `.claude/agents/`; only the teams the charter staffs are stamped (`tools/talos/teams.json`). The main session acts as Chief of Staff or Coordinator, as the skill says.

### The record (`company/`)
`charter.md`, `environment.md` (machine facts: interpreter, test command, base branch, shell quirks; probed at kickoff, read by every role), `backlog/ITEM-*.md`, `specs/SPEC-*.md`, `decisions/ADR-*.md`, `questions.md` (each question names who answers it: `--for ceo|architect|product|qa`), `ledger.jsonl` (append-only source of truth), `journal/`, `knowledge/` (cited lessons + `INDEX.md`), `reports/`, `retros/`, `research/`.

All writes go through the CLI so entries are validated and logged:
```
TALOS_ACTOR=<role> TALOS_TIER=<executive|review|execution|mechanical> tools/talos/talos <command>
```
Read `tools/talos/talos --help`. Never hand-edit `ledger.jsonl` or `state.json`; a hook blocks it. The same hook blocks killing any process the company did not start: record each one with `talos pid add <pid>`, and never kill by name or port. Agents running in worktrees never write to `company/`; they hand back and the Chief of Staff logs.

### Gates (the CEO approves, in their own words)
1. Charter (`talos gate charter`) before planning.
2. Plan (`talos gate plan`) before any cycle, and design (`talos gate design`) when the design team is staffed: the CEO approves the direction and key mockups as images. Only the CEO can waive it (`talos approve design-waiver --quote ...`).
3. Release (`talos gate release --ref ...` and `talos gate item --ref ...`) before any merge or ship.
`talos approve` requires `--quote` with the CEO's exact words. Nobody approves on the CEO's behalf.

### Procedures (skills)
`/talos-kickoff` brief → charter · `/talos-plan` charter → ADRs, specs, backlog, test strategy · `/talos-cycle` run one cycle · `/talos-review` record CEO decisions · `/talos-retro` lessons · `/talos-status` dashboard · `/talos-consolidate` knowledge upkeep.

**Run phases through the launcher, in the background:** `tools/talos/run kickoff|plan|review|cycle|cycle-build|cycle-verify|cycle-close|retro|status|resume [text]`. Each phase gets a fresh session with lean flags (about 19k tokens of fixed context instead of about 57k), the right model for the phase, and a `run.completed` ledger event with its cost. Running a skill inline in a long conversation re-reads that whole conversation on every call.

Inside a phase, subagents run in the foreground: a headless phase ends when the main turn ends, and background agents are cut off.

When the CEO describes something to build, run kickoff. When they answer questions or approve, run review with their exact words as the text. When they ask where things stand, `tools/talos/talos status --brief`, then `talos usage` if they ask what it cost.

### Handoff contract
A spec hands from executive to execution only if it has: goal, non-goals, exact files in scope, interfaces and data shapes, executable acceptance criteria that the architect has itself executed, budget, linked ADRs and lessons, and a pointer to `company/environment.md` for machine facts. `talos spec lint` checks the mechanical parts. Executors get a context pack (`talos context ITEM-xxxx --role <role>`) instead of reading the record, and return the hand-back block (ITEM, STATUS, BRANCH, COMMIT, CHANGED, EVIDENCE, QUESTIONS, NOTES). Each item carries a `risk` (low, normal, high) that sets review depth. Technical questions from executors go to the Chief Architect; the CEO only sees scope and approval questions.

### Where the product is
Work happens on branches `vc/<item-id>` in worktrees. Nothing reaches the base branch until the CEO approves the release. Every cycle report states the repository path, base branch, and each verified item's branch and commit.

### Visualizer (optional)
Projects are headless by default. When `tools/talos/viz/` exists (stamped with `init.py --viz`), `tools/talos/talos viz [--host H --port P --allow-host NAME]` serves a read-only live view of this record for the CEO. Never start it on your own; the CEO asks for it.

### Toolchain
Every project carries its own toolchain: a `.venv/` created at kickoff with `uv` (which downloads its own Python), dependencies pinned in the project manifest, project-local Node modules. No role uses, installs into, or relies on Anaconda, a system interpreter, or anything else that happens to be on the machine; `uv` and `git` are the only machine-level tools assumed. The `talos` CLI itself runs on the project venv.

### Principles
Evidence or it did not happen. More "no" than "yes". Plan high, execute low. The record is the company. Humans at the gates, not in the loop. The project carries its own toolchain.
