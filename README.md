# Talos

**Tiered Agents that Learn, Orchestrate and Ship.**

Run a software project as an autonomous, tiered team of Claude Code agents with one shared, git-tracked project record.

By [Promethean Labs](https://promethean-labs.co). MIT licensed.

> In Greek myth, Talos was the bronze automaton Hephaestus built to guard Crete on its own. This Talos is a standing company of agents that works on its own between your decisions.

Stamp this template into any repo, write a brief, and a standing company of roles takes the work from research through design, build, test and release while you approve three kinds of checkpoints from wherever you are, including your phone through Claude Code Remote Control.

```
CEO brief ─► kickoff ─► charter ✔ ─► plan ✔ ─► cycle ─► report ✔ ─► retro ─► cycle …
                        (gate 1)     (gate 2)            (gate 3)
```

## Why

Agents are good at executing precise instructions and bad at guessing. Most "AI team" setups fail because one model does everything at one quality level, nothing is recorded, and nobody says no. This framework fixes those three things:

- **Plan high, execute low.** Executive roles (product, architecture, research, QA, learning) run on the strongest model and write specs. Execution roles run on a cheaper model and follow the spec exactly. If a spec is ambiguous the executor stops and asks; it never guesses.
- **The record is the company.** Charter, backlog, specs, decisions, questions, an append-only ledger, lessons and reports all live in `company/` in your repo. Every write goes through a small CLI that validates it. You can read the whole history from GitHub on a phone.
- **More "no" than "yes".** Every role has a list of things it is forbidden to do. Items are not done until QA logs evidence. Lessons are not kept without citations. Nothing merges without your approval, in your words.

## Quick start

Requirements: Claude Code, git, and [`uv`](https://docs.astral.sh/uv/) (`winget install astral-sh.uv` on Windows). Nothing else: at kickoff the company creates a per-project `.venv` with `uv`, which downloads its own Python, so no project depends on Anaconda, a system interpreter, or anything else on the machine. The record CLI itself runs on that venv (any Python 3.8+ is enough to run `init.py` once).

```bash
git clone https://github.com/zainbaq/promethean-talos
python promethean-talos/init.py /path/to/your/project --brief my-brief.md --teams core,design
cd /path/to/your/project && tools/talos/run kickoff company/brief.md
```

`--teams` staffs only the teams the project needs (`core` always; `research`, `design` when the work calls for them; see `tools/talos/teams.json`). Unstaffed roles are not stamped and cost nothing.

`tools/talos/run <phase>` runs each phase (`kickoff`, `plan`, `review "<your words>"`, `cycle`, `retro`, `status`) as a fresh headless session with lean flags and the right model for the phase, and logs its cost to the ledger. You can also open the project in Claude Code and describe what you want; the session will use the launcher. The company will:

1. Research (if the brief needs it) and draft a **charter**. You approve it.
2. Write ADRs, specs, a backlog with acceptance criteria and a test strategy. You approve the **plan**.
3. Run a **cycle**: engineers implement items in parallel worktrees, reviewers review, QA verifies, and you get a one-screen report with yes/no questions and branches ready to merge. You approve **releases**.
4. Run a **retro** that turns surprises into cited lessons the next cycle reads.

Say "approved" (or what should change) at each gate; `tools/talos/run review "<your words>"` records them. `tools/talos/talos status --brief` tells you where things stand and `tools/talos/talos usage` what it cost, measured from Claude Code's transcripts.

## The cast

| Tier | Model | Roles |
|---|---|---|
| Executive | Fable | Chief of Staff · Head of Product · Chief Architect · Head of Research · Head of QA · Learning Officer |
| Review | Opus | Code Reviewer · Security Reviewer |
| Execution | Sonnet | Engineer (parallel) · Test Engineer · Research Analyst · UX Designer · DevOps Engineer · Technical Writer |
| Mechanical | Haiku | Librarian |

Each role is a markdown file in `.claude/agents/`. Add your own by copying one. Change the model tiers by editing `model:` in the frontmatter.

## What gets stamped into your repo

```
.claude/agents/          15 role definitions
.claude/skills/          /talos-kickoff /talos-plan /talos-cycle /talos-review
                         /talos-retro /talos-status /talos-consolidate
.claude/rules/           conventions that load when anyone touches company/
.claude/settings.json    hooks (status on start, destructive-command guard, log reminder) and permissions, merged with yours
tools/talos/           the stdlib-only record CLI and hook scripts
company/                 the project record
CLAUDE.md                a "Talos" section appended between markers
```

It also adds a `.gitattributes` that forces LF checkouts (byte-exact fixtures survive Windows) and ignores bytecode and test caches. `init.py` is idempotent. Re-run it to pick up framework updates; your own files are kept unless you pass `--force`.

The first thing the company does on a new project is probe the machine (which interpreter actually runs, the test command and its quirks, base branch, shell quirks) into `company/environment.md`, so executors never rediscover those facts mid-cycle.

## The record

```
company/
  charter.md         decisions/ADR-*.md     ledger.jsonl (append-only truth)
  backlog/ITEM-*.md  questions.md           journal/  reports/  retros/
  specs/SPEC-*.md    knowledge/lesson-*.md  research/
```

All writes go through `tools/talos/talos` (`log`, `ask`, `answer`, `item`, `spec`, `decision`, `lesson`, `cycle`, `approve`, `gate`, `status`, `report`, `usage`, `journal`, `consolidate`). A hook blocks direct edits to the ledger. See `docs/DESIGN.md` for the event model and why files beat a database here.

## Honest limits

- It is not autonomous without you. The three gates are what keep it on course.
- "Learning" means cited lessons that later skills load, not model training.
- Cycles cost tokens, and most of the cost is not engineering. In the first live run, engineering took about a minute per item; review rounds, architecture decisions and verification took the rest. Budget the whole loop; the Chief of Staff stops at the ceiling.
- Executors on cheaper models are reliable when specs are precise. They are not a substitute for review: the first run's only real defect (lost escape sequences in docstrings) passed every test and was caught by the Opus reviewer.
- Headless or scheduled runs must not use `claude --bare`, which disables the hooks and agents this template relies on.

## Docs

- [docs/DESIGN.md](docs/DESIGN.md) — principles, operating model, record schema, Claude Code mapping
- [docs/ROLES.md](docs/ROLES.md) — each role's charter in prose
- [docs/EXTENDING.md](docs/EXTENDING.md) — adding roles, skills, hooks, a storage adapter
- [examples/brief-mdm.md](examples/brief-mdm.md) — the brief for the framework's first client

## Licence

MIT. Built and maintained by Promethean Labs.
