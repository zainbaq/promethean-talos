# Virtual Company — Design

**A Promethean Labs framework for running a software project as an autonomous, tiered team of Claude Code agents with a shared, git-tracked project record.**

Status: v0.1 design · 2026-10-25 · Owner: Zain (CEO) · Drafted by Claude (Fable)

---

## 1. The idea in one paragraph

A repo template that turns Claude Code from a chat into an operating model. You stamp it into any project, write a brief, and a standing company of roles takes the work from research through design, build, test and release, while you approve a small number of checkpoints from your phone. Senior roles think and plan on the strongest model; execution roles carry out those plans exactly on cheaper, faster models. Every role reads from and writes to one shared project record, so knowledge compounds across cycles and the company gets better at *this* project the longer it works on it.

## 2. Principles

1. **Plan high, execute low.** Executive and planning roles run on Fable. Execution roles run on Sonnet and do exactly what the spec says. Mechanical roles run on Haiku. A spec that an executor has to reinterpret is a failed spec, and the fix is upstream.
2. **The record is the company.** No knowledge lives only in a chat. Decisions, specs, questions, lessons, evidence and status live in `company/`, in files, in git, reviewable from a phone.
3. **Humans at the gates, not in the loop.** The CEO approves three things: the charter, the plan, and each release. Everything in between is autonomous and budgeted.
4. **Evidence or it did not happen.** A work item is done when QA has run it and logged proof. A lesson is kept when it cites the ledger event that taught it.
5. **More "no" than "yes".** Every role has a list of things it is forbidden to do. Scope creep, silent assumptions and unlogged changes are the enemy, not slowness.
6. **Portable and boring.** Plain markdown, JSON Lines and a stdlib-only Python CLI. No database or service required. A SQLite adapter is an optional extension, never a dependency.

## 3. Operating model

### 3.1 Cast

| Tier | Model | Role | Owns | Forbidden |
|---|---|---|---|---|
| **Executive** | Fable | **Chief of Staff** (orchestrator) | Runs cycles, assigns work, holds scope and budget, prepares CEO reports, merges after approval | Writing product code; changing the charter; exceeding budget |
| Executive | Fable | **Head of Product** | Charter, backlog, acceptance criteria, prioritisation, open questions to CEO | Technical design; implementation |
| Executive | Fable | **Chief Architect** | Architecture, ADRs, work specs for engineers, interface contracts, tech choices | Implementation beyond spikes; changing scope |
| Executive | Fable | **Head of Research** | Research plans, synthesis, market and technical findings with sources | Making product decisions |
| Executive | Fable | **Head of QA** | Test strategy, acceptance test definitions, release verdicts | Fixing code |
| Executive | Fable | **Learning Officer** | Retros, lessons, knowledge consolidation, pre-mortems | Any delivery work |
| **Review** | Opus | **Code Reviewer** | Diff review against spec and standards | Rewriting code; approving its own tier's work |
| Review | Opus | **Security Reviewer** | Threat review, secrets, PII, dependency risk | Fixing code |
| **Execution** | Sonnet | **Engineer** (N in parallel) | Implements one spec in one worktree, tests included | Interpreting ambiguity; touching files outside the spec; merging |
| Execution | Sonnet | **Test Engineer** | Writes and runs tests from QA's definitions, logs evidence | Changing product code to make tests pass |
| Execution | Sonnet | **Research Analyst** | Executes a research plan, returns sourced findings | Drawing strategic conclusions |
| Execution | Sonnet | **UX Designer** | Flows, wireframe specs, copy, design tokens from the architect's constraints | Implementation |
| Execution | Sonnet | **DevOps Engineer** | CI, containers, environments, release mechanics per spec | Infra not in spec |
| Execution | Sonnet | **Technical Writer** | README, docs, runbooks from the record | Inventing behaviour not in the record |
| **Mechanical** | Haiku | **Librarian** | Renders ledger to journal, indexes knowledge, formats, checks links | Judgment calls |

Roles are cheap to add. Each is a markdown file in `.claude/agents/`. A project can add `Data Engineer`, `Compliance Officer`, `Growth Lead` and so on by copying a template.

