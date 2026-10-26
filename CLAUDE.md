# promethean-talos (template repo)

This repository **is the template**, not a stamped project. There is no `company/` record here and `/talos-*` skills are not active in this checkout.

- Framework files live under `template/`: `.claude/agents/`, `.claude/skills/`, `.claude/rules/`, `.claude/settings.json`, `tools/talos/`, `CLAUDE.talos.md`.
- `init.py` stamps `template/` into a target project. It refuses to stamp onto this repo.
- To test a change: stamp into a temp directory and drive the CLI there. Example:
  ```bash
  python init.py /tmp/vc-test --brief examples/brief-mdm.md
  cd /tmp/vc-test && tools/talos/talos status
  ```
- `tools/talos/talos.py` and the hook scripts are standard-library Python 3.8+; keep them dependency-free.
- Design rationale: `docs/DESIGN.md`. Role charters: `docs/ROLES.md`. How to extend: `docs/EXTENDING.md`.
- Public repo (MIT) maintained by Promethean Labs. Keep client- or project-specific content out of `template/`; project seeds belong in the stamped project's `company/knowledge/`.
