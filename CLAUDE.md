# Dinner Decider — Implementer Constraints (CLAUDE.md)

**Read first, in order:** `docs/PLAN-v1-mvp.md` (the plan — binding spec) → `CHARTER.md` (scope & non-goals). These files are the contract. When in doubt, the plan wins over guesswork; when the plan is silent, ask — never invent product decisions.

## Stack (locked — do not change without Charlie's word)

- Python 3.12+, **uv** for env/deps, **FastAPI**, **SQLAlchemy 2.x**, **SQLite**, **Jinja2**, **HTMX** + minimal vanilla JS.
- **No frontend build step. No Node.** No new runtime dependencies without lead approval (note it in REQUESTS.md instead). openpyxl is a **dev-only** dependency (seed regeneration).

## Product shape (binding)

The app exists to **replace** the spreadsheet-and-dice ritual — it was never a dice-roll app; the D8/D20 mechanic is the pain point, not the product.

- The product is a **weekly planning session**: set lunch/dinner targets → iterative batches of 15–20 meals → private **binary yes/no** votes → unanimous-yes meals kept → repeat until targets met.
- **No dice roll. No "not tonight" / vote shades. No import feature or import UI.** The library is pre-seeded from `seed/meals.json`.
- Meals have title, type (lunch/dinner/both), category, tags, recipe (link/text). `times_kept`/`last_kept_at` are the favorites signal.
- **Deployment is VPS-hosted** (Charlie's Hostinger VPS, behind HTTPS via Caddy) — the app is internet-facing; no LAN/local-only assumptions. Deployment specifics: plan §7.1. Env: `DD_SECRET`, `DD_ACCESS_KEY` (household access gate, once per device), `DD_DB_PATH`, `DD_PORT`.

## Non-negotiables

1. **Green or honest**: run `uv run ruff check .` and `uv run pytest -q` before claiming done. Both must be green. If something is red or doesn't work, **report it** — a false "all green" is the worst possible outcome, worse than a failing test.
2. **TDD for logic**: session_logic (batch assembly, unanimity over the frozen roster, over-target resolution, track progression, **idempotent transitions**), session-code generation, seed loading — tests first, code to pass.
3. **Never auto-delete data.** Archive/reversible only. People are **deactivated, never deleted** (no DELETE endpoint for people). The seed loader dedupes and logs; it never mutates the spreadsheet or the committed seed JSON.
4. **Vote privacy is security** (strong invariant): individual votes are **never exposed in the normal UI, before or after batch closure** — clients see only aggregate outcomes. This is the one invariant that gets you pulled from a slice.
5. **Schema changes ship as Alembic migrations** (D15) — `create_all` is dev/test only. **PINs are stored hashed** (PBKDF2, per-person salt) — no plaintext PINs anywhere.
6. **The app is public on the internet** — nothing user-visible may leak secrets (no secrets in HTML/JS, no debug output in prod, no client-side credentials); secure cookie flags (`Secure`, `HttpOnly`, `SameSite`) and origin/CSRF checks on every state-changing request; admin-only routes enforced server-side (`is_admin`).
7. **State transitions are idempotent** — double-submit close/keep/next/finish must apply exactly once.
8. **One slice, one commit**, conventional messages (`feat:`, `fix:`, `test:`, `chore:`).
9. Follow the lead's delegation contract exactly: stated files, do-NOT list, verification commands with expected outputs, honest-failure escape hatch.

## Files you own / never touch

- **Own**: `app/`, `tests/`, `scripts/` (seed.py, build_seed.py), `alembic/`, `pyproject.toml`, `.github/`, deployment files (Dockerfile / compose / Caddyfile when they land in M5).
- **Never touch**: `CHARTER.md`, `ROADMAP.md`, `docs/` (PLAN-v1-mvp.md, POST-V1.md, ORIGINAL-CONCEPT.md, INITIAL-PLAN-REVIEW.md, DEVLOG.md), `REQUESTS.md`, `CLAUDE.md`, `reference/` (read-only source data), `seed/meals.json` (lead-owned data — regenerate via `scripts/build_seed.py`, never hand-edit).
- Commit messages and branch hygiene are the lead's job. Don't push; the lead lands slices.

## Reporting format (after every slice)

```
Slice: <id>
Changed: <files>
Tests: <count passed/failed> — commands run, paste real output lines
Verification: <exact commands + outputs>
Honest notes: <anything that didn't work / is uncertain>
```
