#!/usr/bin/env python3
"""
screens.py: screenshots and accessibility checks for Design QA and the design gate.

    .venv/Scripts/python tools/talos/screens.py NAME=URL [NAME=URL ...] [--out DIR] [--no-axe]

For every page it captures phone (390x844) and desktop (1280x800) widths, in light and
dark colour schemes, as full-page PNGs: <out>/<name>-<phone|desktop>-<light|dark>.png.
If node_modules/axe-core is installed it runs axe on each capture and writes
<out>/a11y.json with violations by impact; serious or critical violations exit 1.

Everything is project-local (CEO decision, 2026-10-26): Playwright comes from the
project venv and its browser from PLAYWRIGHT_BROWSERS_PATH under .venv. Set up once:

    uv pip install --python .venv playwright
    PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python -m playwright install --only-shell chromium
    uv pip install --python .venv nodeenv && .venv/Scripts/nodeenv -p --node=lts --prebuilt   # Node inside .venv
    npm install --prefix . axe-core@4                                                          # with .venv/Scripts on PATH

This file needs Playwright, so it is not imported by talos.py, which stays stdlib-only.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("TALOS_ROOT", Path.cwd()))
SIZES = {"phone": (390, 844), "desktop": (1280, 800)}
SCHEMES = ("light", "dark")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    out = ROOT / "company" / "design" / "screens"
    axe = True
    pages = []
    i = 0
    while i < len(args):
        if args[i] == "--out":
            out, i = Path(args[i + 1]), i + 2
        elif args[i] == "--no-axe":
            axe, i = False, i + 1
        elif "=" in args[i]:
            name, url = args[i].split("=", 1)
            pages.append((name, url))
            i += 1
        else:
            sys.exit(f"screens: expected NAME=URL, got {args[i]!r}")
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".venv" / "ms-playwright"))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("screens: Playwright is not in the project venv. Run: uv pip install --python .venv playwright "
                 "(then install the browser as this file's --help shows)")
    axe_js = ROOT / "node_modules" / "axe-core" / "axe.min.js"
    axe = axe and axe_js.exists()
    out.mkdir(parents=True, exist_ok=True)
    report, worst = {}, 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, url in pages:
            for size, (w, h) in SIZES.items():
                for scheme in SCHEMES:
                    ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme,
                                              device_scale_factor=2 if size == "phone" else 1)
                    page = ctx.new_page()
                    page.goto(url, wait_until="networkidle")
                    shot = out / f"{name}-{size}-{scheme}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    entry = {"screenshot": shot.relative_to(ROOT).as_posix() if ROOT in shot.parents else str(shot)}
                    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
                    entry["horizontal_overflow"] = overflow
                    if overflow:
                        worst = max(worst, 1)
                    if axe:
                        page.add_script_tag(path=str(axe_js))
                        res = page.evaluate("async () => (await axe.run()).violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help}))")
                        entry["violations"] = res
                        if any(v["impact"] in ("serious", "critical") for v in res):
                            worst = max(worst, 1)
                    report[f"{name}-{size}-{scheme}"] = entry
                    print(f"{name} {size} {scheme}: {entry['screenshot']}"
                          + (f", {len(entry.get('violations', []))} a11y violations" if axe else "")
                          + (", HORIZONTAL OVERFLOW" if overflow else ""))
                    ctx.close()
        browser.close()
    (out / "a11y.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not axe:
        print("screens: axe-core not installed (node_modules/axe-core); accessibility not checked")
    return worst


if __name__ == "__main__":
    sys.exit(main())
