---
id: SPEC-0002
title: Settings screen: focus length, break length, sound switch, persisted in localStorage
item: ITEM-0002
status: ready
author: chief-architect
created: 2026-10-28T04:48:05Z
---

# Settings screen: focus length, break length, sound switch, persisted in localStorage

## Goal
The Settings screen of the focus app: `app/settings.html`, `app/settings.js`, `app/settings.css`, with tests in `tests/test_settings.py`. Two steppers (focus length, break length in minutes) and a sound switch, saved to localStorage through the shared `app/storage.js` on every valid change so they survive a reload (ADR-0002). It matches the approved mockup `company/design/mockups/settings.html` and uses only custom-property names that exist in `app/tokens.css`. Machine facts are in `company/environment.md`; `$PY` below means the main checkout's `.venv/Scripts/python` by absolute path.

## Non-goals
No Timer screen, no edits to the shared modules, no Save button, no accounts or sync, no themes beyond the light and dark that `tokens.css` provides, no long-break or pomodoro settings, no network calls, no build step (ADR-0001). Markup, copy, colours and spacing come from the mockup, `company/design/components.md` and tokens; never invent them, ask.

## Files and modules in scope
_Only these may be touched. Anything else is a question, not a change._
- Create (new): `app/settings.html`, `app/settings.js`, `app/settings.css`, `tests/test_settings.py`.
- Read only, on the base branch `vc/scaffold`: `app/storage.js`, `app/tokens.css`, `tests/conftest.py`.
- Do not create or edit: `app/index.html`, `app/timer.js`, `app/timer.css`, `tests/test_timer.py` (ITEM-0001 owns them), anything under `company/` or `tools/`, `package.json`, `requirements-dev.txt`.
- Design sources, read from the MAIN checkout (repository path in environment.md; your worktree does not contain them): `company/design/direction.md`, `company/design/components.md`, `company/design/mockups/settings.html`. Build `app/settings.html` from the mockup's body and move its `<style>` block into `app/settings.css` unchanged except for adding the `[data-invalid="true"]` rules below; `href="../tokens.css"` becomes `./tokens.css`, `href="timer.html"` becomes `./index.html`; drop the inline `onsubmit`.

## Interfaces and data shapes
Branch: `git switch -c vc/item-0002 vc/scaffold`. DOM contract: the mockup's structure, classes and copy plus these ids, attributes and texts, which are fixed. Ranges come from `LIMITS` in `storage.js` (ADR-0002): the mockup's help copy says 1 to 90 and 1 to 30; the product says 1 to 120 and 1 to 60 as below (the design file is being aligned; do not ask). The Timer link may 404 on your branch; expected.
```html
<link rel="stylesheet" href="./tokens.css"><link rel="stylesheet" href="./settings.css">   <!-- in <head>; no inline styles, no inline handlers -->
<header class="bar"><a class="bar-link" id="to-timer" href="./index.html"><svg …mockup svg… aria-hidden="true" focusable="false"></svg>Timer</a><h1 class="bar-title">Settings</h1><span aria-hidden="true"></span></header>
<main class="stage"><div class="tide" aria-hidden="true"></div>
<form class="sheet" id="settings-form">                                  <!-- settings.js: form.addEventListener("submit", e => e.preventDefault()) -->
  <section class="field" id="focus-field">                               <!-- data-invalid="true" while the input is invalid -->
    <div><label class="field-label" for="focus-minutes">Focus length</label>
         <p class="field-help" id="focus-help" aria-live="polite">Minutes per session, 1 to 120.</p></div>
    <div class="stepper">
      <button class="step" type="button" id="focus-dec" aria-label="Decrease focus length by one minute">&minus;</button>
      <div class="value"><input id="focus-minutes" type="number" inputmode="numeric" min="1" max="120" step="1" aria-describedby="focus-help"><span class="unit" aria-hidden="true">min</span></div>
      <button class="step" type="button" id="focus-inc" aria-label="Increase focus length by one minute">+</button>
    </div>
  </section>
  <section class="field" id="break-field">  …identical with break-dec, break-minutes (min="1" max="60"), break-inc, label "Break length", help id="break-help" "Minutes after each session, 1 to 60."…  </section>
  <section class="field field-row" id="sound-field">
    <div><span class="field-label" id="sound-label">Sound at 0:00</span><p class="field-help" id="sound-help">One soft chime when the countdown ends.</p></div>
    <div class="switch-cell"><button class="switch" type="button" id="sound-toggle" role="switch" aria-checked="true" aria-labelledby="sound-label" aria-describedby="sound-help"><span class="knob"></span></button></div>
  </section>
  <p class="note">Changes are saved on this device as you make them.</p>
</form></main>
<script type="module" src="./settings.js"></script>
```
```text
render(): s = loadSettings(); #focus-minutes.value = String(s.focusMinutes); #break-minutes.value likewise; #sound-toggle aria-checked = String(s.sound);
  #focus-dec disabled iff s.focusMinutes === 1, #focus-inc disabled iff === 120 (break: 1 and 60); clear invalid state; help text = normal copy.
input event on a minutes field: n = parseMinutes(field, el.value). n === null: el aria-invalid="true", its section data-invalid="true",
  help text = "Enter a whole number from 1 to 120." (break: "1 to 60."), nothing saved, typed text kept. Otherwise: saveSettings({[field]: n}); render().
click on #focus-dec / #focus-inc: saveSettings({focusMinutes: loadSettings().focusMinutes -/+ 1}); render(). Same for break.
click on #sound-toggle (mouse, Enter and Space all fire click on a button): saveSettings({sound: !loadSettings().sound}); render().
settings.css additions: .field[data-invalid="true"] { border-color: var(--danger); }  .field[data-invalid="true"] .field-help { color: var(--danger); }
```
```js
import { loadSettings, saveSettings, parseMinutes } from "./storage.js";
// STORAGE_KEY "focus.settings.v1"; DEFAULTS {focusMinutes: 25, breakMinutes: 5, sound: true}; LIMITS {focusMinutes: [1,120], breakMinutes: [1,60]}
// parseMinutes(field, raw) -> int | null; loadSettings() -> settings (never throws); saveSettings(partial) -> settings, throws RangeError if a minutes value is invalid
```
Fixtures from `tests/conftest.py` (do not redefine): `base_url` -> `http://127.0.0.1:<ephemeral>/app/`; `new_page(color_scheme="light"|"dark", viewport=(390, 844))` -> `Page` with empty localStorage; `axe(page)` -> list of serious/critical violations; `focus_ring(page, selector)` -> `True` when that element is focused with an outline of 2px or more. Read stored JSON with `page.evaluate('localStorage.getItem("focus.settings.v1")')`.

