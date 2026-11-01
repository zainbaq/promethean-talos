# Work breakdown: wordstat

**Author:** Chief Architect · **Date:** 2026-10-25 · **Inputs:** charter (approved), ADR-0001..0006, `CONTRACT-core-cli.md`, `retros/pre-mortem-plan.md`
**For:** Head of Product (creates backlog items from this list), Chief Architect (writes one SPEC per item), Test Engineer (verification plan)

Four items, two cycles, parallelism 2. File sets are disjoint; no path appears twice. Every item is bounded by the contract so engineers never talk to each other.

## Items

- **WB-1 Core counting module and its unit tests** (engineer, cycle 1, ~15 min)
  - Owns: `wordstat/__init__.py`, `wordstat/core.py`, `tests/test_core.py`
  - Depends on: nothing (contract section 2 only)
  - Delivers: the five functions of CONTRACT section 2 with verbatim signatures and docstrings; `tests/test_core.py` asserting every row of the two worked-example tables in CONTRACT section 2 (tokeniser cases incl. `Café`, tie order, `ValueError` for n < 1, table and JSON literals, empty cases).
  - Evidence: `python -m pytest tests/test_core.py` output, all green, on 3.7.6.
  - Pre-mortem risks addressed: 2 (verbatim signatures), 5 (both formatters consume `top_words` rows), 8 (`isalnum` + `lower`, one Unicode case), 9 (`split()` with no argument, `a  b\tc\nd` test), 13/14/19 (header imports fixed, `from __future__ import annotations`, 40-line cap, no classes).

