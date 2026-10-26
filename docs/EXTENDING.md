# Extending the framework

## Add a role

1. Copy the closest agent in `template/.claude/agents/` (an executive if it decides, an executor if it does).
2. Set the frontmatter: `name` (unique, no colons), `description` (when to use it; say "use proactively" if the Chief of Staff should reach for it unprompted), `model` (`fable`, `opus`, `sonnet`, `haiku`), `tools` (comma-separated; omit `Agent` so it cannot spawn sub-agents unless it should), and `isolation: worktree` for anything that edits product code in parallel.
3. Write "You own" and "You are forbidden from" before anything else. The forbidden list is what makes the role safe.
4. Execution roles get a hand-back block; executive roles get the CLI calls they are allowed to make with their `TALOS_ACTOR`.
5. Add the role to the tier table in `template/CLAUDE.talos.md` and to `docs/ROLES.md`.
6. Re-run `python init.py <project>` in stamped projects to pick it up.

Examples worth adding per project: `data-engineer`, `compliance-officer`, `growth-lead`, `support-engineer`, `prompt-engineer`.

## Add a procedure (skill)

Skills live in `template/.claude/skills/<name>/SKILL.md`. Keep the frontmatter to `name`, `description`, `argument-hint` and `allowed-tools` for portability. Write the procedure as numbered steps that say which role to spawn with what inputs and which CLI call records the outcome. End with a "Do not" list. A skill should be runnable by a session that has read nothing else, because Remote Control sessions and scheduled runs start cold.

## Add a gate or guard

- **Hard guards** go in `template/tools/talos/hooks/guard.py` (PreToolUse). Add a regex and a reason to `BASH_DENY`, or a path to `PROTECTED`. Exit 2 blocks and shows the reason.
- **Procedural gates** go in the CLI: add a check to `cmd_gate` and call it from the relevant skill.
- **Reminders** go in `stop_reminder.py` and return a `systemMessage`; they never block.

## Change model tiers

Edit `model:` in the agent files. The design assumes executives are at least one tier above executors. Running everything on one model works but removes the cost advantage and, more importantly, the discipline that specs must be precise enough for a weaker model.

## Headless and scheduled cycles

A cycle can run without a human present:

```bash
claude -p "/talos-cycle 4h" --permission-mode acceptEdits --max-turns 200 --output-format json
```

Do **not** add `--bare`; it disables hooks, skills, agents and CLAUDE.md. For Claude Code scheduled tasks (cloud), commit `.claude/` and `tools/` to the repo since cloud runs only read committed files, and point the task's prompt at `/talos-cycle`. Gate 3 still applies: the run ends with a report and nothing merges until the CEO approves through `/talos-review`.

## Running roles from a session that is not inside the project

The project's `.claude/agents/` are only registered when Claude Code is opened in that project. If you are orchestrating from a parent directory, or the headless CLI cannot authenticate, you can still run the company faithfully: act as Chief of Staff yourself and spawn each role with the Agent tool, setting `model` to the role's tier and giving it a prompt of the form "Your role definition is `<project>/.claude/agents/<role>.md`; read it and adopt it completely", followed by the assignment, the project root, the CLI invocation with `TALOS_ACTOR`, and the relevant lines of `company/environment.md`. This is how the first live run was conducted. Worktree roles create their own worktree with `git worktree add` since the Agent tool's worktree isolation applies to the session's repository, not the project's.

## Storage adapter

The CLI is the abstraction; `ledger.jsonl` plus markdown files are the default storage. To add SQLite:

1. Add `talos db sync` that reads `ledger.jsonl` and the frontmatter of items, specs, ADRs and lessons into tables.
2. Keep the JSONL as the write path so git history stays the audit trail; the database is a read model.
3. Add `talos query "<sql>"` for ad-hoc questions ("which items were rejected twice").

Do not make the database the write path unless you also solve concurrent writes from parallel worktrees, which the files-plus-orchestrator design avoids.

## Project-specific knowledge seeds

A new project can start with lessons. Put them in `company/knowledge/` with the standard frontmatter and cite the external source in `evidence` (a document path, a URL, a prior project). Run `talos consolidate` to index them. The Promethean MDM example seeds its knowledge from `promethean-mdm/docs/customer-mdm-knowledge-base.md`.

## Conventions worth keeping

- Branch names `vc/<item-id>`.
- One item, one spec, one engineer, one branch.
- UTC timestamps everywhere.
- Reports lead with decisions.
- The CEO's words, never a paraphrase, in every `--quote`.
