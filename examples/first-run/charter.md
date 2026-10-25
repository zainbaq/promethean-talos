---
status: approved
approved_event: EVT-20261025155321-7732
---

# Charter: wordstat

**Source:** `company/brief.md` (Zain, 2026-10-25) · **Author:** Head of Product · **Status:** draft, awaiting CEO approval

## Goal

Ship `wordstat`, a standard-library-only Python 3.8+ command-line tool that reads one text file and prints its most frequent words as an aligned table or as JSON, with pytest tests and a README.

## Non-goals

This is a framework test. The scope is exactly the brief. We will **not** build:

- Reading from stdin, URLs, directories or more than one file at a time.
- Stop-word lists, stemming, language detection or any "smart" word handling.
- Output formats other than the table and `--json` (no CSV, no charts).
- Configuration files, plugins, colours or a progress bar.
- Packaging to PyPI, Docker images or CI pipelines beyond what is needed to run the tests locally.
- Any third-party dependency, including for tests beyond pytest itself.

If someone wants one of these, it goes to the CEO as a charter amendment first.

## Target users

- **Primary:** Zain, the CEO, checking that the Virtual Company framework can take a small brief end-to-end: charter, plan, build, test, review, ship.
- **Secondary:** anyone with Python 3.8+ who wants a quick word count of a text file from the terminal and can read a short README.

## Success criteria

Each criterion is a test the Test Engineer can run. "Done" means all of them pass.

1. `wordstat path/to/file.txt` on a sample file prints exactly 10 rows (or fewer if the file has fewer distinct words), each row showing the word and its count, with counts aligned in a column.
2. `wordstat file.txt --top 3` prints exactly 3 rows; `--top 25` prints up to 25.
3. `wordstat file.txt --json` prints valid JSON (parseable by `json.loads`) containing the same words, counts and order as the table for the same arguments.
4. A file containing `The the THE tHe` counts `the` once with a count of 4 (case-insensitive).
5. A file containing `hello, hello! "hello"` counts `hello` with a count of 3 (punctuation ignored).
6. Words are split on whitespace only: `a  b\tc\nd` yields four words, each counted once.
7. Running on a missing path prints a clear message to stderr and exits with a non-zero code; running on an empty file prints an empty table (or `[]` with `--json`) and exits 0.
8. `python -m pytest` passes from a clean checkout with no packages installed beyond Python and pytest.
9. The README shows installation (or "run it directly") and at least one example each of the default run, `--top N` and `--json`, and a copy-pasted example from the README works as written.
10. `grep`-level check: the source imports nothing outside the Python standard library.

## Constraints

- Python 3.8+, standard library only. Tests use pytest and nothing else.
- Scope is frozen at the brief. No extra flags, formats or features.
- No research step; the brief is treated as complete.
- All record writes go through `tools/company/company`; nobody hand-edits the ledger.
- Every claim of "done" needs evidence attached (test output, command transcript).

## Proposed defaults for the two open details

The brief leaves two small behaviours unspecified. Both are filed as questions; the defaults below apply unless the CEO says otherwise, so planning does not block.

- **Q-0001, punctuation inside a word.** Default: strip every character that is not a letter or digit from each whitespace-split token, so `don't` becomes `dont` and `well-known` becomes `wellknown`. Tokens that end up empty are dropped.
- **Q-0002, tie order.** Default: sort by count descending, then alphabetically A to Z. This keeps the table and `--json` deterministic and identical.

## Risks

| Risk | Why it matters | Mitigation |
|---|---|---|
| Scope creep ("while we're here, add stdin") | Defeats the point of a framework test | Non-goals list above; any addition needs a charter amendment |
| Two engineers edit the same file in parallel | Merge conflicts eat the 30-minute budget | Plan step splits work into non-overlapping files (e.g. core counting vs CLI/README) |
| Non-deterministic output for ties | Flaky tests, JSON and table disagree | Default tie rule above, locked in by a test |
| Unicode or odd whitespace in input | Counting diverges from expectation | Tests use ASCII plus one simple Unicode case; nothing fancier is in scope |
| Over-engineering a tiny tool | Burns budget, obscures what the framework test is measuring | Items under 40 lines, specs name exact files, reviewers reject anything not traceable to this charter |

## Budget and parallelism

From the brief, per cycle:

- **Wall-clock:** 30 minutes.
- **Parallelism:** 2 engineers at once.
- Anything that does not fit a cycle is split or deferred; nobody extends a cycle silently.

## Definition of done

The project is done when all of the following are true and recorded in the ledger:

1. All ten success criteria above pass, with pytest output attached as evidence.
2. Code review and security review have reported no open blocking findings.
3. The README matches the shipped behaviour (an example run from it produces the documented output).
4. The CEO has approved the release gate in their own words.
5. A retro has been run and any lessons with evidence are filed in `company/knowledge/`.

Nothing beyond this list is required. If it is not in this charter, it is not in the project.
