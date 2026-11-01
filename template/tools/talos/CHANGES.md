# What changed in Talos

Newest first. `init.py --upgrade` shows the parts newer than a project's version.

## 0.3.2
- Running `git init` by hand now answers the company's question about it, so the runner doesn't wait forever.
- `/talos` records your answers to the company's questions instead of acting on them itself.

## 0.3.1
- `talos work --max-usd N` no longer fails, so `/talos` starts the runner on the first try.

## 0.3.0
- Any folder: empty, not a repo, or a project under way. Adoption and the understanding gate.
- Say anything: triage answers it or picks a route. GTM and productization departments draft and never send.
- The control room comes with every project (`--headless` leaves it out): approve, answer, message, preset.
- `talos protect`: the company never changes a branch. Work goes on `talos/work`, and the record is saved on `talos/record`.
- `talos automerge on`: verified low-risk fast-lane fixes merge without asking. Off by default.
- `talos notify <url>`: a gate's name goes to an address you choose. Off by default.
- Lite, medium and heavy presets, and a design revision that doesn't rerun the plan.
