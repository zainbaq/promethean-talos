---
id: SPEC-0001
title: Timer screen: wall-clock countdown with Start, Pause, Reset and Focus/Break label
item: ITEM-0001
status: ready
author: chief-architect
created: 2026-10-28T04:48:05Z
---

# Timer screen: wall-clock countdown with Start, Pause, Reset and Focus/Break label

## Goal
The Timer screen of the focus app: `app/index.html`, `app/timer.js`, `app/timer.css`, with tests in `tests/test_timer.py`. A countdown starting at the saved focus length (default 25:00), one primary Start/Pause button, a Reset button and a Focus/Break/Paused label, driven by a wall-clock end timestamp exactly as ADR-0002 states. It matches the approved mockups `company/design/mockups/timer.html` (idle) and `timer-break.html` (break ready) and uses only custom-property names that exist in `app/tokens.css`. Machine facts are in `company/environment.md`; `$PY` below means the main checkout's `.venv/Scripts/python` by absolute path.

## Non-goals
No Settings screen, no edits to the shared modules, no persistence of timer state, no notifications, no pomodoro counting, no long breaks, no network calls, no build step (ADR-0001), no `<title>` updates. Markup, copy, colours and spacing come from the mockups, `company/design/components.md` and tokens; never invent them, ask.

## Files and modules in scope
_Only these may be touched. Anything else is a question, not a change._
- Create (new): `app/index.html`, `app/timer.js`, `app/timer.css`, `tests/test_timer.py`.
- Read only, on the base branch `vc/scaffold`: `app/storage.js`, `app/tokens.css`, `tests/conftest.py`.
- Do not create or edit: `app/settings.html`, `app/settings.js`, `app/settings.css`, `tests/test_settings.py` (ITEM-0002 owns them), anything under `company/` or `tools/`, `package.json`, `requirements-dev.txt`.
- Design sources, read from the MAIN checkout (repository path in environment.md; your worktree does not contain them): `company/design/direction.md`, `company/design/components.md`, `company/design/mockups/timer.html`, `company/design/mockups/timer-break.html`. Build `app/index.html` from the mockup's body and move its `<style>` block into `app/timer.css` unchanged except for adding selectors the contract below needs; `href="../tokens.css"` becomes `./tokens.css`, `href="settings.html"` becomes `./settings.html`.

## Interfaces and data shapes
Branch: `git switch -c vc/item-0001 vc/scaffold`. DOM contract: the mockup's structure and classes plus these ids, attributes and texts, which are fixed. The Settings link may 404 on your branch; expected.
```html
<link rel="stylesheet" href="./tokens.css"><link rel="stylesheet" href="./timer.css">   <!-- in <head>; no inline styles except --level below -->
<header class="bar"><h1 class="wordmark">focus</h1><a class="bar-link" id="to-settings" href="./settings.html">Settings</a></header>
<main class="stage" id="timer" data-phase="focus" data-state="idle" style="--level: 100%">   <!-- data-phase focus|break; data-state idle|running|paused -->
  <div class="tide" aria-hidden="true"></div>
  <section class="clock" aria-labelledby="phase">
    <p class="phase" id="phase" aria-live="polite">Focus</p>     <!-- textContent exactly Focus | Break | Paused -->
    <p class="count" id="count">25:00</p>                         <!-- M:SS, minutes unpadded, seconds two digits -->
    <p class="hint" id="hint">25 minutes, then a 5 minute break.</p>
  </section>
  <div class="controls">
    <button class="btn btn-primary" type="button" id="toggle">Start</button>   <!-- textContent exactly Start | Pause -->
    <button class="btn btn-secondary" type="button" id="reset" disabled>Reset</button>
  </div>
</main>
<script type="module" src="./timer.js"></script>
```
States and transitions (ADR-0002 wins on conflict). `f`, `b` are `focusMinutes`, `breakMinutes` from `loadSettings()`; `total` is the current phase length in ms.
```text
state        data-state  #phase        #count                 #hint                                              #toggle  #reset
idle focus   idle        Focus         f:00                   "{f} minute(s), then a {b} minute break."          Start    disabled (only here)
running      running     Focus|Break   ceil(remaining/1000)   hidden (visibility: hidden, keeps height)          Pause    enabled
paused       paused      Paused        frozen value           hidden                                             Start    enabled
break ready  idle        Break         b:00                   "Focus done. Start the break when you're ready."   Start    enabled
#toggle when idle or paused: endAt = Date.now() + remainingMs; setInterval(tick, 200); -> running.
#toggle when running: remainingMs = max(0, endAt - Date.now()); clearInterval; -> paused.
tick: remainingMs = max(0, endAt - Date.now()); if 0 -> phase end; render.
phase end: clearInterval; if settings.sound: Web Audio oscillator 440 Hz for 300 ms (AudioContext created lazily inside
  the #toggle click handler) then document.dispatchEvent(new CustomEvent("focus:sound")); flip phase; loadSettings();
  remainingMs = new phase length; -> idle (break ready after focus; idle focus after break). Nothing runs until #toggle.
#reset: clearInterval; loadSettings(); phase focus; remainingMs = f*60000; -> idle focus. Settings are read only at load,
  #reset and phase end. Reload: always idle focus at the saved focus length, no resumption (assumption, ADR-0002).
render: #count = `${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}` with s = ceil(remainingMs/1000);
  main.style.setProperty("--level", `${(s / (total/1000)) * 100}%`); hint plural: "1 minute, then a 5 minute break."
```
```js
import { loadSettings } from "./storage.js";   // -> {focusMinutes: int 1..120, breakMinutes: int 1..60, sound: boolean}; never throws
// tests seed a 1-minute focus with: localStorage.setItem("focus.settings.v1", JSON.stringify({focusMinutes: 1, breakMinutes: 5, sound: true})); then page.reload()
```
Fixtures from `tests/conftest.py` (do not redefine): `base_url` -> `http://127.0.0.1:<ephemeral>/app/`; `new_page(color_scheme="light"|"dark", viewport=(390, 844))` -> `Page` with empty localStorage; `axe(page)` -> list of serious/critical violations; `focus_ring(page, selector)` -> `True` when that element is focused with an outline of 2px or more. Measure criterion 1 as `time.perf_counter()` from just before `page.click("#toggle")` until `page.wait_for_function("document.getElementById('phase').textContent === 'Break'", timeout=70_000, polling=50)` returns. Disabled `#reset` is not focusable by design; the keyboard test reaches it after Start.

