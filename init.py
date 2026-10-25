#!/usr/bin/env python3
"""
init.py — stamp the Virtual Company framework into a target project.

    python init.py /path/to/project [--brief brief.md] [--force]

What it does (idempotent; safe to re-run to pick up framework updates):
  1. Copies template/.claude/agents/*  and template/.claude/skills/*  into the project
     (existing files are overwritten only with --force; otherwise kept and reported).
  2. Merges template/.claude/settings.json into the project's .claude/settings.json
     (hooks are appended if not already present; permissions are unioned).
  3. Copies template/tools/company/ (the record CLI) into the project.
  4. Appends template/CLAUDE.company.md to the project's CLAUDE.md between markers
     (replaces the marked section on re-run).
  5. Runs `company init` to create the company/ record scaffold, seeding company/brief.md
     if --brief is given.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template"
MARK_START = "<!-- virtual-company:start -->"
MARK_END = "<!-- virtual-company:end -->"


def copy_tree(src: Path, dst: Path, force: bool) -> tuple[list[str], list[str]]:
    written, kept = [], []
    for p in src.rglob("*"):
        if p.is_dir() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not force:
            kept.append(str(rel))
            continue
        shutil.copy2(p, target)
        written.append(str(rel))
    return written, kept


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
    dst.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")
    return "merged" if dst.exists() else "created"


def splice_claude_md(section_src: Path, claude_md: Path) -> str:
    section = section_src.read_text(encoding="utf-8").strip("\n")
    block = f"{MARK_START}\n{section}\n{MARK_END}\n"
    if claude_md.exists():
        text = claude_md.read_text(encoding="utf-8")
        if MARK_START in text and MARK_END in text:
            pre = text.split(MARK_START)[0]
            post = text.split(MARK_END, 1)[1]
            claude_md.write_text(pre + block + post, encoding="utf-8")
            return "replaced section"
        claude_md.write_text(text.rstrip("\n") + "\n\n" + block, encoding="utf-8")
        return "appended section"
    claude_md.write_text(f"# Project\n\n{block}", encoding="utf-8")
    return "created"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="path to the project to stamp")
    ap.add_argument("--brief", help="path to a brief.md to seed company/brief.md")
    ap.add_argument("--force", action="store_true", help="overwrite existing agent/skill/tool files")
    ap.add_argument("--python", default="3.12", help="Python version for the project venv created with uv (default 3.12)")
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
    print(f"Stamping Virtual Company into {target}\n")

    for sub in ("agents", "skills", "rules"):
        w, k = copy_tree(TEMPLATE / ".claude" / sub, target / ".claude" / sub, args.force)
        print(f".claude/{sub}: {len(w)} written, {len(k)} kept" + (f" (re-run with --force to overwrite: {', '.join(k[:5])}{'…' if len(k) > 5 else ''})" if k else ""))

    print(f".claude/settings.json: {merge_settings(TEMPLATE / '.claude' / 'settings.json', target / '.claude' / 'settings.json')}")

    w, k = copy_tree(TEMPLATE / "tools", target / "tools", True)
    for name in ("company", "pyrun"):
        try:
            p = target / "tools" / "company" / name
            p.chmod(p.stat().st_mode | 0o111)
        except Exception:
            pass
    print(f"tools/company: {len(w)} written (always refreshed)")

    print(f"CLAUDE.md: {splice_claude_md(TEMPLATE / 'CLAUDE.company.md', target / 'CLAUDE.md')}")

    # Repo hygiene learned from the first live run: force LF checkouts so byte-exact
    # fixtures survive Windows autocrlf, and keep bytecode and test caches out of git.
    ga = target / ".gitattributes"
    if not ga.exists():
        shutil.copy2(TEMPLATE / ".gitattributes", ga)
        print(".gitattributes: created (LF checkouts everywhere)")
    else:
        print(".gitattributes: kept (yours)")
    gi = target / ".gitignore"
    wanted = ["__pycache__/", "*.pyc", ".pytest_cache/", ".venv/"]
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    missing = [w for w in wanted if w not in existing]
    if missing:
        with gi.open("a", encoding="utf-8") as f:
            if existing and existing[-1].strip():
                f.write("\n")
            f.write("# virtual-company\n" + "\n".join(missing) + "\n")
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
            except subprocess.CalledProcessError as e:
                print(f".venv: NOT created (uv exited {e.returncode}). Fix uv's Python install "
                      f"(`uv python install {args.python} --reinstall`) and re-run init.py, or let the kickoff procedure create the venv.")
                shutil.rmtree(venv, ignore_errors=True)
        else:
            print(".venv: NOT created. uv was not found on PATH; install it (winget install astral-sh.uv) and re-run, "
                  "or let the kickoff procedure create the venv. Until then the record CLI falls back to COMPANY_PYTHON.")

    cmd = [sys.executable, str(target / "tools" / "company" / "company.py"), "init"]
    if args.brief:
        cmd += ["--brief", str(Path(args.brief).resolve())]
    subprocess.run(cmd, cwd=target, check=True)

    print("\nDone. Next: open the project in Claude Code and run /company-kickoff (or just describe what you want to build).")


if __name__ == "__main__":
    main()
