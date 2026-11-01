#!/usr/bin/env python3
"""
init.py — stamp the Talos framework into a target project.

    uv run init.py /path/to/project [--brief brief.md] [--teams core,design] [--force] [--prune] [--headless] [--no-commit]
    uv run init.py /path/to/project --upgrade          pick up a newer Talos; files you changed are kept and listed
    uv run init.py /path/to/project --add-team gtm     staff one more team

The folder can be empty, not a repo, or an existing repo. In a repo that already has commits nothing of the developer's is rewritten:
ignores go in .git/info/exclude, no .gitattributes is added, and the framework's own files get one local commit (--no-commit skips it)
that leaves any other changes alone. Then `tools/talos/talos start` says what happens first.

What it does (idempotent; --upgrade picks up framework updates):
  1. Copies the agents of the staffed teams (template/tools/talos/teams.json; default: all) and
     template/.claude/skills/* into the project. Existing files are overwritten only with
     --force. Re-running with more teams adds their agents; --prune removes stamped agents
     of teams no longer listed.
  2. Merges template/.claude/settings.json into the project's .claude/settings.json
     (hooks are appended if not already present; permissions are unioned).
  3. Copies template/tools/talos/ (the record CLI) into the project. The control room
     (tools/talos/viz) comes with it; --headless leaves it out of a new project.
  4. Appends template/CLAUDE.talos.md to the project's CLAUDE.md between markers
     (replaces the marked section on re-run).
  5. Runs `talos init` to create the company/ record scaffold, seeding company/brief.md
     if --brief is given.

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"
MARK_START = "<!-- talos:start -->"
MARK_END = "<!-- talos:end -->"
# Projects stamped before the rename carry these markers; re-stamping replaces them in place.
LEGACY_MARKS = [("<!-- virtual-company:start -->", "<!-- virtual-company:end -->")]
MANIFEST = "tools/talos/stamped.json"


def write_lf(path, text, encoding="utf-8"):
    """Write text with LF line endings on every platform (Windows would otherwise emit CRLF)."""
    with open(path, "w", encoding=encoding, newline="\n") as f:
        f.write(text)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamped_files() -> dict[str, Path]:
    """Every file that may be edited in a project, by its path there, to the template file it came from."""
    base = TEMPLATE / ".claude"
    return {f".claude/{p.relative_to(base).as_posix()}": p for sub in ("agents", "skills", "rules") for p in (base / sub).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts}


def theirs(target: Path) -> set[str]:
    """What the project changed since it was stamped, by comparing with the hashes recorded then. A project from before the record: whatever differs from the template."""
    path = target / MANIFEST
    was = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    out = set()
    for rel, src in stamped_files().items():
        have = target / rel
        if have.is_file() and sha(have) != was.get(rel, sha(src)):
            out.add(rel)
    return out


def write_manifest(target: Path, kept: set[str]) -> None:
    path = target / MANIFEST
    was = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    out = {}
    for rel, src in stamped_files().items():
        if (target / rel).is_file():
            out[rel] = was.get(rel, sha(src)) if rel in kept else sha(target / rel)
    write_lf(path, json.dumps(out, indent=1, sort_keys=True) + "\n")


def changes_since(old: str) -> str:
    """The parts of the changelog newer than the version a project had."""
    def key(v):
        return tuple(int(n) for n in re.findall(r"\d+", v))
    parts = re.split(r"^## ", (TEMPLATE / "tools" / "talos" / "CHANGES.md").read_text(encoding="utf-8"), flags=re.M)[1:]
    return "\n".join("## " + p.strip() for p in parts if key(p.split()[0]) > key(old))


def copy_tree(src: Path, dst: Path, force: bool, skip: tuple[str, ...] = ()) -> tuple[list[str], list[str]]:
    written, kept = [], []
    for p in src.rglob("*"):
        if p.is_dir() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(src)
        if any(rel.as_posix() == s or rel.as_posix().startswith(s + "/") for s in skip):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            kept.append(str(rel))
            continue
        shutil.copy2(p, target)
        written.append(str(rel))
    return written, kept


def git_out(target: Path, *args: str) -> str:
    try:
        p = subprocess.run(["git", *args], cwd=target, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return p.stdout if p.returncode == 0 else ""


def commit_stamp_on(target: Path, branch: str, paths: list[str]) -> str:
    """The same commit, on a branch nobody has checked out: the developer's branch, index and files stay exactly as they were."""
    common = Path(git_out(target, "rev-parse", "--git-common-dir").strip())
    index = (common if common.is_absolute() else target / common) / "talos-stamp-index"
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    run = lambda *a: subprocess.run(["git", *a], cwd=target, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")  # noqa: E731
    who = [] if git_out(target, "config", "user.email").strip() else ["-c", "user.email=talos@localhost", "-c", "user.name=talos"]
    try:
        run("read-tree", branch)
        run("add", "-f", "--", *paths, ":(exclude).claude/worktrees", ":(exclude).claude/settings.local.json")
        tree = run("write-tree").stdout.strip()
        commit = run(*who, "commit-tree", tree, "-p", branch, "-m", "Add Talos (framework files only)").stdout.strip()
        work = target / ".talos" / "work"
        if (work / ".git").exists() and git_out(work, "status", "--porcelain").strip():
            return f"not committed on {branch}: its worktree at .talos/work has changes"
        if not commit or run("update-ref", f"refs/heads/{branch}", commit).returncode != 0:
            return f"not committed on {branch}; worktrees will not have tools/talos"
        if (work / ".git").exists():  # the branch moved under its worktree
            subprocess.run(["git", "reset", "-q", "--hard"], cwd=work, capture_output=True)
    finally:
        index.unlink(missing_ok=True)
    return f"committed the framework's files on {branch}, not on your branch, not pushed"


def commit_stamp(target: Path, dirty: set[str], branch: str | None = None) -> str:
    """One local commit of the framework's files, so worktrees have them. Nothing else in the checkout goes with it."""
    paths = [p for p in (".claude", "tools/talos", "company", "CLAUDE.md") if (target / p).exists() and not any(d == p or d.startswith(p + "/") for d in dirty)]
    ignored = set(git_out(target, "check-ignore", *paths).split())  # this repo's ignores are its own: leave those paths out
    paths = [p for p in paths if p not in ignored]
    if not paths:
        return "nothing to commit: this repo ignores the framework's files, so worktrees will not have tools/talos"
    if branch:
        return commit_stamp_on(target, branch, paths)
    subprocess.run(["git", "add", "--", *paths], cwd=target, capture_output=True)
    who = [] if git_out(target, "config", "user.email").strip() else ["-c", "user.email=talos@localhost", "-c", "user.name=talos"]
    p = subprocess.run(["git", *who, "commit", "-qm", "Add Talos (framework files only)", "--", *paths], cwd=target, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        return f"not committed ({(p.stderr or p.stdout).strip()[:160]}); worktrees will not have tools/talos until you commit it"
    skipped = f"; left out because you had changes there: {', '.join(sorted(dirty))}" if dirty else ""
    skipped += f"; left out because this repo ignores them: {', '.join(sorted(ignored))}" if ignored else ""
    return f"committed the framework's files locally, not pushed{skipped}"


def load_teams() -> dict:
    t = json.loads((TEMPLATE / "tools" / "talos" / "teams.json").read_text(encoding="utf-8"))
    return {k: v for k, v in t.items() if not k.startswith("_")}


def stamp_agents(target: Path, teams: list[str], force: bool, prune: bool, keep: set[str] = frozenset()) -> str:
    catalog = load_teams()
    unknown = [t for t in teams if t not in catalog]
    if unknown:
        sys.exit(f"init: unknown team(s) {', '.join(unknown)}; known: {', '.join(catalog)}")
    want = {a for t in teams for a in catalog[t]["agents"]}
    dst = target / ".claude" / "agents"
    dst.mkdir(parents=True, exist_ok=True)
    written, kept, removed = [], [], []
    for name in sorted(want):
        src, out = TEMPLATE / ".claude" / "agents" / f"{name}.md", dst / f"{name}.md"
        if out.exists() and (not force or f".claude/agents/{name}.md" in keep):
            kept.append(name)
            continue
        shutil.copy2(src, out)
        written.append(name)
    if prune:
        every = {a for v in catalog.values() for a in v["agents"]}
        for name in sorted(every - want):
            if (dst / f"{name}.md").exists():
                (dst / f"{name}.md").unlink()
                removed.append(name)
    msg = f".claude/agents: teams {','.join(teams)}: {len(written)} written, {len(kept)} kept"
    if kept and not force:
        msg += " (re-run with --force to overwrite)"
    if removed:
        msg += f", {len(removed)} pruned ({', '.join(removed)})"
    return msg


def merge_settings(src: Path, dst: Path) -> str:
    tpl = json.loads(src.read_text(encoding="utf-8"))
    if dst.exists():
        cur = json.loads(dst.read_text(encoding="utf-8"))
    else:
        cur = {}
    # permissions: union of allow/deny lists
    for key in ("allow", "deny", "ask"):
        want = tpl.get("permissions", {}).get(key, [])
        if want:
            have = cur.setdefault("permissions", {}).setdefault(key, [])
            for rule in want:
                if rule not in have:
                    have.append(rule)
    # hooks: append matcher groups not already present (compared by JSON identity)
    for event, groups in tpl.get("hooks", {}).items():
        have = cur.setdefault("hooks", {}).setdefault(event, [])
        have_json = {json.dumps(g, sort_keys=True) for g in have}
        for g in groups:
            if json.dumps(g, sort_keys=True) not in have_json:
                have.append(g)
    # env: add missing keys only
    for k, v in tpl.get("env", {}).items():
        cur.setdefault("env", {}).setdefault(k, v)
    dst.parent.mkdir(parents=True, exist_ok=True)
    write_lf(dst, json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    return "merged" if dst.exists() else "created"


def splice_claude_md(section_src: Path, claude_md: Path) -> str:
    section = section_src.read_text(encoding="utf-8").strip("\n")
    block = f"{MARK_START}\n{section}\n{MARK_END}\n"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8")
        for old_start, old_end in LEGACY_MARKS:
            if old_start in text and old_end in text:
                text = text.replace(old_start, MARK_START).replace(old_end, MARK_END)
        if MARK_START in text and MARK_END in text:
            pre = text.split(MARK_START)[0]
            post = text.split(MARK_END, 1)[1]
            write_lf(claude_md, pre + block + post, encoding="utf-8")
            return "replaced section"
        write_lf(claude_md, text.rstrip("\n") + "\n\n" + block, encoding="utf-8")
        return "appended section"
    write_lf(claude_md, f"# Project\n\n{block}", encoding="utf-8")
    return "created"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="path to the project to stamp")
    ap.add_argument("--brief", help="path to a brief.md to seed company/brief.md")
    ap.add_argument("--force", action="store_true", help="overwrite existing agent/skill/tool files")
    ap.add_argument("--teams", help="comma-separated teams to staff (see template/tools/talos/teams.json); default: every team")
    ap.add_argument("--prune", action="store_true", help="remove stamped agents of teams not in --teams")
    ap.add_argument("--python", default="3.12", help="Python version for the project venv created with uv (default 3.12)")
    ap.add_argument("--no-commit", action="store_true", help="in an existing repo, do not commit the framework's files")
    ap.add_argument("--protect", metavar="BRANCH", help="in an existing repo, the company never changes this branch: its files and work go on talos/work")
    ap.add_argument("--viz", action="store_true", help="add the control room to a project stamped --headless")
    ap.add_argument("--headless", action="store_true", help="leave the control room out of a new project")
    ap.add_argument("--upgrade", action="store_true", help="refresh the framework's files; the teams stay, files you changed are kept and listed, company/ is not touched")
    ap.add_argument("--add-team", metavar="TEAM", help="staff one more team, keeping the ones this project has")
    args = ap.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        sys.exit(f"init: target {target} does not exist")
    if target == HERE or HERE in target.parents:
        sys.exit("init: refusing to stamp the template repo onto itself")

    try:
        sys.stdout.reconfigure(line_buffering=True)  # keep our output ordered before the subprocess's
    except Exception:
        pass
    print(f"Stamping Talos into {target}\n")
    state_file = target / "company" / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    stamped = (target / "tools" / "talos" / "talos.py").is_file()
    if (args.upgrade or args.add_team) and not stamped:
        sys.exit("init: Talos is not in this folder yet; run init.py without --upgrade or --add-team first")
    version_file = target / "tools" / "talos" / "VERSION"
    old_version = version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "0"
    if args.add_team:
        args.teams = ",".join(dict.fromkeys([*(state.get("teams") or ["core"]), args.add_team]))
    elif stamped and not args.teams and state.get("teams"):
        args.teams = ",".join(state["teams"])  # a re-stamp keeps the project's teams
    keep = theirs(target) if args.upgrade or not args.force else set()  # a re-stamp or --add-team must not record your edits as the template's
    force = args.force or args.upgrade
    existing_repo = git_out(target, "rev-parse", "HEAD").strip() != ""
    dirty = {l[3:].strip('"') for l in git_out(target, "status", "--porcelain", "--", ".claude", "tools/talos", "company", "CLAUDE.md").splitlines()} if existing_repo else set()

    teams = [t.strip() for t in (args.teams or ",".join(load_teams())).split(",") if t.strip()]
    if args.teams and "core" not in teams:
        sys.exit("init: the core team is required (add core to --teams)")
    print(stamp_agents(target, teams, force, args.prune, keep))
    for sub in ("skills", "rules"):
        skip = tuple(r[len(f".claude/{sub}/"):] for r in keep if r.startswith(f".claude/{sub}/"))
        w, k = copy_tree(TEMPLATE / ".claude" / sub, target / ".claude" / sub, force, skip)
        print(f".claude/{sub}: {len(w)} written, {len(k)} kept" + (f" (re-run with --force to overwrite: {', '.join(k[:5])}{'…' if len(k) > 5 else ''})" if k else ""))

    print(f".claude/settings.json: {merge_settings(TEMPLATE / '.claude' / 'settings.json', target / '.claude' / 'settings.json')}")

    with_viz = args.viz or (target / "tools" / "talos" / "viz" / "server.py").is_file() or (not stamped and not args.headless)
    w, k = copy_tree(TEMPLATE / "tools", target / "tools", True, skip=() if with_viz else ("talos/viz",))
    for name in ("talos", "run", "pyrun"):
        try:
            p = target / "tools" / "talos" / name
            p.chmod(p.stat().st_mode | 0o111)
        except Exception:
            pass
    print(f"tools/talos: {len(w)} written (always refreshed)")
    print("control room: installed (start it with `tools/talos/talos viz`)" if with_viz
          else "control room: not installed (headless; add it with --viz)")
    write_manifest(target, keep)
    if keep:
        print(f"kept because you changed them, compare with the template yourself: {', '.join(sorted(keep))}")
    if args.upgrade:
        print(changes_since(old_version) or f"already at {(TEMPLATE / 'tools' / 'talos' / 'VERSION').read_text(encoding='utf-8').strip()}")

    print(f"CLAUDE.md: {splice_claude_md(TEMPLATE / 'CLAUDE.talos.md', target / 'CLAUDE.md')}")

    # Repo hygiene learned from the first live run: force LF checkouts so byte-exact
    # fixtures survive Windows autocrlf, and keep bytecode and test caches out of git.
    ga = target / ".gitattributes"
    if existing_repo:
        print(".gitattributes: not added (this repo's line endings are its own)")
    elif not ga.exists():
        shutil.copy2(TEMPLATE / ".gitattributes", ga)
        print(".gitattributes: created (LF checkouts everywhere)")
    else:
        print(".gitattributes: kept (yours)")
    exclude = target / git_out(target, "rev-parse", "--git-path", "info/exclude").strip() if existing_repo else None  # a subfolder or a linked worktree has no .git/info of its own
    gi = exclude or target / ".gitignore"
    gi.parent.mkdir(parents=True, exist_ok=True)
    wanted = ["__pycache__/", "*.pyc", ".pytest_cache/", ".venv/", ".claude/worktrees/", ".claude/settings.local.json", "company/.context/", ".talos/"]
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    missing = [w for w in wanted if w not in existing]
    if missing:
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("# promethean-talos\n" + "\n".join(missing) + "\n")
        print(f".gitignore: added {', '.join(missing)}")

    # Project-local toolchain: create .venv with uv when available, so the record CLI and
    # every role run on the project's own interpreter from the first command.
    venv = target / ".venv"
    if venv.exists():
        print(".venv: kept (yours)")
    else:
        uv = shutil.which("uv") or os.environ.get("UV")
        if uv:
            try:
                subprocess.run([uv, "venv", "--python", args.python, str(venv)], cwd=target, check=True)
                subprocess.run([uv, "pip", "install", "--python", str(venv), "pytest"], cwd=target, check=True)
                print(f".venv: created with uv (Python {args.python}) and pytest installed")
                (target / ".talos").mkdir(exist_ok=True)
                (target / ".talos" / "venv-ours").touch()
            except subprocess.CalledProcessError as e:
                print(f".venv: NOT created (uv exited {e.returncode}). Fix uv's Python install "
                      f"(`uv python install {args.python} --reinstall`) and re-run init.py, or let the kickoff procedure create the venv.")
                shutil.rmtree(venv, ignore_errors=True)
        else:
            print(".venv: NOT created. uv was not found on PATH; install it (winget install astral-sh.uv) and re-run, "
                  "or let the kickoff procedure create the venv. Until then the record CLI falls back to TALOS_PYTHON.")

    cmd = [sys.executable, str(target / "tools" / "talos" / "talos.py"), "init", "--teams", ",".join(teams)]
    if args.brief:
        cmd += ["--brief", str(Path(args.brief).resolve())]
    subprocess.run(cmd, cwd=target, check=True)

    if args.protect:
        if not existing_repo:
            sys.exit("init: --protect needs an existing repo with at least one commit")
        subprocess.run([sys.executable, str(target / "tools" / "talos" / "talos.py"), "protect", args.protect, "--actor", "ceo", "--tier", "ceo"], cwd=target, check=True)
    if existing_repo and not args.no_commit:
        print(f"git: {commit_stamp(target, dirty, 'talos/work' if args.protect or state.get('protected') else None)}")
    if args.protect:  # the files are there for the company; on the protected branch they should not show as changes
        with open(exclude, "a", encoding="utf-8", newline="\n") as f:
            f.write("# promethean-talos: committed on talos/work only\n.claude/\ntools/talos/\ncompany/\n")
            if not git_out(target, "ls-files", "CLAUDE.md").strip():
                f.write("CLAUDE.md\n")
    print("\nDone. Next: from the project root run `tools/talos/talos start`.")


if __name__ == "__main__":
    main()
