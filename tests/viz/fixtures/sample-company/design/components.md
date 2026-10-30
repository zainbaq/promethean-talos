# Components

Both screens are built from these and nothing else. Every size and colour is a token from `tokens.css`;
"hover" means pointer only, never the sole affordance. All interactive elements are native `<button>`, `<a>`
or `<input>`: Tab reaches them, Enter or Space operates them, `:focus-visible` shows the ring. Reference
mockups: `mockups/timer.html` (idle), `mockups/timer-break.html` (0:00, break ready), `mockups/settings.html`.

## Focus ring (global)
`:focus-visible { outline: var(--focus-width) solid var(--focus); outline-offset: var(--focus-offset); }`
Never `outline: none` without this replacement. The offset gap makes the ring visible on accent buttons too.

## App column
`max-width: var(--content-max)`, centred, `min-height: 100dvh`, background `--bg`. On desktop (1280) a 1px
`--line` border on each side so the column reads as deliberate. No other desktop layout.

## Top bar
Height `--control-h`, padding `0 var(--space-4)`, flex, space-between, on `--bg`.
- Timer: wordmark `focus` (h1, `--font-display`, `--text-lg`, `--weight-bold`, `--ink`, with an 8px `--accent` dot) left; **bar link** "Settings" right.
- Settings: **bar link** "Timer" with a leading chevron left; title "Settings" (h1, `--text-lg`, `--weight-semibold`) centred; empty spacer right so the title stays centred.

## Bar link (`<a>`)
`--text-md`, `--weight-semibold`, colour `--accent` (or `--accent-break` while on break), min-height `--tap-min`, padding `0 var(--space-3)`, radius `--radius-md`. Hover: background `--surface`. Focus: ring. No disabled state.

## Stage and tide (Timer, Settings)
`main` is `position: relative; flex: 1; overflow: hidden`. The **tide** is an `aria-hidden` child, absolute,
`left:0; right:0; bottom:0; height: var(--level)`, background `--tide`, `border-top: 2px solid --tide-edge`,
`transition: height var(--tide-step)`. `--level` is `100%` when ready, `remaining / total` while running
(updated once a second from wall-clock time), `0%` at 0:00. Break phase (`data-phase="break"`) swaps to
`--tide-break` / `--tide-break-edge`. Settings shows the tide at `100%` in the focus colour, always.

## Phase label (Timer)
`<p>` above the countdown. `--text-sm`, `--weight-semibold`, uppercase, `letter-spacing: --tracking-caps`.
- Focus: text "Focus", colour `--accent`.
- Break: text "Break", colour `--accent-break`.
- Paused: text "Paused", colour `--ink-muted`.
This is the element to announce on change (`aria-live="polite"`), not the countdown.

## Countdown (Timer)
`--font-display`, `--text-display`, `--weight-light`, `--leading-tight`, `font-variant-numeric: tabular-nums`,
colour `--ink`, format `M:SS` (`25:00`, `5:00`, `0:00`). Paused: colour `--ink-muted`. No live region on the
number itself (per-second announcements are noise). Below it a **hint** line, `--text-sm`, `--ink-muted`:
idle "25 minutes, then a 5 minute break." / break ready "Focus done. Start the break when you're ready." /
running and paused: hidden (`visibility: hidden`, keeps its height so nothing jumps).

## Primary button (`<button>`)
Full width, height `--primary-h`, radius `--radius-lg`, `--text-lg`, `--weight-semibold`, background
`--accent`, colour `--on-accent`; break phase uses `--accent-break` / `--on-accent-break`.
States: default; hover `--accent-hover` (`--accent-break-hover`); active `transform: scale(0.99)`; focus ring;
disabled `--ink-disabled` text on `--line`, `cursor: default`. Label is the state machine: "Start" (idle,
paused, break ready) or "Pause" (running). No loading state: there is nothing to load.

## Secondary button (`<button>`)
Full width, height `--control-h`, radius `--radius-lg`, transparent, `1.5px solid --line-strong`, colour
`--ink`, `--text-lg`, `--weight-semibold`. Hover: background `--surface`. Focus ring. Disabled: colour
`--ink-disabled`, border `--line`. Used for "Reset" (disabled while idle at the configured length; enabled
once anything has changed, including while running).

## Field (Settings)
A `--surface` card, radius `--radius-lg`, `1px solid --line`, padding `var(--space-4) var(--space-5)`,
gap `--space-3`. Contains a **field label** (`<label>` or labelled span, `--text-md`, `--weight-semibold`,
`--ink`), a **help** line (`--text-sm`, `--ink-muted`) and one control. Error: help text becomes `--danger`
and reads the rule ("Enter a whole number from 1 to 120." for focus, "1 to 60" for break); the card border becomes `--danger`; the stored
value is unchanged until the input is valid. Empty: not applicable (defaults always exist).

## Stepper (Settings: focus length, break length)
Row, height `--control-h`: **decrement** `<button aria-label="Decrease focus length">` (`--tap-min` square,
radius `--radius-md`, `--surface` on `--line` border, glyph `−` at `--text-xl`), **value** `<input type="number"
inputmode="numeric" min max step="1">` (`--font-display`, `--text-2xl`, `--weight-light`, tabular, centred,
`3ch` wide, no border, transparent, spin buttons hidden), **unit** "min" (`--text-sm`, `--ink-muted`),
**increment** button likewise. Buttons: hover `--bg`, focus ring, disabled at the range limit
(`--ink-disabled`). Input: focus ring; error per Field. Arrow keys on the input also step by 1.
Ranges (ADR-0002): focus 1..120, break 1..60. `min`/`max` come from `LIMITS` in `app/storage.js`.

## Switch (Settings: sound)
`<button type="button" role="switch" aria-checked aria-labelledby aria-describedby>`, track `--switch-w` x
`--switch-h`, radius `--radius-pill`; knob `calc(--switch-h - 8px)` circle, `--surface`, moves over
`--dur-base --ease`. On: track `--accent`. Off: track `--line-strong`. Hover: track `--accent-hover` /
`--ink-muted`. Focus ring. Disabled: `--line` track, `--ink-disabled` knob. Row height `--control-h`,
label and help on the left, switch on the right, whole row is not a click target (only the switch is).

## Note (Settings)
`<p>` under the fields, `--text-sm`, `--ink-muted`, centred: "Changes are saved on this device as you make
them." No Save button exists; the copy is the affordance.

## Screen navigation
Two documents (or two views, the architect decides) linked by the two bar links; the browser Back button
must work. The tide colour carries across so the switch of screen does not feel like a page load.
