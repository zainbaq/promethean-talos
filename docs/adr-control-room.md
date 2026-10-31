# The visualizer may write: the control room

Status: accepted 2026-10-31. Supersedes the visualizer's read-only decision (ADR-0001 point 3 and ADR-0008, in the record of the project that built it).

## Decision

The visualizer becomes where the CEO steers the company: approve or reject a gate, answer a question, send a message, set the preset. `--read-only` keeps the old behaviour.

- **It only records.** Each POST maps to one Talos CLI command with validated arguments and no shell (`viz/control.py`). The server never starts a phase or runs Claude. `talos work` reads the record and acts.
- **Who may write.** A secret is generated at every start and printed as a link. Opening `?k=<secret>` sets an HttpOnly, SameSite=Strict cookie and removes the secret from the address bar. Every POST needs the cookie, a same-origin `Origin` header and a JSON body under 16 KB.
- **Reads stay open** to whoever passes the host allow-list, as before. The server binds to 127.0.0.1 unless `--host` is given.
- **Chat text is data.** Nothing typed is run as a command. The company is told to treat it as the CEO's input and to say what each message became. The only words with an effect of their own are the bare `pause`, `resume` and `stop`, which set the runner's state.

## Why

A gate waited 5h04m for a one-line answer on a real project. The CEO reads the page from a phone, so that is where the answer belongs.

## What it costs

The page is now a write surface. There is no TLS over a plain tailnet address, so the secret is only as private as the tailnet, which is the boundary this project already relies on. A restart invalidates old links.