## Acceptance criteria
_Executed by the architect on 2026-10-28: the fixtures, the seed, the timing loop, the axe, overflow, focus-ring and screens.py commands were run against a scratch page with the real `tests/conftest.py` (6 passed, measured 60.246 s; ADR-0001 consequences). Lines marked UNEXECUTED name flows against the mockup control set, which no product code implements yet; a mismatch there is a spec question, not a product failure._
- [ ] `git ls-tree --name-only -r vc/scaffold -- app tests` prints exactly `app/storage.js`, `app/tokens.css`, `tests/conftest.py` (executed).
- [ ] UNEXECUTED `cd <worktree> && $PY -m pytest -q -p no:cacheprovider tests/test_timer.py` passes with 0 failures (about 75 s; the 1-minute test is real time).
- [ ] UNEXECUTED `test_one_minute_focus_ends_within_1s_and_switches_to_break`: seed focus 1, reload, `#count` is `1:00`; install a `focus:sound` counter; click `#toggle`; elapsed until `#phase` is `Break` is between 59.0 and 61.0 s; then `#count` is `5:00`, `data-state` is `idle`, `data-phase` is `break`, `#toggle` text is `Start`, counter is 1; 2 s later `#count` still `5:00` and counter still 1.
- [ ] UNEXECUTED `test_start_pause_resume_reset`: fresh page: `#count` `25:00`, `#phase` `Focus`, `#reset` disabled; click `#toggle`: text `Pause`, within 1.5 s `#count` is not `25:00`, `#reset` enabled; click `#toggle`: `#phase` `Paused`, `#count` unchanged over 1.5 s; click `#toggle`: 0.3 s later the display in seconds is within 1 of the paused value; click `#reset`: `25:00`, `Focus`, `data-state` `idle`, `#reset` disabled, unchanged over 1.5 s.
- [ ] UNEXECUTED `test_reload_shows_saved_focus_length`: seed `focusMinutes: 30`, reload: `#count` equals `30:00` and `#hint` equals `30 minutes, then a 5 minute break.`; click `#toggle` then `#reset`: `30:00`.
- [ ] UNEXECUTED `test_phone_fit[light]` and `[dark]` (parametrised): at 390x844 `document.documentElement.scrollWidth <= window.innerWidth` is true and the bounding boxes of `#phase`, `#count`, `#toggle`, `#reset` lie within x 0..390 and y 0..844.
- [ ] UNEXECUTED `test_axe_no_serious_or_critical[light]` and `[dark]` (parametrised): `axe(page) == []` on `index.html`.
- [ ] UNEXECUTED `test_keyboard_reach_and_focus_ring`: Tab reaches `#to-settings` then `#toggle`, `focus_ring` `True` on each; Enter on `#toggle` starts (`#count` changes within 1.5 s); Tab reaches `#reset` with `focus_ring` `True`; Space on `#reset` shows `25:00` and `Focus`.
- [ ] UNEXECUTED captures: `$PY -m http.server 8001 --bind 127.0.0.1` from the worktree root, then from the MAIN checkout root `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python tools/talos/screens.py timer=http://127.0.0.1:8001/app/index.html --out <worktree>/shots` exits 0 and prints 4 `timer` lines with `0 a11y violations` and no `HORIZONTAL OVERFLOW`; then stop the server so port 8001 is free. Design QA signs the 4 PNGs against `mockups/timer.html` (verification serves port 8000).

## Budget
- Max wall-clock: 40 min ui-engineer, 10 min code review, 25 min design QA plus verification shared with ITEM-0002; cycle ceiling 90 min (charter).
- Max parallelism: 1 engineer on this item; runs concurrently with ITEM-0002 on disjoint files.

## Constraints from the record
- ADRs: ADR-0001 (stack, serving, scaffold base, ports), ADR-0002 (countdown model, phase end, reload assumption, storage shape).
- Lessons: none; `company/knowledge/` holds no lessons yet. No pre-mortem on file.
- Environment: `company/environment.md` (interpreter, `PLAYWRIGHT_BROWSERS_PATH`, worktree layout, Tailscale URLs).

## Open questions
_File with `talos ask --for architect` and reference this spec._ None open.
