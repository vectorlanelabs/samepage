# Same Page — Implementer Constraints (CLAUDE.md)

> **⚠ Pivot in progress (2026-08-28):** renamed from Dinner Decider. `docs/PLAN-v2-samepage.md` is now the
> binding spec — it supersedes this file's and `docs/PLAN-v1-mvp.md`'s identity (D2) and meal-specific
> (D10) decisions. M3 onward is unapproved until that doc is signed off. (This file swept 2026-08-29 to
> match the M2a/M2b code and the plan's locked decisions — the stale PIN/`is_admin`/global-API-key lines
> are gone; if you find a contradiction between this file and the plan, the plan wins and the
> contradiction is a bug worth reporting in your slice notes.)

**Read first, in order:** `docs/PLAN-v2-samepage.md` (current plan — binding spec) → `docs/PLAN-v1-mvp.md` (superseded, historical) → `CHARTER.md` (scope & non-goals, partially superseded — see its own banner). These files are the contract. When in doubt, the plan wins over guesswork; when the plan is silent, ask — never invent product decisions.

## Stack (locked — do not change without Charlie's word)

- Python 3.12+, **uv** for env/deps, **FastAPI**, **SQLAlchemy 2.x**, **SQLite**, **Jinja2**, **HTMX** + minimal vanilla JS, **MCP (FastMCP)** for the external AI-tool surface (D17).
- **No frontend build step. No Node.** No new runtime dependencies without lead approval (note it in REQUESTS.md instead). openpyxl is a **dev-only** dependency (seed regeneration).

## Product shape (binding)

The app exists to replace ad-hoc negotiation with private group voting — it was never built around a randomized pick, and nothing about that mechanic (including its data provenance) belongs in this product going forward.

- **No in-app AI, ever.** The app will expose a token-authenticated JSON API + MCP server at M6 — **per-group tokens, generated/revoked by each group's owner, stored hashed; never one shared global key** (plan §8 M6). Recipe parsing, discovery, and trend analysis happen in Charlie's AI tools (D17). **No LLM keys in this codebase.**

- The product is a **multi-tenant consensus-voting platform**: groups own collections of items (Meal Planner is the first kind) and host voting sessions against them — iterative batches → private **binary yes/no** votes → **unanimous-yes kept automatically; majority-yes (yes > no, ties excluded) offered to the host to accept**. Full shape, schema, and session/batch state machines: plan §2, §5, §5.5–§5.6.
- Majority acceptance is a **host-only** action at batch results, shown with aggregate counts only (never who voted which way).
- **Mobile-first (plan §9)**: voters and hosts are on phones. M3+ screens are phone-first (voting is one option at a time); no SPA — server-rendered Jinja + htmx/SSE; PWA packaging at M5.
- **No "not tonight" / vote shades. No import feature or import UI.** The library is pre-seeded from `seed/meals.json`.
- Meals (item + `meal_detail`) have name, type (lunch/dinner/both), category, tags, recipe (link/text). `times_kept`/`last_kept_at` are the favorites signal.
- **Deployment is VPS-hosted** (Charlie's Hostinger VPS, behind HTTPS via Caddy) — the app is internet-facing; no LAN/local-only assumptions. Env: `SP_SECRET`, `SP_DB_PATH`, `SP_PORT`. No site-wide access gate — real accounts (M2a) are the security boundary (decided 2026-08-29, see REQUESTS.md).

## Non-negotiables

1. **Green or honest**: run `uv run ruff check .` and `uv run pytest -q` before claiming done. Both must be green. If something is red or doesn't work, **report it** — a false "all green" is the worst possible outcome, worse than a failing test.
2. **TDD for logic**: session_logic (batch assembly, unanimity over the frozen roster, over-target resolution, track progression, **idempotent transitions**), session-code generation, seed loading — tests first, code to pass.
3. **Never auto-delete data.** Archive/reversible only. People are **deactivated, never deleted** (no DELETE endpoint for people). The seed loader dedupes and logs; it never mutates the spreadsheet or the committed seed JSON.
4. **Vote privacy is security** (strong invariant): individual votes are **never exposed in the normal UI, before or after batch closure** — clients see only aggregate outcomes. This is the one invariant that gets you pulled from a slice.
5. **Schema changes ship as Alembic migrations** (D15) — `create_all` is dev/test only. **All credentials are stored hashed** (account passwords today: PBKDF2, per-account salt; M6's per-group API tokens the same way) — no plaintext credential anywhere.
6. **The app is public on the internet** — nothing user-visible may leak secrets (no secrets in HTML/JS, no debug output in prod, no client-side credentials); secure cookie flags (`Secure`, `HttpOnly`, `SameSite`) and origin/CSRF checks on every state-changing request; group-scoped routes enforced server-side via the existing guards (`require_account`, `require_group_admin`, `_get_owned_item_or_404`-style ownership helpers) — **404, never 403, for another tenant's or a nonexistent resource** (no existence oracles), and **every tenant-owned route ships with a cross-tenant negative test**. API/MCP (M6) auth is per-group tokens; responses are **aggregate-only — never raw per-person votes**. No LLM keys anywhere in this repo.
7. **State transitions are idempotent** — double-submit close/keep/next/finish must apply exactly once.
8. **One slice, one commit**, conventional messages (`feat:`, `fix:`, `test:`, `chore:`).
9. Follow the lead's delegation contract exactly: stated files, do-NOT list, verification commands with expected outputs, honest-failure escape hatch.
10. **NEVER create, push, or retry a CI workflow.** CI is out-of-scope for this project and is NOT owned by the implementer or the dev-loop. Do not add, modify, or push any `.github/workflows/` file, do not enable Actions, and do not push extra commits to retry a CI failure. CI does not start until Charlie specifies a hosting/deploy target and explicitly approves it. If anything references CI, flag it in REQUESTS.md and move on — never chase a green CI. (Charlie's GitHub is a free account; retrying failed CI burns Actions minutes and risks locking him out.)

## Files you own / never touch

- **Own**: `app/` (incl. `api.py`, `mcp.py`), `tests/`, `scripts/` (seed.py, build_seed.py), `alembic/`, `pyproject.toml`, deployment files (Dockerfile / compose / Caddyfile when they land in M5). **Note: `.github/` is NOT owned — CI/workflows are out-of-scope (see Non-negotiables #10). Do not create or edit any `.github/` content.**
- **Never touch**: `CHARTER.md`, `ROADMAP.md`, `docs/` (PLAN-v1-mvp.md, POST-V1.md, ORIGINAL-CONCEPT.md, INITIAL-PLAN-REVIEW.md, DEVLOG.md), `REQUESTS.md`, `CLAUDE.md`, `.github/`, `reference/` (read-only source data), `seed/meals.json` (lead-owned data — regenerate via `scripts/build_seed.py`, never hand-edit).
- Commit messages and branch hygiene are the lead's job. Don't push; the lead lands slices.

## Reporting format (after every slice)

```
Slice: <id>
Changed: <files>
Tests: <count passed/failed> — commands run, paste real output lines
Verification: <exact commands + outputs>
Honest notes: <anything that didn't work / is uncertain>
```
