# Dev Log

Chronological record of work on Dinner Decider. Oldest at top.

## 2026-08-26 — Plan 1 (day 0)

- **Read** the repo: `README.md` (product concept — replace the D8/D20 spreadsheet-and-dice ritual, which "narrows the list but does not really solve the decision problem", with consensus voting) and `D20 Dinner Decider.xlsx` (the legacy data).
- **Audited the spreadsheet**: 8 tabs × up to 20 meals (~155 named meals); 4 recipe URLs (2 standalone cells, 2 embedded in meal names); 10 takeout entries; one exact duplicate ("Chicken parm" ×2); Sheet8 has 15 of 20 slots; `Times Rolled` column noted and deliberately ignored.
- **Scope refined with Charlie** (day-0 planning, not iterations): weekly planning sessions — set lunch/dinner targets; iterative 15-meal yes/no batches (same list for everyone, private votes); unanimous-yes meals kept until targets met. Binary votes. No dice (the thing being replaced). Grocery list out of scope. Library pre-seeded (no import feature). Kept-meal records (`times_kept`) seed favorites. Tags/categories as AI hooks. Recipes arrive via a future AI step (photo/link → recipe).
- **Architecture decided**: backend (FastAPI + SQLite), **VPS-hosted** on Charlie's Hostinger VPS behind HTTPS; single household passphrase as the access gate; daily DB backups — the library is the family recipe keeper (replacing the kitchen notebook).
- **Produced**: `CHARTER.md` (pending approval), `ROADMAP.md`, `docs/PLAN-v1-mvp.md`, `docs/POST-V1.md`, `CLAUDE.md`, `REQUESTS.md`, `seed/meals.json` (155 meals) + `seed/README.md`, `reference/README.md`; README gained a pointer to the operative docs.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Initial plan review applied