- **WB-2 README and sample fixture** (technical-writer, cycle 1, ~10 min)
  - Owns: `README.md`, `examples/sample.txt`
  - Depends on: nothing (contract sections 5 and 6 fix the file bytes and the expected outputs; the tool does not need to exist yet)
  - Delivers: `examples/sample.txt` byte-exact per CONTRACT section 5; `README.md` with the six headings and the three usage examples whose output blocks are the reference literals.
  - Evidence: `python -c` check that `examples/sample.txt` content equals the contract string; `grep -c` for each heading and for the lines `the   6`, `the 6`, `[{"word": "the", "count": 6}` in README.md. The behavioural proof lands with WB-3's drift test.
  - Pre-mortem risks addressed: 17 (README examples are the contract literals, verified by WB-3's test), 18 (`python -m wordstat` is the only invocation shown; shorthand explained once).

- **WB-3 CLI, `__main__` and subprocess tests** (engineer, cycle 2, ~25 min)
  - Owns: `wordstat/cli.py`, `wordstat/__main__.py`, `tests/test_cli.py`
  - Depends on: WB-1 merged (imports `wordstat.core`), WB-2 merged (drift test reads `README.md` and `examples/sample.txt`)
  - Delivers: `main`/`positive_int` per CONTRACT section 3; `tests/test_cli.py` using the runner of CONTRACT section 4 with tests for: default 10 rows on a 12-word fixture, `--top 3`, `--top 25` on fewer words, `--json` parses with `json.loads` and matches the table rows, `The the THE tHe` → `the 4`, `hello, hello! "hello"` → `hello 3`, `a  b\tc\nd` → four rows, empty file → zero bytes / `[]\n` exit 0, missing path → exit 1 with path in stderr, `--top 0`/`-1`/`abc` → exit 2 with the contract message, and the README drift test (three commands on `examples/sample.txt` equal `SAMPLE_*` literals and the literals appear in README.md).
  - Evidence: `python -m pytest` (full suite) output, all green, on 3.7.6, run from the repo root.
  - Pre-mortem risks addressed: 1 (owns `__main__.py`, nothing shared), 3 (exit 1 + named stderr format), 4 (`positive_int`, tests for 0/-1/abc), 5 (JSON vs table test), 6 (byte-exact table literals), 7 (empty-file bytes), 10 (`subprocess.run([sys.executable, "-m", "wordstat", ...])`, `tmp_path`, `cwd=REPO_ROOT`), 11 (`encoding="utf-8", errors="replace"`, fixtures written utf-8), 12 (`\r\n` normalisation), 17 (drift test), 18 (`-m` entry point exercised).

- **WB-4 Constraint tests: imports, syntax, size** (test-engineer, cycle 2, ~10 min)
  - Owns: `tests/test_constraints.py`
  - Depends on: WB-1 merged (so `wordstat/*.py` exists); written against ADR-0006 so it also passes once WB-3 lands, because `cli.py`'s imports are fixed in CONTRACT section 3
  - Delivers: a test that reads every `wordstat/*.py` as text and asserts (a) every `import`/`from` line names only `__future__`, `argparse`, `collections`, `json`, `pathlib`, `sys`, `typing`, `wordstat.core`; (b) no line contains `:=`, `list[`, `dict[`, `tuple[`, `| None` or starts with `match `; (c) `core.py` and `cli.py` each have at most 40 non-blank, non-docstring, non-comment lines; (d) `core.py` imports nothing beyond `__future__`, `collections`, `json`, `typing`.
  - Evidence: `python -m pytest tests/test_constraints.py` green on WB-1's files; re-run green after WB-3 merges.
  - Pre-mortem risks addressed: 13 (3.8-incompatible syntax grep; interpreter named), 14 (import allowlist as an executable check), 19 (size cap enforced, not just requested).

## Schedule

| Cycle | Slot A | Slot B | Gate after |
|---|---|---|---|
| 1 | WB-1 core + unit tests | WB-2 README + sample | both merged; `python -m pytest` green (only test_core runs) |
| 2 | WB-3 CLI + subprocess tests | WB-4 constraint tests | both merged; Test Engineer full verification (below) |

WB-3 and WB-4 wait for cycle 1 because both need `wordstat/core.py` in the tree. Nothing else waits. If WB-1 slips, WB-3 cannot start; WB-4 cannot start either; WB-2 is unaffected.

## Verification and release conditions (process, not work items)

- After cycle 2 the Test Engineer runs `python -m pytest` on a fresh `git worktree add` of the merged branch (not the engineers' worktrees) with `C:/Users/you/anaconda3/python.exe`, plus the manual charter checks: the three README commands, and `grep -E "^(import|from) " wordstat/*.py`. Attach the transcript as evidence (pre-mortem 10).
- After any review fix the same full run is repeated from a fresh worktree before `company gate release`; a green run before the fix is not evidence (pre-mortem 20).
- Each SPEC the Chief Architect writes lists acceptance criteria only as pytest test names or shell commands with expected stdout and exit code (pre-mortem 15), and ends with a "stop and ask" list naming the decided points: exit codes (ADR-0004), `--top` validation (ADR-0004), tokeniser and `lower` vs `casefold` (ADR-0002), table bytes (ADR-0003), 3.7.6 interpreter (ADR-0006) (pre-mortem 16).

## Pre-mortem coverage

| Risk | Where addressed |
|---|---|
| 1 | disjoint file sets above; ADR-0001 names owners of `__init__.py` and `__main__.py` |
| 2, 5, 8, 9 | ADR-0002, CONTRACT section 2, WB-1 |
| 3, 4, 11 | ADR-0004, CONTRACT section 3, WB-3 |
| 6, 7 | ADR-0003, CONTRACT sections 2 and 5, WB-1 and WB-3 |
| 10, 12 | ADR-0005, CONTRACT section 4, WB-3, verification conditions |
| 13, 14, 19 | ADR-0006, WB-4 |
| 15, 16 | SPEC template rule in verification conditions (applied when specs are written) |
| 17, 18 | ADR-0001, ADR-0005, WB-2, WB-3 drift test |
| 20 | verification conditions |

All 20 risks have an owner. One note for the record: the charter says Python 3.8+, but the only interpreter on the CEO's machine is CPython 3.7.6; ADR-0006 therefore forbids 3.8-only syntax as well, so the code runs on both. If the CEO wants the suite proven on a 3.8+ interpreter, that is a charter-level ask (installing one is outside scope).
