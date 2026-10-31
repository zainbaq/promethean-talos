#!/usr/bin/env python3
"""survey.py: what is in this folder, and do its tests pass. No model, standard library only.

The inventory bounds everything after it: the company reads this map, not the whole folder. The baseline records which tests
passed before the company arrived, so failures that were already there are never blamed on it. The baseline runs in a temporary
detached worktree, so the developer's checkout is not touched, even when it is dirty.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

STAMPED = (".claude/", "tools/talos/", "company/", ".talos/", ".venv/", "CLAUDE.md", ".gitattributes", ".gitignore")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".pytest_cache", ".mypy_cache", "target", ".idea", ".vscode"}
LANGUAGES = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".c": "C", ".h": "C",
    ".cpp": "C++", ".swift": "Swift", ".sh": "Shell", ".ps1": "PowerShell", ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".scss": "CSS",
    ".vue": "Vue", ".svelte": "Svelte", ".ipynb": "Notebook",
}
MATERIAL = {
    "documents": {".md", ".txt", ".doc", ".docx", ".pdf", ".rtf", ".odt"}, "spreadsheets": {".xls", ".xlsx", ".csv", ".tsv", ".ods"},
    "decks": {".ppt", ".pptx", ".key", ".odp"}, "images": {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".psd", ".ai", ".fig"},
    "media": {".mp4", ".mov", ".mp3", ".wav"},
}
MANIFESTS = {"package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "poetry.lock", "uv.lock", "go.mod", "Cargo.toml",
             "pom.xml", "build.gradle", "Gemfile", "composer.json", "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "Makefile"}
CI = (".github/workflows/", ".gitlab-ci.yml", ".circleci/", "azure-pipelines.yml", "Jenkinsfile")
ENTRY_NAMES = {"main.py", "app.py", "manage.py", "wsgi.py", "asgi.py", "server.py", "cli.py", "__main__.py", "index.js", "index.ts", "main.ts", "main.go", "main.rs"}
DOCS = re.compile(r"(^|/)(README[^/]*|CLAUDE\.md|AGENTS\.md|CONTRIBUTING[^/]*|CHANGELOG[^/]*)$|^docs?/", re.I)
TEST_FILE = re.compile(r"(^|/)(tests?/|test_[^/]*\.py$|[^/]*_test\.(py|go)$|[^/]*\.(test|spec)\.[jt]sx?$)")
TODO = re.compile(r"\b(TODO|FIXME)\b")
MAX_READ = 1_000_000
SIZES = ((5_000, 100, "small"), (50_000, 1_000, "medium"))
# What reading a folder costs, by size: the estimate shown first, and the hard cap on the understanding phase.
COST = {"small": {"low": 2, "high": 5, "cap": 6}, "medium": {"low": 6, "high": 12, "cap": 15}, "large": {"low": 12, "high": 25, "cap": 30}}
BASELINE_TIMEOUT = 600


def _git(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def _git_out(root: Path, *args: str) -> str:
    p = _git(root, *args)
    return p.stdout if p is not None and p.returncode == 0 else ""


def is_repo(root: Path) -> bool:
    return _git_out(root, "rev-parse", "--show-toplevel").strip() != ""


def has_commits(root: Path) -> bool:
    return _git_out(root, "rev-parse", "HEAD").strip() != ""


def _stamped(rel: str) -> bool:
    return any(rel == s or rel.startswith(s) for s in STAMPED)


def list_files(root: Path) -> list[str]:
    """The project's own files, relative with forward slashes: not the framework's, not build output."""
    if is_repo(root):
        raw = _git_out(root, "ls-files", "--cached", "--others", "--exclude-standard")
        rels = [l for l in raw.splitlines() if l]
    else:
        rels = []
        for base, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rels += [(Path(base) / n).relative_to(root).as_posix() for n in names]
    return [r for r in rels if not _stamped(r) and not (set(r.split("/")[:-1]) & SKIP_DIRS)]


def kind_of(root: Path, files: list[str] | None = None) -> str:
    """empty, files (not a git repo) or repo: what the company does first depends on this."""
    if is_repo(root):
        return "repo"
    return "files" if (list_files(root) if files is None else files) else "empty"


def size_class(lines: int, files: int) -> str:
    for max_lines, max_files, name in SIZES:
        if lines < max_lines and files < max_files:
            return name
    return "large"


def _python(root: Path) -> str:
    for p in (root / ".venv" / "Scripts" / "python.exe", root / ".venv" / "bin" / "python"):
        if p.exists():
            return str(p)
    return sys.executable


def test_commands(files: list[str], root: Path) -> list[dict]:
    """Candidate commands to run the suite, most likely first. `runner` says how the baseline reads the result."""
    found = []
    names = {f.rsplit("/", 1)[-1] for f in files}
    if any(TEST_FILE.search(f) and f.endswith(".py") for f in files):
        found.append({"runner": "pytest", "command": "python -m pytest"})
    if "package.json" in names and (root / "package.json").exists():
        try:
            if "test" in (json.loads((root / "package.json").read_text(encoding="utf-8")).get("scripts") or {}):
                found.append({"runner": "npm", "command": "npm test"})
        except ValueError:
            pass
    if "go.mod" in names:
        found.append({"runner": "exit", "command": "go test ./..."})
    if "Cargo.toml" in names:
        found.append({"runner": "exit", "command": "cargo test"})
    return found


def inventory(root: Path) -> dict:
    root = Path(root).resolve()
    files = list_files(root)
    lines_by_lang, code_files, todos, material = Counter(), 0, 0, Counter()
    for rel in files:
        ext = Path(rel).suffix.lower()
        for kind, exts in MATERIAL.items():
            if ext in exts:
                material[kind] += 1
        lang = LANGUAGES.get(ext)
        if not lang:
            continue
        code_files += 1
        try:
            path = root / rel
            if path.stat().st_size > MAX_READ:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines_by_lang[lang] += text.count("\n") + 1
        todos += len(TODO.findall(text))
    total = sum(lines_by_lang.values())
    out = {
        "kind": kind_of(root, files), "files": len(files), "code_files": code_files, "lines": total, "languages": dict(lines_by_lang.most_common()),
        "size": size_class(total, len(files)),
        "tree": sorted(Counter(r.split("/")[0] if "/" in r else "." for r in files).items(), key=lambda kv: -kv[1])[:40],
        "manifests": sorted(f for f in files if f.rsplit("/", 1)[-1] in MANIFESTS)[:40],
        "ci": sorted(f for f in files if any(f == c or f.startswith(c) for c in CI))[:20],
        "entry_points": sorted(f for f in files if f.rsplit("/", 1)[-1] in ENTRY_NAMES)[:30],
        "test_files": sum(1 for f in files if TEST_FILE.search(f)), "test_commands": test_commands(files, root),
        "todo_fixme": todos, "docs": sorted(f for f in files if DOCS.search(f))[:40], "material": dict(material),
    }
    out["git"] = _git_facts(root) if out["kind"] == "repo" else None
    out["cost"] = COST[out["size"]]
    return out


def _git_facts(root: Path) -> dict:
    """Authors as a count only: names are not needed to understand the code."""
    if not has_commits(root):
        return {"commits": 0}
    hot = Counter(l for l in _git_out(root, "log", "-500", "--name-only", "--pretty=format:").splitlines() if l and not _stamped(l))
    return {
        "commits": int(_git_out(root, "rev-list", "--count", "HEAD").strip() or 0),
        "commits_last_90_days": int(_git_out(root, "rev-list", "--count", "--since=90.days", "HEAD").strip() or 0),
        "first": _git_out(root, "log", "--reverse", "--format=%as", "--max-count=100000").split("\n", 1)[0],
        "last": _git_out(root, "log", "-1", "--format=%as").strip(),
        "authors": len(_git_out(root, "shortlog", "-sn", "HEAD").splitlines()),
        "branch": _git_out(root, "rev-parse", "--abbrev-ref", "HEAD").strip(),
        "branches": len(_git_out(root, "branch", "--list").splitlines()),
        "dirty_files": len(_git_out(root, "status", "--porcelain").splitlines()),
        "hot_files": hot.most_common(15),
    }


# ------------------------------------------------------------------ baseline

PYTEST_LINE = re.compile(r"^(FAILED|ERROR) (\S+)", re.M)
PYTEST_COUNT = re.compile(r"(\d+) (passed|failed|error|errors|skipped)\b")


def parse_pytest(text: str) -> dict:
    counts = Counter()
    tail = text.strip().splitlines()[-1] if text.strip() else ""
    for n, word in PYTEST_COUNT.findall(tail):
        counts["errors" if word.startswith("error") else word] += int(n)
    return {"passed": counts["passed"], "failed": counts["failed"], "errors": counts["errors"], "skipped": counts["skipped"],
            "failures": sorted(set(m[1] for m in PYTEST_LINE.findall(text)))}


def install_python_deps(root: Path, where: Path) -> str:
    """Into the project's own .venv. A project whose dependencies will not install gets a baseline that says so."""
    uv = shutil.which("uv")
    if not (root / ".talos" / "venv-ours").exists():
        return "the project's own .venv, used as it is"
    if not uv:
        return "no uv: dependencies not installed"
    args = None
    if (where / "requirements.txt").exists():
        args = ["-r", "requirements.txt"]
    elif (where / "pyproject.toml").exists() or (where / "setup.py").exists():
        args = ["-e", "."]
    if not args:
        return "no Python manifest"
    p = subprocess.run([uv, "pip", "install", "--python", _python(root), *args], cwd=where, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=BASELINE_TIMEOUT)
    return "dependencies installed" if p.returncode == 0 else "dependencies did not install: " + (p.stderr.strip().splitlines() or ["?"])[-1][:200]