- **Read** `docs/INITIAL-PLAN-REVIEW.md` (12 findings: 6 required, 3 doc cleanup, 3 recommended). **All 12 accepted** and applied to the docs.
- **Substantive changes**: lobby/roster-freeze phase (late join disallowed; unanimity = explicit yes from every roster member); Alembic migrations from M0; WAL-safe backups (`VACUUM INTO` / backup API) with restore verification in M5; curated 27-meal `both` seed subset so the lunch track is populated (review option A); `Person.is_admin` + hashed PINs (PBKDF2) + secure cookies/origin checks + deactivate-not-delete; strengthened privacy invariant (individual votes never exposed in the normal UI, before or after close); batch size fixed at 15; idempotent session transitions; recipe-use experience (cooking view, printing) attached to v2 intake; README rewritten for the real product, original concept moved to `docs/ORIGINAL-CONCEPT.md`; post-v1 deployment wording corrected (v1 is already VPS-hosted).
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Majority-vote host acceptance (Charlie's change)

- **Change**: unanimous-yes meals stay auto-kept, but **majority-yes meals (non-unanimous, `yes > no`, ties excluded) are now shown in the batch results with aggregate counts** — everyone sees them, and the **host (session starter) may accept** them while slots remain.
- **Locked mechanics**: unanimous auto-kept first, majority offered after (capped by remaining slots; over-target resolves unanimous first); accepted majority meals recorded as `kept_by='host'` and count toward targets + `times_kept`; **privacy invariant unchanged** — aggregate counts only, individual votes never exposed; 2-person rosters have no majority (feature engages with 3+ voters).
- **Docs updated**: CHARTER (core use case, mechanic, D5/D9/D13, DoD), PLAN (header, D5/D9/D13, US5/US10, `batch_meal.kept_by`, §9.4–9.6, routes, tests, risks, open questions, M3), README, ROADMAP, CLAUDE.md, REQUESTS.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — AI lives outside the app (Charlie, with Claude Design)

- **Decision (D17)**: Dinner Decider never runs AI. It exposes a **token-authenticated JSON API (`/api/v1`, Bearer `DD_API_KEY`) + FastMCP server** (same auth) so Charlie's AI tools (ChatGPT/Claude/Hermes) can import meals/recipes and run discovery/trend analysis via MCP. No LLM keys, no in-app AI, now or later — eliminates the entire in-app AI build.
- **New milestone M6 — External API & MCP** (part of v1, not M0): meals/taxonomy CRUD, sessions/stats (aggregate-only — no raw per-person votes in any API response), MCP tools over `/mcp`.
- **Seeded recipe links**: default is **Option B** — leave the seed as-is; the 4 linked recipes become the first real MCP imports at M6, proving the path end-to-end. Option A (parse at seed time) available.
- **Docs updated**: CHARTER (mechanic, non-goals, D17, M6, DoD), PLAN (header, scope, D17, layout, §7.1, §8.1 API surface, M6, tests, risks, open questions), POST-V1 (v2 rewritten as external intelligence; recipe-use UI moved to v1.5), ROADMAP, README, CLAUDE.md, REQUESTS.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Charter approved; M0 cycle 1 starts

- Charlie **fully approved the charter** and stepped away; the autonomous dev loop is now running. No further questions will be asked — REQUESTS.md is the only channel.
- **Design handoff ingested** (`Design Handoff/`): high-fidelity reference (10 screens, all v1 views) + `Dinner Decider.dc.html` prototype + design tokens (Fredoka/Nunito Sans, oklch palette: purple primary 300, terracotta dinner 25, green lunch 140; radii 999/24/16/12; shadows; desktop-first responsive with breakpoints; sidebar → top bar below 900px). Production = FastAPI+Jinja2+HTMX recreation; the prototype's client-side state is NOT copied. Fidelity: colors/type/spacing/copy final.
- **M0 scope locked** (plan §11): pyproject/uv scaffold, settings (DD_DB_PATH/SECRET/ACCESS_KEY/API_KEY/PORT/ENV), full §6 models, Alembic initial migration, FastAPI skeleton + session/origin-check middleware, design-system base template + home screen, CI. Design system rides in T0.4 (base template + static).
- **Safety net scheduled**: hourly resume-the-loop cron (repo is the memory; TUI delivery is local-only).
- **Status**: M0 dispatched to implementer (deepseek-v4-flash). Next: independent verify → adversarial review (strong-model override) → land.

## 2026-08-26 — M0 landed (cycle 1 complete)

**Shipped** (`0a786dc`, one slice): uv/uv.lock project, `app/` (settings, db, models — all 9 §6 tables, security middleware, main, routes/home), design-system shell (sidebar/topbar, exact handoff tokens, home screen with live counts), Alembic 0001, vendored HTMX, 22 tests, CI.

**Process**: implementer (deepseek-v4-flash) → lead re-verified everything (14→22 tests, live smoke, WAL/FK, revert-and-run spot check on the origin middleware — test fails when middleware disabled) → Oscar review on gpt-5.6-luna (BLOCKING, 5 findings, all live-reproduced) → fix slice 1 → re-review (MAJOR, 2 remaining) → fix slice 2 → landed.

**Full findings disposition (nothing left behind):**
| Finding | Sev | Disposition |
|---|---|---|
| Fresh boot didn't create DB (home 500) | blocking | **fixed** — lifespan runs `alembic upgrade head`, fail-fast; live 200 + DB exists; `test_fresh_boot` |
| Origin check failed open (null/malformed/non-http) | major | **fixed** — fail-closed (403 on null/ftp/malformed; absent allowed by design, documented); live 403s; probe-app tests w/ mutation asserts |
| `data/secret.key` world-readable (0644) | major | **fixed** — created 0600 (O_EXCL), chmod self-heal on load; live `stat` 600 |
| Migration-created DB 0644 until first engine connect (re-review) | major | **fixed** — `_run_migrations` chmods target 0600 post-upgrade (log-only on failure); regression assert |
| Enum fields unconstrained | minor | **fixed** — 6 CHECK constraints in models + amended (uncommitted) 0001; raw-insert IntegrityError test |
| Origin "matching" test vacuous (405, no mutation) | minor | **fixed** — probe app with real POST /probe + mutation-recorded assertions (6 cases) |
| Existing `data/` dir not tightened (755) (re-review) | minor | **fixed** — `_ensure_private_dir` helper (mkdir 0700 + chmod existing 0700); tests |
| Raw sqlite3 connections don't enforce FK | — | **rejected** — standard SQLite semantics; the app's supported path enforces FK+WAL on every app connection |
| `itsdangerous` dep added beyond M0 spec | — | **accepted** (lead) — required by Starlette SessionMiddleware (unconditional import); transparently commented |
| StarletteDeprecationWarning (httpx→httpx2) | nit | **deferred** — cosmetic; revisit when fastapi/httpx move |
| Third Oscar pass on final perms micro-slice | — | **conscious skip** (logged) — lead-verified live + direct mode-assert regression tests; same finding class already reviewed |

**CI note**: workflow registered/active but the commit that adds a workflow file doesn't trigger it (GitHub quirk) — the run fires on the next push; verifying on the state-file push.

**Next**: M1 — household profiles (hashed PINs, admin flag, deactivate-not-delete, people UI per handoff screen 10).

## 2026-08-26 — M1 landed (cycle 2 complete)

**Shipped** (`e8a83d2`, one slice): `app/pins.py` (PBKDF2-SHA256 200k, per-person salt, strict parse, constant-time compare), `app/auth.py` (session identity, require_admin/require_any, inactive sessions die instantly), login/logout + `/me`, people CRUD (admin-only, first-person auto-admin bootstrap, deactivate-not-delete, self-protection), People page per handoff screen 10 (hue avatars, ★ Admin toggle, add form), Alembic 0002 (failed_pin_attempts, locked_until), 58 tests.

**Process**: implementer → lead verify (48 tests, live smoke of full auth flow incl. lockout) → Oscar on gpt-5.6-luna (**BLOCKING**, 3 findings, all live-reproduced) → fix slice (atomic SQL lockout, serialized bootstrap, fail-closed Origin) → re-review (**MINOR**, all 3 closed, 1 new minor) → micro-fix (/mcp boundary + barrier tests) → landed.

**Findings disposition (nothing left behind):**
| Finding | Sev | Disposition |
|---|---|---|
| Concurrent wrong-PIN logins bypass lockout (10 guesses → counter 1) | blocking | **fixed** — atomic `UPDATE ... +1` + same-transaction read-back + concurrent-lock reset; live: 10 concurrent → locked, counter 0; barrier-synchronized regression test |
| First-person bootstrap race → 2 admins | major | **fixed** — `threading.Lock` around count→insert→commit; live: 2 concurrent → [303,403], one admin; barrier test |
| Absent Origin trusted on state-changing routes (login CSRF) | major | **fixed** — fail-closed: mutating requests require same-origin Origin; absent → 403 except `/api/`, `/mcp`, `/mcp/` (token surfaces, M6); login-CSRF test |
| `/mcp` exemption matched `/mcpfoo` (re-review) | minor | **fixed** — exact boundary `== "/mcp" or startswith("/mcp/")`; probe tests |
| Concurrency tests could serialize vacuously (re-review) | minor | **fixed** — `threading.Barrier` synchronization; 5x reruns stable, no flakes |
| Multi-worker deployment needs a DB-level bootstrap guard | — | **deferred** — documented in code; tracked in REQUESTS (deployment is single-process uvicorn) |
| Unauthenticated `/people` returns bare 403 (no redirect to /login) | nit | **deferred** — UX polish; tracked in REQUESTS |

**CI**: removed 2026-08-26 per Charlie (error emails on every commit; will re-enable when a hosting environment exists). Runs had been failing GitHub-side (~12s, zero steps, logs 404) with no determined cause — local gates are the verification. Tracked in REQUESTS.

**Next**: M2 — meal library CRUD + pre-seeded data (seed loader from `seed/meals.json`, library screen per handoff screen 6/7).

## 2026-08-26 — M2 landed (cycle 3 complete)

**Shipped** (`6d22054`): seed loader, browse/search/filter, CRUD, recipe view. 85 tests passing. Not yet
devlog'd in detail before the pivot below — see git log for the slice.

## 2026-08-28 — Local validation, then a real architecture pivot

Charlie cloned M0–M2 for local testing (this session, as primary agent going forward — the autonomous
loop that ran M0–M2 had stopped for review, not still running). `uv sync` → `alembic upgrade head` →
`scripts/seed.py` → 85 tests green, `ruff` clean, manual browser walkthrough of home/library/people/login
all confirmed working. One real gap found: `GET /people` requires an existing admin even on a fresh
install, but the bootstrap-first-admin logic lives in `POST /people` — no UI path exists to create the
first person. Logged for a future fix; worked around via direct POST for this session's testing.

**Then a genuine scope conversation, not a testing note.** Walking through what M3 (voting) would need
surfaced that the consensus mechanic (batch of options → private yes/no → unanimous-keep, host-may-accept-
majority) has nothing to do with meals specifically, and Charlie wants this to become **SamePage** — a
multi-tenant platform any family/friend group can host, with meal planning (**Meal Planner**) as the first
of several collections (things to do, games, date-night options, ...).

**Design conversation landed on:**
- **Single shared multi-tenant deployment**, not per-family self-hosted + federation — avoids a real
  distributed-identity problem since federation between independent instances was the hard alternative.
- **Real accounts, but only for group owners/admins.** Regular participants need zero credentials — PINs
  are gone entirely, not just loosened. A logged-in account only pre-fills a display name when voting;
  it's never a gate to join or vote.
- **Groups have an owner (one, transferable) + any number of admins**, who together manage that group's
  collections, sessions, and reports.
- **Sessions don't require group membership to join** — a link/code is enough, logged in or not, and this
  is also how cross-group invites work (no federation needed, since everyone's account lives in the same
  system).
- **Vote outcomes are recorded, voters are not.** `batch_item` becomes the durable record — per-item
  outcome + aggregate yes/no counts, no `person_id`, ever. This is what "was this meal rejected because of
  a `fish` tag" reporting reads from later. In-batch per-participant response tracking still exists (to
  detect "has everyone responded") but is explicitly ephemeral/operational, not history.
