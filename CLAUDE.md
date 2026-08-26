# Dinner Decider — Implementer Constraints (CLAUDE.md)

**Read first, in order:** `docs/PLAN-v1-mvp.md` (the plan — binding spec) → `CHARTER.md` (scope & non-goals). These files are the contract. When in doubt, the plan wins over guesswork; when the plan is silent, ask — never invent product decisions.

## Stack (locked — do not change without Charlie's word)

- Python 3.12+, **uv** for env/deps, **FastAPI**, **SQLAlchemy 2.x**, **SQLite**, **Jinja2**, **HTMX** + minimal vanilla JS.
- **No frontend build step. No Node.** No new runtime dependencies without lead approval (note it in REQUESTS.md instead). openpyxl is a **dev-only** dependency (seed regeneration).

## Product shape (corrected 2026-08-26 — do not regress to the old concept)

- The product is a **weekly planning session**: set lunch/dinner targets → iterative batches of 15–20 meals → private **binary yes/no** votes → unanimous-yes meals kept → repeat until targets met.
- **No dice roll. No "not tonight" / vote shades. No import feature or import UI.** The library is pre-seeded from `seed/meals.json`.
- Meals have title, type (lunch/dinner/both), category, tags, recipe (link/text). `times_kept`/`last_kept_at` are the favorites signal.
- **Deployment is VPS-hosted** (Charlie's Hostinger VPS, behind HTTPS via Caddy) — the app is internet-facing; no LAN/local-only assumptions. Deployment specifics: plan §7.1. Env: `DD_SECRET`, `DD_ACCESS_KEY` (household access gate, once per device), `DD_DB_PATH`, `DD_PORT`.

## Non-negotiables

1. **Green or honest**: run `uv run ruff check .` and `uv run pytest -q` before claiming done. Both must be green. If something is red or doesn't work, **report it** — a false "all green" is the worst possible outcome, worse than a failing test.
2. **TDD for logic**: session_logic (batch assembly, unanimous keeps, over-target resolution, track progression), session-code generation, seed loading — tests first, code to pass.
3. **Never auto-delete data.** Archive/reversible only. The seed loader dedupes and logs; it never mutates the spreadsheet or the committed seed JSON.
4. **Vote privacy is security**: no vote data other than the caller's own appears in any client response until the batch is closed. This is the one invariant that gets you pulled from a slice.
5. **The app is public on the internet** — anything user-visible must be safe to expose (no secrets in HTML/JS, no debug output in prod, no client-side credentials).
6. **One slice, one commit**, conventional messages (`feat:`, `fix:`, `test:`, `chore:`).
7. Follow the lead's delegation contract exactly: stated files, do-NOT list, verification commands with expected outputs, honest-failure escape hatch.

## Files you own / never touch

- **Own**: `app/`, `tests/`, `scripts/` (seed.py, build_seed.py), `pyproject.toml`, `.github/`, deployment files (Dockerfile / compose / Caddyfile when they land in M5).
- **Never touch**: `CHARTER.md`, `ROADMAP.md`, `docs/PLAN-v1-mvp.md`, `docs/POST-V1.md`, `docs/DEVLOG.md`, `REQUESTS.md`, `CLAUDE.md`, `reference/` (read-only source data), `seed/meals.json` (lead-owned data — regenerate via `scripts/build_seed.py`, never hand-edit).
- Commit messages and branch hygiene are the lead's job. Don't push; the lead lands slices.

## Reporting format (after every slice)

```
Slice: <id>
Changed: <files>
Tests: <count passed/failed> — commands run, paste real output lines
Verification: <exact commands + outputs>
Honest notes: <anything that didn't work / is uncertain>
```