### 3.2 The cycle

```
   CEO brief
      │
      ▼
 ┌─ KICKOFF ──────────────────────────────────────────────┐
 │ Head of Research: landscape + feasibility (if asked)    │
 │ Head of Product: charter (goal, non-goals, users,      │
 │   success criteria, constraints, budget)               │
 └────────────────────────── CEO approves charter ◄───────┘  gate 1
      │
      ▼
 ┌─ PLAN ─────────────────────────────────────────────────┐
 │ Chief Architect: architecture + ADRs + specs           │
 │ Head of Product: backlog with acceptance criteria      │
 │ Head of QA: test strategy + acceptance tests           │
 │ Learning Officer: pre-mortem from past lessons         │
 └────────────────────────── CEO approves plan ◄──────────┘  gate 2
      │
      ▼
 ┌─ EXECUTE (repeat per cycle, within budget) ────────────┐
 │ Chief of Staff: pick independent items, assign         │
 │ Engineers (parallel, own worktrees): implement + tests │
 │ Test Engineer: run acceptance tests, log evidence      │
 │ Code + Security Reviewers: review, request changes     │
 │ Chief of Staff: cycle report + open questions          │
 └────────────────────────── CEO reviews report/PRs ◄─────┘  gate 3
      │
      ▼
 ┌─ RETRO ────────────────────────────────────────────────┐
 │ Learning Officer: what surprised us → lessons           │
 │ Librarian: consolidate knowledge, render journal       │
 └────────────────────────────────────────────────────────┘
      │
      └──► next cycle
```

Gates 1 and 2 happen once per project (and again on a re-plan). Gate 3 happens every cycle and is designed to take five minutes on a phone: one report, a list of PRs, a list of yes/no questions.

### 3.3 Handoff contract between tiers

Executive roles produce **specs**. Execution roles consume specs. A spec is valid only if it has:

- Goal and non-goals
- Exact files or modules in scope
- Interfaces and data shapes
- Acceptance criteria that a Test Engineer can execute
- Budget (time or token ceiling)
- Links to the ADRs and lessons that constrain it

An executor who finds the spec ambiguous **stops that item, files a question in the record, and moves on**. Guessing is the one thing an executor is never allowed to do. This is the single most important rule in the framework; it is what makes cheap models safe.

### 3.4 Budgets

The charter sets a per-cycle budget (wall-clock hours or a token figure) and a maximum parallelism. The Chief of Staff logs budget consumption to the ledger and stops the cycle at the ceiling with a partial report rather than overrunning.

## 4. The shared project record (`company/`)

Everything is a file, git-tracked, in the project repo.

```
company/
  charter.md               # approved charter; status + approval event id at top
  backlog/
    ITEM-0001.md           # one item per file: status, owner, spec link, acceptance, evidence
  specs/
    SPEC-0001-*.md         # architect → engineer handoffs
  decisions/
    ADR-0001-*.md          # architecture decision records
  questions.md             # open questions for the CEO; answered inline, then logged
  ledger.jsonl             # append-only event log (the source of truth for "what happened")
  journal/
    2026-10-25.md          # human-readable rendering of the ledger per day (Librarian)
  knowledge/
    INDEX.md               # one line per lesson
    lesson-*.md            # one lesson per file, with evidence and applies_to tags
  reports/
    cycle-001.md           # what the CEO reads on the phone
  retros/
    cycle-001.md
  research/
    *.md                   # sourced findings
```

### 4.1 Ledger events

```json
{"ts":"2026-10-25T14:02:11Z","actor":"engineer","role_tier":"execution","event":"item.completed",
 "ref":"ITEM-0007","summary":"Implemented cluster registry per SPEC-0003","evidence":["tests/test_registry.py: 14 passed"],
 "branch":"vc/item-0007","cycle":2}
```

Event types: `project.kickoff`, `charter.proposed|approved`, `plan.proposed|approved`, `item.created|assigned|started|blocked|completed|verified|rejected`, `question.asked|answered`, `decision.recorded`, `review.requested|passed|changes_requested`, `release.proposed|approved|shipped`, `lesson.recorded`, `budget.consumed`, `cycle.started|ended`.