- **Voting sessions don't require a backing collection** — ad hoc, never-persisted options are first-class
  (`batch_item.ad_hoc_label`), covering "what bar tonight" without any database involved.
- **Pre-reveal ad hoc option submission** (everyone adds options before the batch is revealed; host may
  promote one into the permanent collection) — logged as backlog, schema already accommodates it, not
  blocking anything above.

**Produced**: `docs/PLAN-v2-samepage.md` (full v2 architecture — supersedes `CHARTER.md`'s identity/D10
decisions and `docs/PLAN-v1-mvp.md`'s M3–M6); `ROADMAP.md` and `CHARTER.md` updated with pivot banners and
a revised milestone table (M0 stands, M1→**M2a** identity/tenancy, M2→**M2b** generic collections, M3
unapproved until the v2 doc is signed off). Product/repo/module renamed **SamePage** / **Meal Planner**
(was Dinner Decider) — code-level rename (env var prefix `DD_*`→`SP_*`, package name, branding strings)
done alongside the docs; **GitHub repo rename intentionally left for an explicit go-ahead** (changes a
public URL).

**Status**: M0–M2 code stands as the starting point for M2a/M2b, not thrown away. M3 onward unapproved
pending Charlie's sign-off on `docs/PLAN-v2-samepage.md`. No implementation work started against the new
architecture yet — this was a spec/design pass only.
