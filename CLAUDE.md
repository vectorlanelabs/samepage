# Dinner Decider — Implementer Constraints (CLAUDE.md)

**Read first, in order:** `docs/PLAN-v1-mvp.md` (the plan — binding spec) → `CHARTER.md` (scope & non-goals). These files are the contract. When in doubt, the plan wins over guesswork; when the plan is silent, ask — never invent product decisions.

## Stack (locked — do not change without Charlie's word)

- Python 3.12+, **uv** for env/deps, **FastAPI**, **SQLAlchemy 2.x**, **SQLite**, **Jinja2**, **HTMX** + minimal vanilla JS.
- **No frontend build step. No Node.** No new dependencies without lead approval (note it in REQUESTS.md instead).

## Non-negotiables

1. **Green or honest**: run `uv run ruff check .` and `uv run pytest -q` before claiming done. Both must be green. If something is red or doesn't work, **report it** — a false "all green" is the worst possible outcome, worse than a failing test.
2. **TDD for logic**: common-ground computation, pool sampling, round-code generation, import parsing — tests first, code to pass.
3. **Never auto-delete data.** Archive/reversible only. Import never auto-merges or mutates the spreadsheet.
4. **Vote privacy is security**: no vote tally appears in any client response until the round is closed. This is the one invariant that gets you pulled from a slice.
5. **One slice, one commit**, conventional messages (`feat:`, `fix:`, `test:`, `chore:`).
6. Follow the lead's delegation contract exactly: stated files, do-NOT list, verification commands with expected outputs, honest-failure escape hatch.

## Files you own / never touch

- **Own**: `app/`, `tests/`, `scripts/`, `pyproject.toml`, `.github/`.
- **Never touch**: `CHARTER.md`, `ROADMAP.md`, `docs/PLAN-v1-mvp.md`, `docs/POST-V1.md`, `docs/DEVLOG.md`, `REQUESTS.md`, `CLAUDE.md`, `reference/` (read-only source data).
- Commit messages and branch hygiene are the lead's job. Don't push; the lead lands slices.

## Reporting format (after every slice)

```
Slice: <id>
Changed: <files>
Tests: <count passed/failed> — commands run, paste real output lines
Verification: <exact commands + outputs>
Honest notes: <anything that didn't work / is uncertain>
```
