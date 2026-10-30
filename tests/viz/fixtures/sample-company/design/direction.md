# Design direction: focus

## Who it is for
One person, phone in hand or at a desk, who wants to start a quiet 25-minute stretch of work and be told,
gently, when it is over. Keyboard-only and screen-reader users are first-class: every control is a real
button or input, every state has a visible focus ring.

## Mood, three words
Quiet. Warm. Patient.

## References
- Braun clocks (Dietrich Lubs): one function, honest numerals, nothing decorative. https://www.braun-clocks.com/
- The original kitchen-timer pomodoro: you read remaining time as a physical level from across the room,
  not by squinting at digits. https://francescocirillo.com/products/the-pomodoro-technique
- Vitsoe on Rams' "as little design as possible": the screen should feel finished because nothing is left to
  remove. https://www.vitsoe.com/gb/about/good-design

## The one distinctive idea: the tide
The screen itself is the timer. Behind the numerals a flat band of colour (`--tide`) fills the whole stage when
a session is ready and drains downward, one step a second, as time passes; the paper background shows above
the water line. Remaining time is a level you read from a metre away. At 0:00 the stage is bare paper, then
fills again in a warm clay tide for the break. Light teal for focus, warm clay for break: the colour tells you
which half you are in before you read the label. The numerals are large, light-weight, tabular and secondary.

## Type and colour
System fonts only (no network): `ui-rounded` / SF Pro Rounded on Apple, Segoe UI Variable on Windows, with
`tabular-nums` so the countdown never jitters. Warm paper, not white; charcoal with a green cast, not black.
One accent per phase, white or ink on top of it. Every value lives in `tokens.css`; nobody invents a colour.

## Avoid
- Progress rings, circular dials, gradients, drop shadows, glassmorphism. The tide is the only indicator.
- Pure white (#FFF) or pure black (#000) backgrounds; default browser blue; unstyled form controls.
- Chatty copy, emoji, exclamation marks, "You've got this". The app is a clock, not a coach.
- Hover-only affordances; anything that needs a second tap to reach Start, Pause or Reset.
- Per-second screen-reader announcements; announce only on phase change (ready, running, paused, break).