def run_tests(root: Path, where: Path, candidate: dict, timeout: int = BASELINE_TIMEOUT) -> dict:
    runner = candidate["runner"]
    if runner == "pytest":
        cmd = [_python(root), "-m", "pytest", "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider"]
    else:
        cmd = candidate["command"].split()
        resolved = shutil.which(cmd[0])
        if not resolved:
            return {"ran": False, "why": f"{cmd[0]} is not installed on this machine"}
        cmd[0] = resolved
    env = dict(os.environ, CI="1", PYTHONUTF8="1")
    try:
        p = subprocess.run(cmd, cwd=where, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return {"ran": False, "why": f"the suite did not finish in {timeout} s"}
    except OSError as e:
        return {"ran": False, "why": str(e)}
    out = {"ran": True, "exit": p.returncode, "command": candidate["command"]}
    if runner == "pytest":
        out.update(parse_pytest(p.stdout))
    return out


def baseline(root: Path, inv: dict) -> dict:
    """Run the suite once in a temporary detached worktree of HEAD. Nothing in the checkout changes."""
    root = Path(root).resolve()
    commands = inv.get("test_commands") or []
    if not commands:
        return {"ran": False, "why": "no test suite found"}
    if not has_commits(root):
        return {"ran": False, "why": "no commits yet"}
    wt = root / ".claude" / "worktrees" / "talos-baseline"
    if wt.exists():
        _git(root, "worktree", "remove", "--force", str(wt))
    added = _git(root, "worktree", "add", "--detach", "-q", str(wt), "HEAD", timeout=300)
    if added is None or added.returncode != 0:
        return {"ran": False, "why": "could not make a temporary worktree: " + ((added.stderr.strip() if added else "") or "git failed")[:200]}
    try:
        deps = install_python_deps(root, wt) if commands[0]["runner"] == "pytest" else "not needed"
        result = run_tests(root, wt, commands[0])
        result["dependencies"] = deps
        result["commit"] = _git_out(root, "rev-parse", "--short", "HEAD").strip()
        return result
    finally:
        _git(root, "worktree", "remove", "--force", str(wt))


def new_failures(known: dict, now: dict) -> list[str]:
    return sorted(set(now.get("failures") or []) - set(known.get("failures") or []))


def report(b: dict) -> str:
    """company/baseline.md."""
    if not b.get("ran"):
        return f"# Test baseline\n\nNo baseline: {b.get('why')}.\n\nUntil there is one, say in every hand-back that nothing could check for regressions.\n"
    lines = ["# Test baseline", "", f"Recorded before the company changed anything, at commit `{b.get('commit')}`, with `{b.get('command')}`. Dependencies: {b.get('dependencies')}.", ""]
    if "passed" in b:
        lines += [f"**{b['passed']} passed, {b['failed']} failed, {b['errors']} errors, {b['skipped']} skipped.**", ""]
    else:
        lines += [f"The suite exited {b.get('exit')}. This runner gives no per-test result, so only the exit code can be compared.", ""]
    lines += ["**The rule: never regress this.** The failures below were here before the company arrived. They are known failures, not the company's to blame and not to be fixed unasked. Any other failure is a regression. `tools/talos/talos baseline --check` compares.", ""]
    lines += ["## Known failures", ""] + ([f"- `{f}`" for f in b.get("failures") or []] or ["_none_"])
    return "\n".join(lines) + "\n"


def first_reply(inv: dict) -> str:
    """What the company says first in this folder, from the survey alone."""
    kinds = ", ".join(f"{n} {k}" for k, n in sorted(inv["material"].items(), key=lambda kv: -kv[1])) or "no documents"
    if inv["code_files"]:
        langs = ", ".join(list(inv["languages"])[:3])
        seen = f"{inv['files']} files, about {inv['lines']:,} lines of {langs} ({inv['size']}), {inv['test_files']} test files"
    else:
        seen = f"{inv['files']} files: {kinds}"
    return seen
