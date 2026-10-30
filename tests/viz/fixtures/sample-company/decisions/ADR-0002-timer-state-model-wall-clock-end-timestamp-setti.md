---
id: ADR-0002
title: Timer state model: wall-clock end timestamp; settings persisted as JSON in localStorage key focus.settings.v1
status: accepted
author: chief-architect
created: 2026-10-28T04:47:35Z
---

# Timer state model: wall-clock end timestamp; settings persisted as JSON in localStorage key focus.settings.v1

## Context

Charter risk: browser timers drift and are throttled in background tabs, so the countdown must use wall-clock time, not tick counts. Criterion 1 requires a 1-minute focus to end within 1 s of 60 s wall-clock. Criterion 3 requires focus, break and sound to survive a reload and the Timer to show the saved focus length. Q-0001 (CEO approved): at focus 0:00 the app waits for the user. The Head of Product asked how break end, input validation, mid-countdown settings changes, non-button keyboard operation and reload behave.

## Decision

COUNTDOWN. The Timer holds remainingMs and, while running, endAt = Date.now() + remainingMs; a setInterval of 200 ms recomputes remainingMs = max(0, endAt - Date.now()). The display shows ceil(remainingMs / 1000) formatted as M:SS with minutes unpadded and seconds two digits (25:00, 1:00, 0:05). Start when idle sets endAt and starts the interval; Start while running does nothing. Pause stores remainingMs and clears the interval; Pause while idle does nothing. Reset clears the interval, re-reads settings, sets phase to focus and remainingMs to focusMinutes. PHASE END (remainingMs reaches 0): the interval stops; if settings.sound is true a sound plays once (Web Audio oscillator, 440 Hz, 300 ms, AudioContext created on the first Start click so autoplay rules allow it) and in all cases document dispatches CustomEvent focus:sound only when a sound was played; the phase flips (focus to break, break to focus), the label flips (Focus/Break), settings are re-read and remainingMs becomes the new phase length; nothing runs until Start. Break end mirrors focus end. Settings are read only at page load, on Reset and at phase end; a running countdown is never changed by a settings edit. RELOAD: the Timer always starts idle in the focus phase at the saved focus length; no timer state is persisted and no session is resumed (stated assumption for the CEO at the plan gate). PERSISTENCE: localStorage key focus.settings.v1 holds JSON {"focusMinutes":25,"breakMinutes":5,"sound":true} (these are the defaults). Limits: focusMinutes integer 1 to 120, breakMinutes integer 1 to 60, sound boolean. app/storage.js exports STORAGE_KEY, DEFAULTS, LIMITS, parseMinutes(field, raw), loadSettings() and saveSettings(partial); loadSettings never throws and falls back to the default for each invalid or missing field; saveSettings throws RangeError on an invalid minutes value and writes nothing. SETTINGS SCREEN: focus and break are <input type=number inputmode=numeric step=1> with min and max from LIMITS; sound is <button type=button role=switch aria-checked>. Every valid input event saves immediately (no Save button). An empty, non-integer or out-of-range value is not saved: the input gets aria-invalid=true and its inline error paragraph (role=alert) becomes visible with the text Enter a whole number from 1 to 120 (or 1 to 60); the stored value is unchanged and reappears on reload. Keyboard: buttons and the switch operate by Enter or Space; number inputs by typing digits or ArrowUp/ArrowDown; every control is in the Tab order and shows a focus ring drawn with CSS outline of at least 2px on :focus-visible.

## Consequences

Accuracy is bounded by one interval tick (200 ms) plus the render, independent of tab throttling, because remaining time is derived from the end timestamp; the spike measured 60.246 s for a 1-minute focus. The display never shows 0:00 while running (ceil), and at phase end immediately shows the next phase length, so tests observe the end instant as the label change. Tests set a 1-minute focus by writing the JSON above to localStorage and reloading, which decouples the Timer item from the Settings item. Saving on every valid input means typing 3 then 0 stores 3 then 30; acceptable. The versioned key allows a later shape change without migration bugs. Sound plays only in the tab that ran the timer; no notifications (charter non-goal). Multi-tab edits are not synchronised (not in scope).

## Alternatives considered

Decrementing a counter on setInterval: rejected, drifts and is throttled to 1 Hz or less in background tabs. requestAnimationFrame: rejected, pauses entirely in hidden tabs. Persisting timer state to resume after reload: rejected, not in the charter; surfaced as an assumption. Auto-starting the break: rejected by the CEO (Q-0001). Save button on Settings: rejected, an extra control and an extra state for no requirement. Checkbox for sound: viable, but a role=switch button is operable by both Enter and Space and matches the charter wording. Cookies or IndexedDB: rejected, three fields need neither.
