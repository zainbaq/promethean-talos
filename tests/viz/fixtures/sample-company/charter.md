---
status: approved
approved_event: EVT-20261028043125-7723
size: small
---

# Charter: focus

## 1. Goal
A calm, phone-first focus timer in the browser: a Timer screen (25-minute default countdown, start, pause, reset, focus/break label) and a Settings screen (focus length, break length, sound on/off) that survive a reload.

## 2. Non-goals
- Accounts, login, backend, sync between devices, analytics or any network calls at runtime.
- Native or installable apps (no PWA, no app store).
- Notifications beyond the in-page sound: no browser push, no OS notifications.
- Long-break scheduling or pomodoro counting (no "4 sessions then a long break"). Assumed out; say so if you want it in.
- Task lists, history, statistics, themes beyond light and dark.

## 3. Target users
One person at a desk or on a phone who wants a single, quiet countdown to start work and a short break after. Keyboard-only and screen-reader users are included, not an afterthought.

## 4. Success criteria (a Test Engineer or Design QA runs each one)
1. **Timer accuracy.** With focus set to 1 minute, a Playwright run from Start to 0:00 measures within 1 second of 60 s wall-clock, and the label switches from Focus to Break.
2. **Controls work.** Start, Pause, Reset each change the display as named; Pause then Start resumes from the paused value; Reset returns to the configured focus length.
3. **Settings survive reload.** Set focus 30, break 7, sound off; reload the page; the Settings screen shows the same values and the Timer shows 30:00.
4. **Phone fit.** At 390 px width (light and dark) there is no horizontal scroll and the countdown, all controls and the label are visible without scrolling.
5. **Dark and light captures.** Both screens captured at 390x844 and 1280x800 in light and dark (`tools/talos/screens.py`); Design QA signs each as matching the approved mockups.
6. **Accessibility.** axe-core reports zero serious or critical violations on both screens in both modes; every control is reachable by Tab and operable by Enter or Space, with a visible focus ring.
7. **Design gate passed.** The CEO approved the direction and key mockups (`talos gate design`) before engineering began.

## 5. Constraints
- Everything project-local per `company/environment.md`: project venv, Node in the venv, Playwright and axe-core from the repo. No machine interpreters.
- Proposal: no CDN or network dependencies at runtime; the app runs from local files. The Chief Architect confirms the stack.
- Two backlog items, one per screen, one cycle. Every document short; this charter stays under 80 lines.
- Core and design teams only. Design gate is mandatory; only the CEO can waive it.

## 6. Risks
- The design gate is new and untested; a slow or unclear mockup round delays the only cycle.
- Browser timers drift or throttle when a tab is backgrounded; the countdown must use wall-clock time, not tick counts.
- Two parallel items share one look; if Timer and Settings diverge visually, Design QA fails one of them late.
- Sound playback may be blocked by autoplay rules until the user interacts; the test must press Start first.
- Playwright on Windows needs the `PLAYWRIGHT_BROWSERS_PATH` quirk every call; a missed env var looks like a product failure.

## 7. Budget and parallelism
- One cycle. Budget: **2 items through design QA and verification in one cycle.** Parallelism: 2.
- Wall-clock ceiling for the whole loop (design critique, engineering, review, design QA, verification): 90 minutes. If exceeded, the Chief of Staff stops and reports rather than extending.

## 8. Where the work lives
Repository `C:\Users\ceo\AppData\Local\Temp\claude\D--Projects-Promethean\0d1279cd-a8fd-45ee-a27d-13220792d67f\scratchpad\talos-ui`, base branch `main`. Work on `vc/<item-id>` branches in worktrees. Nothing merges to `main` until the CEO approves the release.

## 9. Definition of done
Both items verified against criteria 1 to 6 with evidence in the cycle report, criterion 7 recorded in the ledger, release approved by the CEO in their own words, and a retro filed. The app opens from a local URL on the CEO's phone and the timer runs.

## 10. Project size
`small`. Two screens, no data model beyond three settings, one cycle; planning depth beyond one ADR and two specs would cost more than it saves.

## 11. Teams staffed
`core` and `design`. Research is not staffed: the brief makes no market, pricing or feasibility claims, and the CEO did not ask for it.

## 12. Open questions for the CEO
- **Q-0001:** When focus reaches 0:00, auto-start the break or wait for the user? Proposed default: wait. Label switches to Break, sound plays if enabled, countdown shows the break length, nothing runs until Start. Planning proceeds on the default.
