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

Requirements: Claude Code, git, and [`uv`](https://docs.astral.sh/uv/) (`winget install astral-sh.uv` on Windows). Nothing else: at kickoff the company creates a per-project `.venv` with `uv`, which downloads its own Python, so no project depends on Anaconda, a system interpreter, or anything else on the machine. The record CLI itself runs on that venv (`uv run` finds its own Python for `init.py`).

**With the plugin.** Installed for one project, from the folder you want a company in:

```bash
claude plugin marketplace add zainbaq/promethean-talos --scope project
claude plugin install talos@promethean-talos --scope project
```

Then say `/talos:talos` in Claude Code, with or without what you want done. In a repo with commits it stamps with your current branch protected, so the work goes on `talos/work` and only you merge it. `/talos:talos staff design` adds a team and `/talos:talos upgrade` picks up a newer Talos. Updating the plugin itself is `claude plugin update talos@promethean-talos --scope project`.

**With a clone.** The same files, pinned to the commit you cloned:

```bash
git clone https://github.com/zainbaq/promethean-talos
uv run promethean-talos/init.py /path/to/your/project --brief my-brief.md --teams core,design
cd /path/to/your/project && tools/talos/talos doctor && tools/talos/talos start
```

Either way the files live in your project and everything the company makes stays there. `uv run init.py <project> --upgrade` keeps any agent or skill you changed and lists what's new; `--add-team gtm` staffs one more team.

In cmd or PowerShell on Windows, use `tools\talos\talos.cmd` and `tools\talos\run.cmd`. If a run stops on a usage limit, `tools/talos/run resume` continues it. `tools/talos/talos status` always ends with the next step.

`--teams` staffs only the teams the project needs (`core` always; `research`, `design` when the work calls for them; see `tools/talos/teams.json`). Unstaffed roles are not stamped and cost nothing.

`tools/talos/run <phase>` runs each phase (`kickoff`, `plan`, `review "<your words>"`, `cycle`, `retro`, `status`) as a fresh headless session with lean flags and the right model for the phase, and logs its cost to the ledger. You can also open the project in Claude Code and describe what you want; the session will use the launcher. The company will:

1. Research (if the brief needs it) and draft a **charter**. You approve it.
2. Write ADRs, specs, a backlog with acceptance criteria and a test strategy. You approve the **plan**.
3. Run a **cycle**: engineers implement items in parallel worktrees, reviewers review, QA verifies, and you get a one-screen report with yes/no questions and branches ready to merge. You approve **releases**.
4. Run a **retro** that turns surprises into cited lessons the next cycle reads.

Say "approved" (or what should change) at each gate; `tools/talos/run review "<your words>"` records them. `tools/talos/talos status --brief` tells you where things stand and `tools/talos/talos usage` what it cost, measured from Claude Code's transcripts.

### The control room

Once it is employed, ask for anything: `tools/talos/talos say --text "add CSV export"`, then `tools/talos/talos work --detach --max-usd 10`, which keeps going after you close Claude. `tools/talos/talos say --text stop` stops it once the phase under way ends, and `tools/talos/talos questions` shows what it is waiting to hear. Each phase stops at what is left of the limit, and each start of the runner gets a new limit ($50 if you don't say). Triage answers it or picks a route and says the cost first. Marketing and launch work needs `--teams core,gtm`; those roles draft and you send.

In a repo you want left alone, stamp with `--protect main`. The company then never changes `main`: its files and all approved work go on a local `talos/work` branch, and only you merge from there. `tools/talos/talos protect main --off` lifts the rule. The record is saved on its own `talos/record` branch. Git 2.28 or later refuses every change to the branch outright; on older git, a change hidden in a script is caught when the phase ends, and the queue stops until you say whose it was.

Two options are off until you turn them on: `tools/talos/talos automerge on` merges verified low-risk fast-lane fixes without asking, and `tools/talos/talos notify <url>` posts a gate's name, and nothing about its content, to an address you choose such as an ntfy topic.

Every project gets a control room unless you stamp it with `--headless`. Start it from the project root:

```bash
tools/talos/talos viz                                  # http://127.0.0.1:8000/
tools/talos/talos viz --host 0.0.0.0 --allow-host my-pc # reachable from your phone, e.g. over Tailscale
```

It is a page over the project record, standard library only, and it is also where you steer: approve or reject gates, answer questions, send the company a message and set the preset, from the link it prints at start (`--read-only` turns that off). Its Canopy page shows the company as a tree, with what each role is doing. Your decisions wait in the record until `tools/talos/talos work` is running.  The growth rings show one ring per cycle, an arc per phase run sized by its cost and a tick per ledger event; hover or tap any mark for what happened, who did it and what the run cost. Timeline lists every event, filterable, and Work shows the backlog by status. It updates live while a phase runs, and the project name in the header switches to any other Talos project next to this one (`--scan DIR` to look elsewhere, `--no-scan` for just this one).

## The cast

| Tier | Model | Roles |
|---|---|---|
| Executive | Opus on the default medium preset; Fable only on heavy; Sonnet on lite | Chief of Staff · Head of Product · Chief Architect · Head of Research · Head of QA · Learning Officer · Head of Design |
| Review | Opus | Code Reviewer · Security Reviewer |
| Execution | Sonnet | Engineer (parallel) · UI Engineer · Test Engineer · Design QA · Research Analyst · UX Designer · DevOps Engineer · Technical Writer |
| Mechanical | Haiku | Librarian |

Each role is a markdown file in `.claude/agents/`. Add your own by copying one. `tools/talos/talos preset lite|medium|heavy` sets which model each role uses; a role's `model:` line is only the fallback. GTM adds Head of GTM and GTM Analyst, productization adds Head of Productization, and Codebase Analyst reads an existing folder when the company adopts it.

## What gets stamped into your repo

```
.claude/agents/          the staffed teams' roles (22 in all)
.claude/skills/          /talos-kickoff /talos-adopt /talos-plan /talos-cycle /talos-review
                         /talos-retro /talos-status /talos-consolidate /talos-triage
                         /talos-task /talos-department /talos-design-revise
.claude/rules/           conventions that load when anyone touches company/
.claude/settings.json    hooks (status on start, destructive-command guard, log reminder) and permissions, merged with yours
tools/talos/           the stdlib-only record CLI and hook scripts
tools/talos/viz/         the control room, left out by --headless
company/                 the project record
CLAUDE.md                a "Talos" section appended between markers
```

It also adds a `.gitattributes` that forces LF checkouts (byte-exact fixtures survive Windows) and ignores bytecode and test caches. `init.py --upgrade` picks up framework updates and shows what changed; files you edited are kept unless you pass `--force`.

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
