---
id: ADR-0001
title: Stack: plain HTML, CSS and ES-module JavaScript, no build step, static files over a local HTTP server
status: accepted
author: chief-architect
created: 2026-10-28T04:47:08Z
---

# Stack: plain HTML, CSS and ES-module JavaScript, no build step, static files over a local HTTP server

## Context

The charter (small project, one 90-minute cycle, parallelism 2) asks for a two-screen phone-first timer with no CDN or network at runtime, running from local files, light and dark via prefers-color-scheme. The Head of Design mocks up in plain HTML/CSS and publishes company/design/tokens.css. The CEO default stack is Next.js, TypeScript, Tailwind and shadcn/ui. Engineers work in git worktrees that do not contain .venv or node_modules (both git-ignored, present only in the main checkout). The test toolchain is already pinned in requirements-dev.txt (pytest 9.2.0, playwright 1.64.1) on the venv Python 3.12.15 per company/environment.md.

## Decision

The product is static files under app/: index.html (Timer), settings.html (Settings), one stylesheet per screen (timer.css, settings.css), app/tokens.css (a byte copy of company/design/tokens.css, made on branch vc/scaffold by the Chief Architect after the design gate; never edited in app/), and app/storage.js, a shared ES module. Scripts are <script type=module>; no framework, no bundler, no transpiler, no npm runtime dependency, no CDN. ES modules do not load over file://, so the app is served over HTTP: for the CEO and for verification, .venv/Scripts/python -m http.server 8000 --bind 0.0.0.0 from the checkout root gives http://devbox:8000/app/ and http://100.64.0.10:8000/app/; engineers capturing their own screens use 8001 (ITEM-0001) and 8002 (ITEM-0002). Tests are pytest plus Playwright (Python) from requirements-dev.txt; tests/conftest.py (branch vc/scaffold) serves the checkout root on an ephemeral 127.0.0.1 port per pytest session, so parallel worktrees never collide, and locates the venv browser and node_modules/axe-core through sys.executable so the same command runs unchanged in a worktree. Branch vc/scaffold, cut from main at de819b4, holds exactly app/storage.js and tests/conftest.py and is the base branch for vc/item-0001 and vc/item-0002. Nav markup and each screen's CSS are copied from the mockups by each item; there is no shared layout stylesheet.

## Consequences

The CEO default (Next.js, TypeScript, Tailwind, shadcn/ui) is declined for this product: two static screens need no routing, hydration or component library; a build step and a per-worktree node_modules install would eat into a 90-minute cycle; Tailwind utilities would compete with the token stylesheet the design team owns. Costs accepted: the nav is duplicated in two HTML files (both copied from the mockups, so Design QA catches divergence); opening index.html by double-click (file://) is unsupported; no type checking. Spike evidence (2026-10-28, scratch timer plus this conftest in the scratchpad, not committed): 6 tests passed, measured focus-to-Break interval 60.246 s for a 1-minute focus, axe 0 serious/critical, module import over the ephemeral server OK, fixtures resolved .venv and axe from a directory outside the repo, screens.py produced 8 captures plus a11y.json from a temporary port 8765 which was then freed.

## Alternatives considered

Next.js + TypeScript + Tailwind + shadcn/ui (CEO default): rejected, see consequences; would be right for a product with many screens or a component system. Vite + vanilla TypeScript: rejected, a build step and dev server for no behavioural gain at this size. Classic scripts with globals so that file:// works: rejected, the phone needs an HTTP URL anyway and explicit module imports make the shared storage interface checkable. Linking company/design/tokens.css directly from app/: rejected, the product would depend on the company record path and item worktrees branched from vc/scaffold do not contain company/design/.