Agents never hand-write JSON. They call the CLI, which validates and appends:

```bash
company log item.completed --ref ITEM-0007 --summary "..." --evidence "tests: 14 passed" --branch vc/item-0007
```

### 4.2 Why files and not a database first

- Reviewable from a phone through GitHub without any service running.
- Diffable, so a PR shows exactly what the company learned and decided.
- Zero dependencies for people who clone the public repo.
- A SQLite adapter (`company db sync`) can index the same JSONL for queries later. The CLI is the abstraction; the storage behind it can change.

### 4.3 How knowledge compounds

- **Lessons** are one fact per file with `applies_to` tags (`engineering`, `testing`, `research`, `product`, a module name), `evidence` (ledger event ids), and `confidence`.
- **Skills load lessons by tag.** The `company-plan` skill reads lessons tagged `product` and `architecture`; an Engineer's spec links the lessons that constrain it; the Head of QA reads `testing` lessons before writing acceptance tests.
- **Retros convert surprises to lessons**: the Learning Officer reads the cycle's ledger, finds blocked items, rejected reviews, re-opened bugs and budget overruns, and writes lessons that cite them.
- **Consolidation** merges duplicates, deletes lessons contradicted by later evidence, and keeps `INDEX.md` short enough to load every time.
- **Pre-mortem** at plan time: the Learning Officer lists the lessons most likely to bite this plan and the architect must address each one in the specs.

This is journaling plus retrieval, not model training. It works when lessons are specific and cited, and it decays when they are vague. The Learning Officer's charter forbids vague lessons.

## 5. Claude Code mapping

| Framework concept | Claude Code primitive |
|---|---|
| Role | `.claude/agents/<role>.md` with `model` tier, allowed tools, system prompt |
| Procedure (kickoff, plan, cycle, review, retro, consolidate, status) | `.claude/skills/company-<procedure>/SKILL.md` |
| Parallel engineers in isolation | Agent tool with worktree isolation, or sessions, one branch per item |
| Deterministic multi-step runs | Workflow tool scripts (optional; the skills work without it) |
| Gates and guard rails | Hooks in `.claude/settings.json` (session-start status injection, dangerous-command blocks, stop reminders to log) plus the `company gate` CLI check |
| Project constitution | `CLAUDE.md` section describing the operating model and pointing at `company/` |
| Standing knowledge | `company/knowledge/` (project-scoped, in repo) alongside Claude's own auto-memory (user-scoped) |
| CEO on the phone | Remote Control; cycle reports sent as files; PRs on GitHub; questions in `questions.md` answered in chat |
| Overnight cycles | Scheduled routine that opens a session and runs `/company-cycle` |

## 6. The CEO experience

1. Create a repo, run `python init.py /path/to/repo` (or use the template on GitHub), open it in Claude Code, enable Remote Control.
2. Type the brief. The company runs kickoff and asks for charter approval.
3. Approve. The company plans and asks for plan approval, with a pre-mortem attached.
4. Approve. Cycles run. Each ends with `company/reports/cycle-N.md` delivered to the phone: what shipped, evidence, open questions as yes/no, PRs to merge.
5. Answer questions in chat. Merge PRs on GitHub. The next cycle starts.
6. At any point: `/company-status` for a dashboard, `company/journal/` for the narrative, `company/knowledge/INDEX.md` for what the company has learned.

## 7. Repository layout (this template)

```
virtual-company/
  README.md                 # public-facing: what, why, quick start
  CLAUDE.md                 # the operating model, read by every session in a stamped project
  init.py                   # stamps the template into a target repo (idempotent, merges existing files)
  template/
    .claude/
      agents/               # one file per role, tiered by model
      skills/               # company-kickoff, -plan, -cycle, -review, -retro, -consolidate, -status
      settings.json         # hooks + sane permissions
    company/                # empty scaffold with README files
    tools/company/          # the stdlib-only CLI (company log/ask/backlog/lesson/status/report/gate)
    CLAUDE.company.md       # section appended to the project's CLAUDE.md
  docs/
    DESIGN.md               # this document
    ROLES.md                # role charters in prose, for humans
    EXTENDING.md            # adding a role, a skill, a storage adapter
  examples/
    brief-mdm.md            # the first client: Promethean MDM
```

