---
status: probed
probed: 2026-10-28
---

# Environment

Probed by the Chief of Staff at kickoff (2026-10-28). Every spec and executor prompt points here instead of
restating machine facts. Update it the same day a role discovers a quirk.

## Repository
- Path: `C:\Users\ceo\AppData\Local\Temp\claude\D--Projects-Promethean\0d1279cd-a8fd-45ee-a27d-13220792d67f\scratchpad\talos-ui`
  (Git Bash form: `/c/Users/ceo/AppData/Local/Temp/claude/D--Projects-Promethean/0d1279cd-a8fd-45ee-a27d-13220792d67f/scratchpad/talos-ui`)
- Base branch: `main`. Work happens on `vc/<item-id>` branches in worktrees under `.claude/worktrees/` (git-ignored).
- Line endings: `.gitattributes` present (`* text=auto eol=lf`, images and archives binary). `core.autocrlf=true` on this
  machine; the attributes file wins, so files are LF in the repo. Do not change either.
- Product code (decided at plan, ADR-0001): plain HTML/CSS/ES-module JS under `app/`, Playwright tests under `tests/`.
  **Base branch for item work is `vc/scaffold`** (off `main` de819b4; holds `app/storage.js`, `app/tokens.css`,
  `tests/conftest.py`). Item branches: `vc/item-0001`, `vc/item-0002`. `main` stays untouched until the release gate.
  Scaffold worktree: `.claude/worktrees/scaffold`.

## Toolchain (project-local, never the machine's)
- Python venv: `.venv/` at the repo root (created by init.py with `uv`). Interpreter: `.venv/Scripts/python.exe`,
  **Python 3.12.15**. `uv 0.13.5` is the only machine-level tool used.
- Dependency manifest: `requirements-dev.txt` (pytest 9.2.0, playwright 1.64.1, nodeenv 1.11.0).
  Reinstall with `uv pip install --python .venv -r requirements-dev.txt`.
- Node: **v24.22.1 LTS** inside the venv via nodeenv (`.venv/Scripts/node.exe`, `.venv/Scripts/npm`, npm 11.19.1).
  Use it by putting `.venv/Scripts` first on PATH: `PATH="$PWD/.venv/Scripts:$PATH"`. There is no Node on the machine.
- Playwright: Python package in the venv; browser **Chromium headless shell 156.0.8078.4** under `.venv/ms-playwright/`.
  Every Playwright call needs `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright` or it will look in the user profile and fail.
- axe-core **4.14** in `node_modules/axe-core/axe.min.js` (project `package.json`; `node_modules/` git-ignored).
  Reinstall with `PATH="$PWD/.venv/Scripts:$PATH" npm install --prefix . axe-core@4`.
- Screenshots and accessibility checks: `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python tools/talos/screens.py NAME=URL ...`
  writes phone (390x844) and desktop (1280x800), light and dark PNGs plus `a11y.json` to `company/design/screens/`.
- Machine interpreters found and deliberately NOT used: Anaconda at `C:\Users\ceo\anaconda3` (condabin on PATH);
  Windows Store `python`/`python3` stubs in `AppData\Local\Microsoft\WindowsApps` (they fail with "Permission denied"
  from Git Bash). `py` launcher absent. No machine Node, npm or conda on PATH.

## Test runner
- Python suite: `.venv/Scripts/python -m pytest -q` from the repo root. Verified on a trivial test: 1 passed in 0.02s.
- Browser checks: `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python <script>`. Verified: Chromium
  rendered a page at phone width in dark mode, axe-core ran (4 violations, 8 passes on a bare probe page), screenshot written.
- **Product test command (chosen at plan):** `<main>/.venv/Scripts/python -m pytest -q -p no:cacheprovider tests`
  from the checkout root. Works unchanged inside a worktree: `tests/conftest.py` sets `PLAYWRIGHT_BROWSERS_PATH`,
  finds `node_modules/axe-core` via `sys.executable`, and serves the checkout on an ephemeral 127.0.0.1 port per
  session, so parallel worktrees never collide. Full suite takes about 75 s (one real-time 1-minute focus test).
- No JavaScript test runner; all browser tests are Python/Playwright.
- `tools/talos/screens.py` must run with cwd = main checkout (it finds axe at `./node_modules`); point its URLs at a
  server that serves the worktree under test.
- Known quirks: `-p no:cacheprovider` avoids `.pytest_cache/` noise when running tests outside the repo; the Windows
  Store `python` stub must never be invoked (`tools/talos/pyrun` already skips it).

## Shell
- The Bash tool runs Git Bash (`MINGW64_NT-10.0-26300`, `/usr/bin/bash`). The user's primary shell is PowerShell; the
  Bash tool is not it. Use POSIX syntax, forward slashes, `/dev/null`.
- Quirks: `cd` does not persist between tool calls (cwd resets to the repo root); use absolute paths or `cd ... &&`.
  Windows paths work in both `C:/...` and `/c/...` forms inside Git Bash. `.venv/Scripts/activate` exists but is
  unnecessary; call venv binaries by path. `which bash` is Git Bash, not WSL.

## Services and ports
- No backend. ES modules do not load from `file://`, so the app is served statically (ADR-0001):
  - **8000** CEO preview and verification: `.venv/Scripts/python -m http.server 8000 --bind 0.0.0.0` from the checkout
    root, app at `/app/`.
  - **8001** ITEM-0001 engineer captures, **8002** ITEM-0002 engineer captures (127.0.0.1 is enough).
  - Tests use ephemeral ports (conftest).
- Stopping a background `http.server` from Git Bash: `kill $!` kills the shell wrapper, not `python.exe`. Use
  `netstat -ano | grep :PORT` then `taskkill //PID <n> //F`, and confirm the port is free afterwards.

## Access from other devices
- Machine: `DevBox`, Tailscale node `devbox`, IPv4 `100.64.0.10`. The CEO's phone (`phone`) is on the
  same tailnet. Every URL in a report is given in BOTH forms: `http://devbox:8000/app/` and
  `http://100.64.0.10:8000/app/`, with a note on which one was verified.

## Secrets
- None. The brief forbids accounts, backend and analytics; there is nothing to store. If a deployment target is ever
  added, name its credential here (name only, never the value).