## Acceptance criteria
_Executed by the architect on 2026-10-28: the fixtures, `fill` on number inputs, ArrowUp stepping, switch toggling by Space and Enter, stored-JSON reads, reload, axe, overflow, focus-ring and screens.py commands were run against a scratch page with the real `tests/conftest.py` (2 passed in 2.86 s; ADR-0001 consequences). Lines marked UNEXECUTED name flows against the mockup control set, which no product code implements yet; a mismatch there is a spec question, not a product failure._
- [ ] `git ls-tree --name-only -r vc/scaffold -- app tests` prints exactly `app/storage.js`, `app/tokens.css`, `tests/conftest.py` (executed).
- [ ] UNEXECUTED `cd <worktree> && $PY -m pytest -q -p no:cacheprovider tests/test_settings.py` passes with 0 failures (one test skips on this branch, see below).
- [ ] UNEXECUTED `test_settings_persist_across_reload`: `page.fill("#focus-minutes", "30")`, `page.fill("#break-minutes", "7")`, click `#sound-toggle`; stored JSON parses to `{"focusMinutes": 30, "breakMinutes": 7, "sound": false}`; after `page.reload()` the inputs read `30` and `7` and `#sound-toggle` has `aria-checked="false"`.
- [ ] UNEXECUTED `test_saved_focus_reaches_timer`: after the steps above, click `#to-timer`; `#count` equals `30:00`; click `#toggle` then `#reset`; `#count` equals `30:00`. The test calls `pytest.skip("Timer not on this branch")` when `app/index.html` is absent from the checkout, so it runs on the integration worktree, not on `vc/item-0002` alone.
- [ ] UNEXECUTED `test_invalid_input_not_saved`: fill `#focus-minutes` with `0`, then with the empty string, and `#break-minutes` with `61`: each time the input has `aria-invalid="true"`, its section has `data-invalid="true"` and its help text equals the rule sentence above; the stored JSON is still null or the defaults; after reload the inputs show `25` and `5`.
- [ ] UNEXECUTED `test_stepper_buttons`: click `#focus-inc`: input `26`, stored `focusMinutes` 26; click `#focus-dec` twice: `24`; fill `#break-minutes` with `1`: `#break-dec` is disabled and `#break-inc` enabled.
- [ ] UNEXECUTED `test_no_network_requests`: with `page.on("request", ...)` recording every URL during load and the edits, every URL starts with the `base_url` origin (`http://127.0.0.1:<port>`).
- [ ] UNEXECUTED `test_phone_fit[light]` and `[dark]` (parametrised): at 390x844 `document.documentElement.scrollWidth <= window.innerWidth` is true and the bounding boxes of `#focus-minutes`, `#break-minutes`, `#sound-toggle` lie within x 0..390 and y 0..844.
- [ ] UNEXECUTED `test_axe_no_serious_or_critical[light]` and `[dark]` (parametrised): `axe(page) == []` on `settings.html`.
- [ ] UNEXECUTED `test_keyboard_reach_and_focus_ring`: Tab reaches, in order, `#to-timer`, `#focus-dec`, `#focus-minutes`, `#focus-inc`, `#break-dec`, `#break-minutes`, `#break-inc`, `#sound-toggle`, with `focus_ring(page, sel)` `True` on each; ArrowUp on `#focus-minutes` makes its value `26` and the stored `focusMinutes` 26; Enter on `#focus-inc` makes it `27`; Space on `#sound-toggle` gives `aria-checked="false"`, Enter gives `"true"`.
- [ ] UNEXECUTED captures: `$PY -m http.server 8002 --bind 127.0.0.1` from the worktree root, then from the MAIN checkout root `PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/Scripts/python tools/talos/screens.py settings=http://127.0.0.1:8002/app/settings.html --out <worktree>/shots` exits 0 and prints 4 `settings` lines with `0 a11y violations` and no `HORIZONTAL OVERFLOW`; then stop the server so port 8002 is free. Design QA signs the 4 PNGs against `mockups/settings.html` (verification serves port 8000).

## Budget
- Max wall-clock: 40 min ui-engineer, 10 min code review, 25 min design QA plus verification shared with ITEM-0001; cycle ceiling 90 min (charter).
- Max parallelism: 1 engineer on this item; runs concurrently with ITEM-0001 on disjoint files.

## Constraints from the record
- ADRs: ADR-0001 (stack, serving, scaffold base, ports), ADR-0002 (storage shape, limits, validation, keyboard rules).
- Lessons: none; `company/knowledge/` holds no lessons yet. No pre-mortem on file.
- Environment: `company/environment.md` (interpreter, `PLAYWRIGHT_BROWSERS_PATH`, worktree layout, Tailscale URLs).

## Open questions
_File with `talos ask --for architect` and reference this spec._ None open.