## 8. What this is not

- Not autonomous without a CEO. Remove the three gates and the company drifts within two cycles.
- Not learning in the ML sense. It is disciplined journaling with retrieval.
- Not a replacement for tests. QA is a role because agents will otherwise declare victory on code that does not run.
- Not cheap to run continuously. Cycles are budgeted and scheduled.

## 9. Lessons from the first live run (2026-10-25)

The framework was exercised on a deliberately tiny project (a 40-line word-count CLI) through kickoff, plan and one full cycle, with roles run on their assigned tiers. What held, what broke, and what changed as a result:

**What held**
- Sonnet executors followed specs literally and stopped to ask instead of guessing, three separate times (two spec criteria wrong as written, one git command git refused). None invented behaviour.
- Opus review caught a real defect that all 14 tests missed: docstrings copied from the spec had lost escape sequences. Round-2 review confirmed the three-line fix.
- The gates and the ledger worked unmodified. Nothing merged without approval; every claim of "done" has an evidence trail.
- The architect reproduced a problem in a scratch repo before deciding, recorded an ADR, and amended the affected spec with a visible correction note rather than a silent rewrite.

**What broke or cost too much**
- Machine facts were rediscovered mid-cycle by several roles: `python` on PATH was a broken stub, `bash` resolved to WSL, pytest crashed without `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, the base branch was `master` not `main`, and `core.autocrlf=true` turned LF fixtures into CRLF on fresh checkout. Each discovery was a round trip.
- Engineering took about one minute per item; reviews, one fix round, one architecture decision and one spec amendment consumed a 30-minute budget. Budgets that count only engineering are wrong.
- Specs ran 142 to 262 lines for 40 lines of product. Three acceptance commands in them were wrong as written and were found by the executors who ran them.
- The CLI could not add acceptance criteria to an existing item, could not record a question answered by anyone but the CEO, and the report did not say where the product was. The CEO's first question after the cycle was "where is the output?"

**What changed**
- `company/environment.md`, probed by the Chief of Staff at kickoff and referenced by every spec and executor prompt (section 4, kickoff step 2).
- Questions carry an audience (`ask --for architect|product|qa|ceo`); the status and report count only CEO questions; `answer --by <role>` closes the rest.
- The report has a "Where the product is" section: repository, base branch, each verified item's branch and commit. Items record `--commit`.
- The architect must execute every acceptance command before handoff and keep small-item specs under about 120 lines; verbatim blocks are marked and reviewers diff them character for character.
- Budgets cover the whole loop; the Head of Product sizes them accordingly.
- `init.py` ships a `.gitattributes` forcing LF checkouts and keeps bytecode and test caches out of git.
- The Test Engineer verifies on a detached integration worktree with item branches merged locally, never on the base branch; check-only worktrees use `--detach`.
- **The project carries its own toolchain** (CEO decision after the run). Kickoff creates `.venv` with `uv`, which downloads its own Python; dependencies are pinned in the project manifest; `pyrun` prefers the project venv over anything on PATH; execution roles are forbidden from using or installing into a system or Anaconda interpreter, and a suite that only passes with machine-installed packages is a reject. `uv` and `git` are the only machine-level tools assumed.

## 10. Open design questions (CEO)

1. Should Review-tier roles run on Opus or on Fable? Opus is the default here for cost; Fable for security review if the project handles PII.
2. Default parallelism: three engineers per cycle unless the charter says otherwise.
3. Should the template ship a GitHub Actions workflow that runs tests on every `vc/*` branch, so gate 3 shows green checks on the phone? Proposed: yes, optional.
4. Repo name and licence for the public release. Proposed: `virtual-company`, MIT, "by Promethean Labs".
