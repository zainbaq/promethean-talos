# promethean-talos (template repo)

This repository **is the template**, not a stamped project. There is no `company/` record here and `/talos-*` skills are not active in this checkout.

- Framework files live under `template/`: `.claude/agents/`, `.claude/skills/`, `.claude/rules/`, `.claude/settings.json`, `tools/talos/`, `CLAUDE.talos.md`.
- `init.py` stamps `template/` into a target project. It refuses to stamp onto this repo.
- This repo is also the plugin (`.claude-plugin/`, `skills/talos/`). When `template/tools/talos/VERSION` changes, change `.claude-plugin/plugin.json` and add a section to `template/tools/talos/CHANGES.md`.
- To test a change: stamp into a temp directory and drive the CLI there. Example:
  ```bash
  python init.py /tmp/vc-test --brief examples/brief-mdm.md
  cd /tmp/vc-test && tools/talos/talos status
  ```
- `tools/talos/talos.py`, `usage.py` and the hook scripts are standard-library Python 3.8+; keep them dependency-free.
- Tests: create the repo venv once with `uv venv --python 3.12 .venv`, then run `.venv/Scripts/python -m unittest discover -s tests` (Windows) or `.venv/bin/python -m unittest discover -s tests`.
- The control room lives in `template/tools/talos/viz/` (stdlib only) and is stamped into every project unless `init.py --headless`. Its tests are pytest + Playwright under `tests/viz/` (setup in `tests/viz/requirements-dev.txt`): `.venv/Scripts/python -m pytest tests/viz -q`. To view any project from this checkout: `cd template/tools/talos && python -m viz --root <project>`.
- Design rationale: `docs/DESIGN.md`. Role charters: `docs/ROLES.md`. How to extend: `docs/EXTENDING.md`.
- Public repo (MIT) maintained by Promethean Labs. Keep client- or project-specific content out of `template/`; project seeds belong in the stamped project's `company/knowledge/`.
