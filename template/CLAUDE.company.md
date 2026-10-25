## Virtual Company

This project is run by a virtual company: tiered Claude Code agents with one shared, git-tracked record in `company/`. The human is the CEO. Framework: https://github.com/promethean-labs/virtual-company (Promethean Labs).

### Tiers and models
- **Executive (Fable):** `chief-of-staff`, `head-of-product`, `chief-architect`, `head-of-research`, `head-of-qa`, `learning-officer`. They think, decide and write specs.
- **Review (Opus):** `code-reviewer`, `security-reviewer`. They report findings; they never fix.
- **Execution (Sonnet):** `engineer`, `test-engineer`, `research-analyst`, `ux-designer`, `devops-engineer`, `technical-writer`. They execute specs exactly. An ambiguous spec means they stop and ask; they never guess.
- **Mechanical (Haiku):** `librarian`. Formatting, indexes, journal rendering.

Definitions live in `.claude/agents/`. The main session acts as Chief of Staff when running a `/company-*` skill.

### The record (`company/`)
`charter.md`, `environment.md` (machine facts: interpreter, test command, base branch, shell quirks; probed at kickoff, read by every role), `backlog/ITEM-*.md`, `specs/SPEC-*.md`, `decisions/ADR-*.md`, `questions.md` (each question names who answers it: `--for ceo|architect|product|qa`), `ledger.jsonl` (append-only source of truth), `journal/`, `knowledge/` (cited lessons + `INDEX.md`), `reports/`, `retros/`, `research/`.

All writes go through the CLI so entries are validated and logged:
```
COMPANY_ACTOR=<role> COMPANY_TIER=<executive|review|execution|mechanical> tools/company/company <command>
```
Read `tools/company/company --help`. Never hand-edit `ledger.jsonl` or `state.json`; a hook blocks it. Agents running in worktrees never write to `company/`; they hand back and the Chief of Staff logs.

### Gates (the CEO approves, in their own words)
1. Charter (`company gate charter`) before planning.
2. Plan (`company gate plan`) before any cycle.
3. Release (`company gate release --ref ...` and `company gate item --ref ...`) before any merge or ship.
`company approve` requires `--quote` with the CEO's exact words. Nobody approves on the CEO's behalf.

### Procedures (skills)
`/company-kickoff` brief → charter · `/company-plan` charter → ADRs, specs, backlog, test strategy · `/company-cycle` run one cycle · `/company-review` record CEO decisions · `/company-retro` lessons · `/company-status` dashboard · `/company-consolidate` knowledge upkeep.

When the CEO describes something to build, run `/company-kickoff`. When they answer questions or approve, run `/company-review`. When they ask where things stand, `/company-status`.

### Handoff contract
A spec hands from executive to execution only if it has: goal, non-goals, exact files in scope, interfaces and data shapes, executable acceptance criteria that the architect has itself executed, budget, linked ADRs and lessons, and a pointer to `company/environment.md` for machine facts. Executors return the hand-back block (ITEM, STATUS, BRANCH, COMMIT, CHANGED, EVIDENCE, QUESTIONS, NOTES). Technical questions from executors go to the Chief Architect; the CEO only sees scope and approval questions.

### Where the product is
Work happens on branches `vc/<item-id>` in worktrees. Nothing reaches the base branch until the CEO approves the release. Every cycle report states the repository path, base branch, and each verified item's branch and commit.

### Toolchain
Every project carries its own toolchain: a `.venv/` created at kickoff with `uv` (which downloads its own Python), dependencies pinned in the project manifest, project-local Node modules. No role uses, installs into, or relies on Anaconda, a system interpreter, or anything else that happens to be on the machine; `uv` and `git` are the only machine-level tools assumed. The `company` CLI itself runs on the project venv.

### Principles
Evidence or it did not happen. More "no" than "yes". Plan high, execute low. The record is the company. Humans at the gates, not in the loop. The project carries its own toolchain.
