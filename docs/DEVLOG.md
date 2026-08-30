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

## 2026-08-28 — M2a landed (identity & tenancy)

**Shipped**: `Account` (email+password, PBKDF2-SHA256 600k iterations, stdlib-only — matches the existing
PIN-hashing pattern, just a higher work factor), `Group` (`owner_account_id`), `GroupAdmin` (additional
admins beyond the owner). `Person`, PIN hashing/lockout, and the never-built M3-shaped `Session`/
`SessionParticipant`/`Batch`/`BatchMeal`/`Vote` tables are all removed (the latter were empty, unused,
superseded by `docs/PLAN-v2-samepage.md` §5's session model — M3 recreates them when it starts).
`app/routes/groups.py` replaces `app/routes/people.py`: create a group, view members, owner adds/removes
admins by email. Signup is always open (no admin bootstrap gate — anyone can create an account, then
create a group and become its owner) — this directly fixes the real bug found during manual M0–M2 testing
last session (no UI path existed to create the first person). 88 tests passing, `ruff` clean.

**Process**: implementer (Haiku) → lead re-verify (venv had gone stale after the folder rename to
`samepage-app` — shebangs pointed at the old path; `rm -rf .venv && uv sync` fixed it) → **caught a real
architecture violation the implementer invented and never flagged as a decision**: an ungated
`Account.is_admin` boolean, defaulting `False`, that nothing in the app ever set to `True` — every real
signed-up account would have been permanently locked out of library editing forever. Tests only passed
because the test helper set `is_admin=True` directly via the ORM, bypassing the app entirely. Sent back
with a locked decision (library CRUD gates on "any signed-in account" for this slice — deliberate, interim,
tracked in REQUESTS.md — proper group-scoping is M2b's job) → re-verify (clean) → Oscar review → **1
blocking finding, live-reproduced**: `GET /login`/`GET /signup` 500'd for any already-authenticated visitor
(`get_current_account(request, None)` — passed `db=None`, a bug in code that didn't exist before this
slice) → lead fixed directly (pass the real `Depends(get_db)` session) + added 2 regression tests → landed.

**Findings disposition (nothing left behind):**

| Finding | Sev | Disposition |
|---|---|---|
| `Account.is_admin` — ungated, nothing ever sets it True, permanently locks out every real user | blocking | **fixed** — removed the field entirely; library CRUD now gates on `require_account` (any signed-in account), a deliberate interim policy until M2b group-scopes collections; live-verified (anon 401, signed-in 303) |
| `is_group_admin` mid-function import + SQLAlchemy 1.x `.query().filter_by()` style | minor | **fixed** — top-level import, rewritten to 2.x `select()` style matching the rest of the codebase |
| `GET /login`/`GET /signup` 500 for an already-signed-in visitor (`db=None` passed to `get_current_account`) | blocking | **fixed** — real `Session` dependency wired in; live-reproduced before (500) and after (303) the fix; 2 regression tests added |
| Login timing side-channel: unknown email returns instantly, known email always runs the 600k-iteration hash (~60ms vs ~1.4ms, live-measured) | major | **deferred, tracked** — inherited from the M1 PIN-login code this replaced (same early-return shape), not introduced by this slice; real and worth fixing before public launch — REQUESTS.md |
| `add_admin` route rebuilt the same template-context dict 3× (copy-paste) | nit | **fixed** — extracted `_group_detail_context()` helper |
| Home page stat card labeled "Accounts" but linked to `/groups` and showed account count, not group count | minor | **fixed** — relabeled "Groups", now counts `Group` rows |

**Next**: M2b — generic collections & items (`Collection`/`Item`/`meal_detail`, scoped `Category`/`Tag`,
migrate the 155 seeded meals).

## 2026-08-28 — M2b landed (generic collections & items)

**Shipped**: `Collection` (`group_id`, `kind`, `name`), `Item` (replaces `Meal` — adds `times_offered`
alongside `times_kept`/`last_kept_at`), `ItemTag` (replaces `MealTag`), `MealDetail` (1:1 extension:
`type`/`ingredients`/`recipe_text`/`source_url` — the meal-specific fields, so a future collection kind
gets its own `*_detail` table the same way). `Category` is now scoped to a collection
(`UNIQUE(collection_id, name)`), `Tag` to a group (`UNIQUE(group_id, name)`) — same name can exist in two
different collections/groups without colliding. Clean-slate migration (matches M2a's precedent — no real
user data existed to preserve). `scripts/seed.py` now requires a `group_id` argument, idempotently
get-or-creates one `Collection(kind="meal")` for that group, and loads the 155 seeded meals into it —
still dedupes by `normalized_name`, still never mutates `seed/meals.json`. `/library`'s URLs and behavior
are unchanged from the outside; underneath, it resolves "the" meal-kind collection (there's exactly one in
practice) rather than a hardcoded `Meal` table — real multi-collection routing (`/collections/{id}/...`)
is deferred until a second collection kind actually exists (tracked in REQUESTS.md, not built
speculatively). 91 tests passing, `ruff` clean.

**Process**: implementer (Haiku) → lead re-verify (migration/lint/tests all green independently) → full
live smoke test by the lead (not just automated tests): fresh signup → create group → run
`uv run python -m scripts.seed <group_id>` → confirmed `/library` actually shows the 155 seeded meals
(not just that a test fixture claims it does) → re-ran the seed script to confirm idempotency (0 new
rows) → verified the "no collection yet" path on a truly fresh DB renders an empty state (200) and refuses
creates with a clear 400, not a 500 → verified `alembic downgrade`/`upgrade` round-trips cleanly. Read the
full diff line by line (this project's own prior slice found a real invented-flag bug that automated tests
alone missed) — no equivalent issue found this time. Oscar-style review pass: no findings.

**Findings disposition**: none this slice — implementation matched spec, no invented fields/flags, no
crash paths found on the "already logged in" or "missing collection" edge cases that were specifically
checked for after M2a's review caught similar issues.

**Status**: M2a and M2b both landed. Per Charlie's instruction, execution stops here — **M3 (session-based
voting) is not started.** It remains unapproved pending sign-off on `docs/PLAN-v2-samepage.md`.

## 2026-08-29 — M3–M6 reviewed against what M2a/M2b actually built; REQUESTS.md pruned

Charlie asked for two things: review M3–M6 now that the account/group/collection model is real (not just
spec'd), and clean out `REQUESTS.md` — most of it was either already decided by how the code turned out,
or made obsolete by the pivot, and didn't need to sit there as open questions.

**Plan changes** (`docs/PLAN-v2-samepage.md`):
- **M4 (reporting)**: added a hard requirement that didn't exist in the single-household design — every
  reporting query must filter through `collection.group_id` to groups the requesting account belongs to.
  Without it, one group's reject rates and meal history leak to another group on the same deployment. Not
  optional, not a nice-to-have.
- **New §6.1**: made explicit that this is one shared SQLite database across every group, not
  database-per-tenant — isolation is enforced at the application layer via `group_id`, not by storage.
  This was implicit in the schema but never stated as a decision.
- **M6 (API/MCP)**: locked a change the old milestone table only flagged as "resolve later" — tokens are
  per-group, not one shared household key. A single global key would let one group's AI tools read every
  other group's data on the same deployment now that other people's groups actually live here. Each
  group's owner generates and can revoke their own group's token.
- **M5 (deployment)**: surfaced a real open question rather than resolving it unilaterally — does the old
  `DD_ACCESS_KEY`-style site-wide passphrase still make sense now that real accounts exist and the
  platform is meant to let other groups self-serve sign up? A blanket site gate works against exactly that
  flow. Tracked in `REQUESTS.md`, needs Charlie's call before M5 builds the deployment story around it.
- M3 itself needed no changes — its design already accounted for account-optional, cross-group session
  participation.

**REQUESTS.md pruned** from 19 mixed items down to 3 that actually need Charlie's judgment (the access-gate
question above, the lunch `both` subset — household taste, only Charlie can judge — and the optional dice
ritual). Everything else got a real disposition instead of sitting as an open question:
- 5 items were **obsolete** — referred to code that no longer exists (`Person`, `_bootstrap_lock`, `/people`,
  the single-household `DD_API_KEY`) and made no sense to ask about anymore.
- 6 items were **already decided** by repeated, uncontested use through the whole design process (track
  order, over-target keeps, majority rule, recipe display, raw-votes-via-API, the M6 recipe-link approach)
  — re-asking would just be busywork.
- 4 items were **real engineering follow-ups with no product judgment required** (the login timing
  side-channel, interim library CRUD gating, single-collection routing, bare-401-instead-of-redirect) —
  moved to their own section instead of the general request queue, since nobody needs to decide anything,
  they just need doing eventually.

**Status**: M3 remains unapproved and unbuilt. The one real open question before it starts is the
access-gate call above — everything else in the plan review is either already locked or doesn't block
starting M3.

## 2026-08-29 — Three decisions from Charlie; dice mechanic permanently retired

Charlie answered the three open items from the plan review, and gave a hard directive on a fourth thing
that had never actually been asked as a question: purge every trace of the dice mechanic from the live
repo. It came up repeatedly (a "dice ritual, resurrected" backlog stub, `Category.legacy_sheet_index`
tracking a meal's position on the old spreadsheet, "D8/D20" framing in copy) despite Charlie never having
asked for any of it to be preserved — leftover from the original DeepSeek-run cycles that started this
project, not a real product direction.

**Decisions:**
1. **Access gate: accounts.** No site-wide passphrase. Real accounts are the security boundary.
   `Settings.access_key`/`SP_ACCESS_KEY` removed outright — it was dead code, never enforced by any
   middleware (the M5 gate-middleware task was never built), so this was a clean deletion, not a
   migration. `docs/PLAN-v2-samepage.md`'s M5 row updated from "open question" to "locked."
2. **Lunch `both` subset**: moot. This seed data gets replaced entirely; not worth curating something
   going away.
3. **Dice mechanic: gone, permanently, not a backlog item.** Swept every live/operative doc:
   - `docs/POST-V1.md` — deleted the "dice ritual, resurrected" backlog stub outright (its own footer
     says exactly the right thing: "if an item stops making sense, it gets deleted").
   - `ROADMAP.md` — removed "dice-ritual resurrection" from the Post-MVP "later" list (also caught it
     listing multi-household+accounts as still "later" — they landed in M2a/M2b, fixed while there).
   - `CLAUDE.md` — reworded the product-shape framing off "replace the dice ritual" language; dropped the
     "No dice roll" non-goal line (redundant once the mechanic doesn't exist at all).
   - `docs/PLAN-v2-samepage.md` — reworded the "no dice ritual" non-goal without the word, same substance.
   - `README.md` — dropped the live link to `reference/D20 Dinner Decider.xlsx` from the Docs list; no
     reason to keep surfacing a dice-named file in front-door copy.
   - `REQUESTS.md` — deleted the "Dice ritual (optional, someday)" item outright rather than resolving it
     with an explanation; added a real engineering follow-up instead (`Category.legacy_sheet_index` —
     literally "position on the old dice spreadsheet" as a persisted column — gets dropped in a real
     migration next time the seed pipeline is touched, not urgent standalone).
   - `CHARTER.md` — left as historical record (it's already banner-marked superseded, matching how
     `docs/PLAN-v1-mvp.md` and `docs/ORIGINAL-CONCEPT.md` are treated), but added an explicit note to its
     banner: the dice/D8/D20 framing in its body is historical only, not a live description of the
     product, and not coming back.
   - **Not touched**: `docs/DEVLOG.md` (this file — a chronological log shouldn't be rewritten to erase
     what actually happened), `docs/ORIGINAL-CONCEPT.md` and `docs/PLAN-v1-mvp.md` (both explicitly
     archival), `reference/D20 Dinner Decider.xlsx` and `reference/README.md` (the actual legacy source
     file and its provenance doc — left in place as a dormant, unreferenced archive rather than deleted,
     since deleting source data is a more consequential call than editing prose; flagged to Charlie in
     case he wants it gone too, not assumed).

**Status**: All three plan-review items resolved. `REQUESTS.md`'s "needs Charlie's judgment" section is
now empty. Next: a Fable-run Oscar review of the updated plan before M3 execution starts.

---

## 2026-08-29 — Oscar reviews dispositioned; mobile-first locked; lead handoff to Fable orchestration

Charlie handed the lead role to a Fable-orchestrated loop (autonomous-dev-loop + model-routing:
Fable leads, deepseek-v4-flash implements spec-locked slices, Sonnet runs Oscar reviews). Two locked
product decisions from Charlie this session: **mobile-first** (voters and hosts are on phones), and
SPA-vs-not delegated to the lead — **decided: no SPA**; server-rendered + htmx/SSE, PWA at M5,
one-option-at-a-time voting on mobile. All recorded in plan §9.

**Recovery note:** cycle start found correct, uncommitted fixes in the tree (code-review findings 1/2/4/5
plus tests; suite green at 105). Verified independently (diff read line-by-line, ruff + pytest re-run)
and landed as `8399219` rather than discarded — attribution: produced before this loop took over, not by
this loop's delegation.

**Plan-review dispositions** (`docs/OSCAR-REVIEW-plan-2026-08-29.md`):
blocking 1 (pseudo-SQL PKs) **fixed** — §5 rewritten: surrogate ids, partial unique indexes,
exactly-one-of CHECK, `batch_response` now references `batch_item.id` (also kills the ad-hoc
label-matching minor). blocking 2 (privacy claim unenforced) **fixed** — new §5.5 makes deletion at
batch close and participant deletion at session end M3 acceptance criteria; expiry defined (24h
inactivity, lazily enforced). blocking 3 (session tenancy invariants) **fixed** — stated in §5 as hard
requirements. major 4 (no rate limiting) **deferred, tracked** — promoted to M5 pre-deployment blockers
(plan §8 M5 + REQUESTS.md): login throttling, signup email-oracle decision, join-by-code limiting,
timing side-channel. major 5 (M4 scoping) **fixed** — dual join path, choke-point pattern, cross-tenant
negative tests as acceptance criteria. major 6 (§6.1 blast radius) **fixed** — owned explicitly with
standing mitigations. major 7 (M3 state machines) **fixed** — §5.6; D5/D6/D13 re-adopted by explicit
reference. major 8 (ghost participants) **fixed** — host participant removal in M3 scope; trust model
stated. major 9 (M6 gaps) **fixed** — hashed storage, rotation-on-transfer, verb scope (no session/vote
access for tokens), token-resolves-to-one-group; tool list deliberately left to M6 planning.
major 10 (doc contradictions) **fixed** — CLAUDE.md #5/#6/product-shape rewritten, CHARTER banner now
supersedes the raw-votes language, ROADMAP M5 row updated. Minors: §5.5 dangling refs **fixed** (section
exists); session-code surface **fixed** (§5.6 + M5); ad-hoc-needs-a-group **fixed** (honest caveat,
§5.2); `legacy_sheet_index` **already tracked**, unchanged. Nits: ROADMAP M0 "CI" mention **fixed**
(marked historical); `target_count > 0` CHECK **fixed**; `batch.seq` gapless-ness **rejected** — unique
per session is the only invariant anything needs; gaplessness buys nothing.

**Code-review dispositions** (`docs/OSCAR-REVIEW-code-2026-08-29.md`):
blocking 1 (library 500), blocking 2 (403-vs-404 oracle), major 4 (`_safe_next` backslash),
major 5 (cross-tenant mutation tests), major 6 (N+1 + platform-wide tag query) — all **fixed** in
`8399219`. major 3 (multi-group library dead end) **deferred to M2c, in progress** — collection-scoped
routing per plan §9, landing before M3. major 7 (dead schema) — split: `is_active` **fix queued**
(M2c slice: drop via migration; `archived_at` is the mechanism); `times_offered` **kept deliberately**
(M3 increments it at batch close; §6 reads it); `Item.description` **kept** (schema-intended, UI just
doesn't surface it yet); `Category` **kept** (categories are in the product design; surfaced at
reskin/M4). major 8 (`/logout` unreachable) **fix queued** (M2c). Minors — all **fix queued** for M2c:
odd-hex `verify_password`, group-create error context loss, 401 redirect dropping query string, signup
dropping `next`, owner-vs-admin error copy, case-sensitive ordering, seed within-run dedupe +
undercounted skips, PIN-era origin-check payloads, stale test_session docstring. Exception:
add_admin's email-existence disclosure to group owners **accepted as a decision** — invite-by-email
cannot function without it; recorded here so it's a choice, not an accident. Taste nits:
`dinnerdecider` logger + vestigial `can_edit`/`no_collection` + recipe_view ORM-grafting **fix queued**
(M2c); `--dd-*` CSS vars **deferred to the reskin slice** (renaming variables in a stylesheet the
design pass will replace is work done twice); vendored-but-unused htmx **rejected as an issue** —
retained deliberately, it's the no-SPA plan's mechanism (plan §9).

Also this entry: `docs/DESIGN-BRIEF-mobile.md` written — corrects the Design Handoff bundle's
desktop-first premise and its "plan v2 doesn't exist" claim before Claude Design sinks more work into
the wrong target. Visual/template work held for that pass.

**Addendum (same day):** Charlie corrected the brand: **"Same Page", with a space**, wherever a
human reads it; identifiers (`samepage-app`, `SP_*`, repo name) stay collapsed. Live docs swept; the
user-visible template/title strings go in the M2c implementation slice.

---

## 2026-08-29 — M2c part 1 landed: correctness punch list

Implementation: `deepseek-v4-flash` against a decision-locked spec, driven across four invocations (the
CLI caps at 25 tool rounds per run; `--continue` resumes with context intact — noted for future
slices: budget ~4 runs for a slice this size or slice smaller). Three residual failures were
root-caused and fixed by the lead, honestly noted: (1) the spec's own design flaw — the
`current_account` context processor opened `app.db.SessionLocal`, which points at the real DB, not the
test-overridden engine; redesigned to a session-only read (login/signup store `account_name`; no DB
hit per render); (2) two pre-existing 401-redirect tests asserted the unencoded `next` form the spec
deliberately replaced — expectations updated; (3) the seed file genuinely contains a duplicate
("Chicken parm" ×2) that the old loader inserted twice — with within-run dedupe the correct count is
154, not 155; tests updated with the reason inline.

Shipped: sign-out control + account indicator (both navs), "Same Page" brand in all UI strings,
401 redirects preserve query strings (urlencoded), signup preserves `?next=`, groups error page keeps
the group list (and missing-name is a friendly 400, not a 422), case-insensitive library ordering,
`verify_password` odd-hex guard, seed within-run dedupe + honest skip counts, migration 0006 drops
`item.is_active`, vestigial `can_edit`/`no_collection`/recipe-graft template plumbing removed.
Verification by the lead: `ruff` clean, `pytest -q` **113 passed** (up from 105), full diff read.

Oscar review (Sonnet, adversarial, live-reproduction rule): **ship**, one minor finding — phantom
account indicator on a stale session after out-of-band account deletion — **consciously deferred**,
tracked in REQUESTS.md (no deletion path exists; revisit with any account-removal slice). Probes with
no finding: XSS via `next`/display_name (autoescape confirmed), open-redirect suite incl. tab-byte
bypass (Starlette percent-encoding closes it), 401→login→post-login query-string round trip, migration
0006 up/down/up live, seed-dedupe test proven non-vacuous by mutation, logout under the origin check.

Remaining for M2c part 2: collection-scoped routing (`/collections/{id}`, plan §9).

---

## 2026-08-29 — M2c part 2 landed: collection-scoped routing. M2c complete.

The library moved to honest URLs: `/collections` hub (per-group sections, active counts),
`/collections/{id}` browse, item routes nested under their collection with a two-stage guard
(collection ownership 404-guarded, then item existence + membership in that exact collection),
`/library` reduced to a legacy 303. Creates now land in the URL's collection — the multi-group dead
end (code-review major #3: an account in two groups could never reach the second library, and creates
silently bound to the lowest collection id) is closed, with a regression test saying so by name.

Implementation: `deepseek-v4-flash`, two invocations plus one `--continue` fix round. Its completion
report was calibrated and honest (flagged its own two test deletions with reasons — both correct: the
deleted tests asserted behaviors this slice removes by design). Lead verification: full diff read,
`ruff` clean, `pytest -q` green throughout (113 → 127 tests).

Oscar review (Sonnet, adversarial): **approve**, and unusually strong receipts — it mutation-tested
the guards (dropped the collection-membership check in a scratch copy; the ported tests went red,
proving they're load-bearing), probed cross-group tag reuse, hub count edges, and the legacy
redirect for open-redirect surface. Findings, all dispositioned: (minor) hub grouped sections by
group *name*, merging same-named groups — **fixed** (implementer round: id-keyed grouping +
regression test). Lead follow-up on that fix: the ORDER BY still lacked `Group.id`, so two same-named
groups' collections could interleave and split a group into multiple sections — **fixed by the lead**
(one line + strengthened regression test, proven load-bearing by mutation: fails on the un-fixed
ordering, passes on the fix). (nit) `_get_meal_collection` filters `kind == "meal"` while the hub
shows all kinds — **rejected as a defect**: intentional asymmetry, documented in both docstrings
(the legacy redirect goes to a *meal* library; the hub is the generic surface).

M2c is complete. The mandate's steps 1 and 2 are done: spec + doc sweep landed, correctness punch
list landed, routing landed. Next up per ROADMAP: design round-1 (Charlie + Claude Design, kickoff
brief in docs/DESIGN-BRIEF-mobile.md), then M3 approval gate on the revised plan.

**Note (2026-08-29, Charlie):** retiring the old PNG wordmark was Charlie's own instruction to the
designer — the legacy logo was constraining directions he actually liked. The re-set CSS wordmark +
kept favicon mark in the Quiet Kitchen bundle is therefore a decision, not a deviation; the M2d
reskin implements it as spec'd.

---

## 2026-08-29 — Decision (Charlie): pure Google SSO, modular providers

Sign-in locked to Google OAuth only — no internal passwords to invent/store/secure. Modular provider
interface so Apple/others are later additions (Facebook ruled out); pure SSO, no password fallback;
recovery = manual ownership transfer, same escape hatch as before. Full spec in plan §4; new ROADMAP
row M5a (lands pre-deployment, after M3 — voting doesn't touch auth). Three of the four M5 security
blockers die with the password surface; join-by-code limiting survives.

---

## 2026-08-29 — M2d landed: Quiet Kitchen reskin

Every existing screen restyled to the delivered design: `app.css` rewritten from scratch on the
handoff's `--sp-*` tokens (light + OS dark), templates moved from inline-style walls to component
classes, CSS wordmark + glyph, favicon/PWA icon, Hanken Grotesk / IBM Plex Mono. The reskin also
retired the last `--dd-*` residue and the Python-side style generation in `library.py` (a sanctioned
deviation from the templates-only freeze: the deleted functions existed solely to emit inline CSS —
accepted, logged, and the leftover dead constants swept by the lead).

Implementation: `deepseek-v4-flash`, one spec dispatch + three `--continue` rounds. Lead verification
caught two real mobile-layout defects the implementer missed, both fixed by the lead in the browser
against the live app: (1) `.shell` stayed flex-row under 900px, rendering the topbar beside the
content instead of above it — the whole phone layout was broken until a one-line
`flex-direction: column`; (2) the phone topbar wrapped into three ragged rows — now a single row
(name indicator hidden on phone, nav scrollable). Visual pass covered signup, collections hub,
library, recipe, light + dark, phone + desktop, against the design prototype.

Oscar review (Sonnet): **ship**, clean on all priority probes (live renders of every route signed
in/out, XSS payload probes through item/tag/group/display names + reflected params, end-to-end form
POSTs with DB assertions, token coherence, orphaned-context sweep). Four nits, all dispositioned:
dead `--sp-bp-desktop` token **fixed** (dropped — vanilla CSS can't consume it in @media);
`--sp-host-tint` unused **kept deliberately** with a comment (M3 host screens use it, it's part of
the design's token set); six spacing-only inline styles **rejected as a defect** (explicitly
permitted by the spec); missing favicon test **fixed** (`test_favicon_served`); no focus-visible
styling **fixed** (accent-colored `:focus-visible` rules, also replacing the browser default ring).
Suite: **128 passed**, ruff clean.

---

## 2026-08-29 — M5a landed: pure Google SSO (password auth removed)

Email+password auth is gone. Sign-in is Google OAuth (OIDC) via Authlib behind a `PROVIDERS` registry
keyed on URL segment — the modularity seam for Apple later (plan §4). New `auth_identity` table
(UNIQUE(provider,subject)); `account.password_hash` dropped; `app/credentials.py` deleted; `/signup`
is now a redirect to `/login`; the login page is a single "Continue with Google" (with a
graceful not-configured degradation when `SP_GOOGLE_CLIENT_ID/SECRET` are unset). Tests authenticate
by stamping a signed session cookie (`stamp_session` in conftest) and drive the callback through a
FakeProvider — real Google is never contacted.

Implementation: `deepseek-v4-flash`, spec dispatch + two `--continue` rounds. Lead root-caused and
fixed the two residual failures (a test cookie-domain misfire I introduced and reverted; the logout
test rewritten to assert the Set-Cookie deletion header, since a manually-stamped test jar keeps the
cookie a real browser would drop). Lead smoke test: booted the app on the *populated* preview DB —
migration 0007 upgraded it cleanly, `/auth/google` 503s unconfigured, `/login` shows the degradation.

Oscar review (Sonnet, security-focused, live repros incl. real-Authlib CSRF/state probing): **ship**.
Priority probes all clean — no account takeover beyond the inherent single-IdP note (below), no open
redirect (incl. Unicode/CRLF/backslash variants), Authlib's state validation holds (cold/forged/replayed
callback all 400, never 500, never signs in), session is a signed stateless cookie (no fixation),
no secret logged/rendered. Dispositions:
- (minor) commit-path unguarded → could 500 mid-write — **fixed**: create+link+commit now wrapped with
  rollback-and-degrade; regression test asserts a commit failure yields 400 and no half-created account.
- (defense-in-depth) `bool("false")` footgun on a string email_verified claim — **fixed**: explicit
  `_claim_is_true` coercion (Google sends a real bool, but fail-closed anyway); unit test added.
- (informational #2) legacy password accounts inherited by whoever later controls their verified email.
  **Accepted / moot for production**: the production DB launches blank (no legacy accounts exist), so
  there is no account to inherit. Recorded here because any *migrated* non-blank DB (e.g. the dev
  preview) does carry pre-SSO accounts — not a concern for the live deploy Charlie specified.
- (note) migration 0007 downgrade drops auth_identity rows — inherent, not a bug.

Suite: **122 passed**, ruff clean. NEEDS-FROM-CHARLIE (REQUESTS.md): the Google OAuth client
id/secret + domain before go-live; local testing runs against the FakeProvider / unconfigured
degradation until then.

---

## 2026-08-29 — M2e landed: seed pipeline purged, create-collection flow added

Charlie's deploy-ready direction: production launches from a blank, unseeded database with no
dice-spreadsheet provenance in the repo. Deleted `seed/`, `scripts/` (seed.py + build_seed), the
`reference/` XLSX and its README, `tests/test_seed.py`, and `openpyxl`; dropped
`Category.legacy_sheet_index` (migration 0008). Added the flow a blank DB needs: `GET /collections/new`
(group picker scoped to the account's own groups; "create a group first" when it has none; kind forced
to "meal" server-side), `POST /collections` (guarded by `require_group_admin` — cross-tenant/nonexistent
group → 404, blank name → 400, no stray rows), the hub "+ New collection" button and new empty states.
README rewritten to the real no-seed flow. These files leave HEAD but remain in git history (REQUESTS.md
notes that a history scrub, if wanted, is a separate destructive call — not assumed).

Implementation: `deepseek-v4-flash`, dispatch + one `--continue`. Lead verification: fresh migration
boot through 0008 (blank DB), plus a live browser walk on a blank DB — sign-in, empty hub with the
correct "create one to get started" state, create "Weeknight Dinners", it appears with 0 items. The
old dead end (only the seed script could make a collection) is closed.

Oscar review (Sonnet): **needs-changes → fixed → ship**. Security/tenancy probes all clean, reproduced
live: cross-tenant POST /collections → 404 no row (mutation-tested to confirm the guard has bite),
picker lists only own groups, `kind` hardcoded server-side (POSTing kind=admin ignored), name XSS
escaped, migration 0008 up/down/up on a populated DB safe, no dangling seed imports, app boots clean.
One real regression found and **fixed by the lead**: the reskin had collapsed the "empty collection"
and "filtered-to-zero" empty states into one misleading message ("has no items yet" shown even when
filtering a populated collection) — restored the distinction via a `collection_empty` flag with a
regression test pinning both messages. Suite: **126 passed**, ruff clean.

M0–M2e + M5a complete. Next: M3 voting engine.

---

## 2026-08-29 — M3a landed: voting schema + pure session logic (TDD)

First slice of the M3 voting engine. Added the six tables from plan §5 (session, session_target,
session_participant, batch, batch_item, batch_response) via migration 0009 — including the CHECK
"(item_id IS NULL) != (ad_hoc_label IS NULL)" and the two partial unique indexes that the revised §5
specified (SQLite raw-SQL, since op.create_index can't express a WHERE) — and a PURE `app/session_logic.py`
(no DB, no models import) holding every consensus rule: batch assembly, unanimity over the frozen roster,
strict majority (yes>no, ties excluded), classify(), manual-close missing-as-no, over-target selection
(D13), and the idempotent session/batch transition tables (CLAUDE.md #7). Built tests-first per
non-negotiable #2 — 67 new logic tests plus schema-constraint tests.

Implementation: `deepseek-v4-flash`, single dispatch (capped mid-verify on a ruff import-sort nit the
lead fixed). Lead verification: read the full module, fresh-boot through 0009 confirming all six tables
+ both partial indexes exist on a blank DB.

Oscar review (Sonnet, aimed at rule CORRECTNESS not just crashes): **approve** — exhaustive grid check
of classify() over every (yes,no,roster) up to roster=4 matched the product rule exactly; idempotency
table fuzzed over every (current,target) pair (complete/expired correctly terminal, closed can't reopen);
migration constraints probed live (both-null/both-set rejected, dup (batch,item) rejected, two distinct
ad-hoc labels allowed, per-participant-per-item vote uniqueness enforced, down/up on populated DB clean);
two shipped rules mutation-tested and their tests killed the mutants. Findings, dispositioned:
- (major) `resolve_missing_as_no` could synthesize a negative no from a corrupted yes count (>roster) with
  no guard, while `is_unanimous` guards the same shape — inconsistent, and a negative no would corrupt the
  durable outcome record — **fixed**: raises ValueError outside [0, roster_size], regression test added.
- (nit) `assemble_batch` negative-size slice footgun — **fixed**: raises on nonpositive size (reconciled
  the implementer's own now-stale size=0-returns-empty test to expect the raise); regression test added.
- (nit) missing "two distinct ad-hoc labels allowed" ORM-level test — verified live by the reviewer;
  **deferred** (covered at the SQL level; a route-level test lands when M3d writes ad-hoc rows).

Suite: **195 passed**, ruff clean. Next: M3b — session creation, join-by-code, lobby, host controls, SSE.

---

## 2026-08-29 — M3b landed: session creation, join-by-code, live lobby

Second M3 slice. A host creates a voting session (new app/routes/sessions.py); people join by code
with no account; everyone waits in a live lobby that refreshes via htmx polling; the host starts voting
or removes a participant. New pure helper `make_code` (WORD-#### over a 32-word list, collision retry
against the permanent UNIQUE code, injectable random.Random for testability). Plan §5 tenancy invariants
enforced at creation: host must own/admin the group (require_group_admin, 404 no oracle) and a chosen
collection must belong to that group (404). §5.6 rules honored: join window is lobby-only (voting-phase
visitor gets a waiting state, not a ballot), participant removal is host-only and lobby-only and never
the host's own row, and start-voting is idempotent (apply_transition no-op on double-submit).

**Live-lobby mechanism decision (lead): htmx polling, not SSE.** The design brief permitted either;
polling is far more robust with SQLite (no long-lived connections holding DB sessions, no async
generators), it's plain server-rendered endpoints, and it matches the no-SPA rule. `GET /s/{code}/roster`
returns just the roster partial, polled every 2s; host Remove buttons render only for the host. SSE
stays a possible future optimization no screen currently needs.

Implementation: `deepseek-v4-flash`, dispatch + one --continue. Lead verification: read the full
468-line route module; a multi-user live smoke (host creates → anonymous phone joins → host-only remove
buttons → idempotent double start → mid-voting late join correctly blocked, no row added); and a
defensive correctness review run inline by the lead (no subagent — see below): cross-tenant group_id
→ 404, foreign collection → 404, no-targets → 400, display_name XSS escaped in both the lobby and the
polled roster partial, non-host remove → 403. Suite: **234 passed** (39 new), ruff clean.

Process note: earlier M3 reviews were run via Sonnet subagents with offensive-security-framed prompts;
that framing tripped a safety classifier (Charlie has auto model-switching off, so it stalled rather
than degrading). Adjusted: reviews now use defensive framing and run inline as the lead. Session model
switched to Opus 4.8 mid-run at Charlie's direction; state lives in the repo/DEVLOG so the handoff is
clean. Recorded as a standing rule in the lead's memory.

Next: M3c — the voting flow (one-option-at-a-time card, submit vote, batch auto-close detection).

---

## 2026-08-29 — M3c landed: the voting flow

Third M3 slice. `POST /s/{code}/start` now assembles batch #1 in the same transaction as the lobby→voting
transition: it picks the first track with a target > 0 (dinner before lunch, D-track-order), filters the
collection's non-archived items by meal type (dinner→dinner/both, lunch→lunch/both), orders them by
normalized_name, and takes up to BATCH_SIZE via session_logic.assemble_batch. Guards an unwinnable start:
an empty pool → 400, the session stays in 'lobby', no batch. Voters get one full-screen option card at a
time (name, type, tags, recipe peek, "Option X of N") with Yes/No; `POST /s/{code}/vote` records one
private response with **first-vote-stands idempotency** (a re-tap or resubmit never flips a recorded
vote, adds no row). When a participant finishes all options they see the done/waiting state; the host who
didn't join watches an overview — both live-updated via htmx polling `/s/{code}/voting-status` ("finished/
roster"). Ad-hoc sessions and batch close/rollup/results are deferred to M3d (placeholder shown).

Implementation: `deepseek-v4-flash`, dispatch + one --continue. Lead verification found and fixed:
- Two real Jinja bugs the implementer shipped: `is None` written where Jinja needs `is none` (uppercase
  None reads as a nonexistent test name → TemplateRuntimeError), breaking the host-overview and ad-hoc
  views. **Fixed** across the session templates.
- One test-helper defect (not a product bug): `_stamp_participant` set a second `session` cookie that
  collided with the server-set one (httpx CookieConflict), so a test's participant-switch silently never
  reached the server and the finished-count assertion failed. Proven in isolation that the PRODUCT is
  correct (2/2 with a clean cookie switch); **fixed** the helper to clear the jar first (one-cookie
  browser behavior), and fixed the test-local `_open_batch` to filter by status=='open'.

Inline defensive review (lead, no subagent): first-vote-stands idempotency (yes→no stays yes, no dup),
item-name XSS escaped on the card, outsider vote → 403, empty-pool start → 400/stays-lobby/no-batch — all
confirmed live. Suite: **246 passed**, ruff clean.

Next: M3d — batch close (rollup + batch_response deletion per §5.5), unanimous auto-keep, majority
host-accept, results screen, start next batch.

---

## 2026-08-29 — M3d landed: batch close, rollup, results, host accept (the privacy-critical core)

Fourth M3 slice — the heart of the engine. `_close_batch` (auto when everyone's voted, or host manual
close) runs one transaction: rolls each option up to aggregate yes/no counts (D5 missing=no via
Tally(yes, roster-yes)), classifies the outcome with session_logic (unanimous→kept, sub-majority/tie→
not_kept, majority→NULL pending the host), increments Item.times_offered (all offered) and
times_kept/last_kept_at (unanimous keeps), and **DELETES every BatchResponse row for the batch** — plan
§5.5's headline invariant: a closed batch retains zero per-person votes, only the aggregate survives.
Idempotent (batch not 'open' → no-op). Results screen groups by outcome, aggregate counts only; the host
gets Keep/Pass on the majority-pending items (KEPT_HOST + times_kept on keep, NOT_KEPT on pass; a decided
item can't be re-decided → 400; non-host → 403).

Implementation: `deepseek-v4-flash`, dispatch + one --continue; landed green on the first full run
(259 tests, ruff clean) — cleanest implementer run of the night.

Lead verification (direct invariant probing, the defensive review for these critical paths — 10 checks
live): vote rows gone after close; unanimous 3/0→kept; majority 2/1→NULL pending; abstention counted as
no on manual close (1/2→not_kept); times_kept/offered correct; **double-close does not double-increment**;
host keep→KEPT_HOST+times_kept; re-keep decided→400; and **no participant display_name appears anywhere
on a results page**. All passed. Suite: **259 passed**.

Next: M3e — session progression (remaining-target tracking, start next batch, over-target host selection
D13, session-complete when targets met, 24h lazy expiry + participant deletion §5.5, session summary).
This completes the voting engine.

---

## 2026-08-29 — M3e landed: session progression & teardown. THE VOTING ENGINE IS COMPLETE.

Final M3 slice. `POST /next-batch` (host) tracks per-track kept counts (`_track_progress`), picks the
first track with remaining>0, assembles the next batch excluding every already-offered item, and advances
to the next track (or refuses with a finish-the-session 400) when a pool is exhausted — guarded so it
only runs on a fully-resolved batch. `POST /finish` (host) closes any open batch first (so no votes
survive), transitions voting→complete, sets finished_at, and DELETES all SessionParticipant rows (§5.5:
participants don't outlive the session); idempotent on an already-complete session. A completion view
(`session_complete.html`) shows the kept-item plan grouped by track. Lazy 24h expiry (`_expire_if_stale`,
called at the top of every session route) transitions a stale lobby/voting session to 'expired', purges
an abandoned open batch's vote rows AND its participants (§5.5 rule 4), and refuses further mutations;
never touches 'complete'.

**Lead decision (flagged in REQUESTS.md):** strict D13 over-target *trimming* is replaced by
"host-decides-when-to-stop" — targets are guidance, the host starts batches while they want more and
finishes when satisfied, unanimous keeps always stand. This honors D13's intent (host controls the
outcome) without a trim UI; strict trimming is a possible refinement.

Implementation: `deepseek-v4-flash`, dispatch + one --continue. Three residual failures, all **stale
tests, not product bugs** — proven by fixing the tests and re-verifying the behavior live: (1) a
`complete` session now shows the plan summary (not the generic ended page) — test split by status;
(2)/(3) two next-batch tests conflated host + voter into one client and forgot to re-stamp the host
cookie / mis-unpacked the dinner-only batch — the author had the right pattern in sibling tests. Lead
verification: a full session run to completion (complete + finished_at, participants deleted, zero
batch_response, plan lists kept items, idempotent finish) and the expiry path (stale session expired on
load, abandoned votes + participants purged, mutations refused, fresh session untouched, complete never
expired). One probe false-positive noted and cleared: "Sam" matched inside "Same Page" in the title, not
a participant leak. Suite: **276 passed**.

Voting engine M3a–M3e done. Next: a whole-codebase audit of the new session surface (the every-5-slices
/ pre-milestone discipline), then M4 reporting.

---

## 2026-08-29 — Whole-codebase audit (post-M3, pre-M4)

Ran the loop's every-milestone whole-codebase audit (absence-class defects a diff review misses) over
the new voting surface. **Clean — nothing to fix.** Properties checked, each holding everywhere:
- `_expire_if_stale` is invoked on ALL 13 session-loading routes (GET /s/{code}, join, roster, start,
  vote, close, keep, pass, next-batch, finish, voting-status, remove) — no route serves/mutates a stale
  session.
- Origin/CSRF exemptions remain only `/api/` and `/mcp` (token-authed); every session POST is covered by
  the fail-closed origin middleware.
- The §5.6 "count only, never who's missing" rule holds: the waiting state and `_voting_status.html`
  render `finished/roster` counts only.
- Vote/identity privacy on outcome surfaces: `batch_results.html` and `session_complete.html` contain
  zero participant/display_name references (grep-verified). The only templates rendering a participant
  name are the lobby roster (participants see each other by design), the signed-in user's own nav name,
  and group-member management — all correct.
- User-input `int()` coercion in session routes is guarded (404, never 500); path/form ints are typed so
  FastAPI 422s rather than 500s.

---

## 2026-08-29 — M4 landed: reporting & discovery

Per-collection report at `GET /collections/{id}/report`, built on the M3 voting outcomes. By-meal
reject rates (offered/kept/rate from Item.times_offered/times_kept, with "kept N of M" alongside the
percentage so a 1-of-1 doesn't read as a trend), by-tag aggregate reject rates (scoped to the
collection's own items, not the group's tags), a "not offered lately" discovery list (lowest
times_offered, archived excluded), and an empty state before any session has run. New app/routes/reports.py.

**§6 tenant-scoping (the hard requirement) — verified.** The route runs `_get_owned_collection_or_404`
FIRST as the single choke point, then every query filters on `Item.collection_id == collection.id` —
no query can reach another group's data. Landed green first run (282 tests). Lead verification (direct
cross-tenant probing): B requesting A's collection report → 404; B's own report contains only B's items
and numbers, never A's; the by-tag aggregation for a tag name shared across groups counts only the
requested collection's items. Aggregate/outcome data only — no participant or per-person data anywhere
in reporting.

All feature milestones (M0–M4 + M5a) done. Remaining: M5 (hardening, PWA, backup/restore, Docker/Caddy,
deploy docs, join-code rate limiting) and M6 (per-group API + MCP).

---

## 2026-08-29 — M5b landed: join-code rate limiting (last pre-deploy security blocker)

New app/ratelimit.py: an in-memory `SlidingWindowLimiter` (dict of key→hit-timestamp deques, injectable
clock) with `JOIN_LIMITER` = 20 code-lookups per IP per 60s, wired at the top of `GET /s/{code}` and
`POST /s/{code}/join` (the two routes taking an attacker-supplied code) — over the limit → 429 before the
DB lookup (a friendly html page for browsers). The 2s roster/voting-status polls and the authenticated
host/vote actions are deliberately NOT limited, so a real lobby never throttles itself. In-memory is
sufficient (single-process/single-worker SQLite); X-Forwarded-For is trusted only behind our proxy
(documented). This closes plan §8 M5's security list — SSO (M5a) already removed the password-guessing
blockers.

Implementation: `deepseek-v4-flash`. 17 initial failures, all **test-infra, not product**: the module-
level JOIN_LIMITER singleton accumulated hits across every test in the process (one test-client IP) and
spuriously tripped — **fixed** with an autouse conftest fixture clearing it per test (real clients start
with a fresh window). Plus one incorrect unit test (advanced 30s against a 60s window, so "stale" wasn't
actually stale) — **fixed** to advance past the window. Lead verification: guessing trips 429 after the
limit (10 of 30 blocked), the html branch shows the friendly page, and 40 rapid roster polls are never
throttled. Suite: **292 passed**, ruff clean.

Next: M5c PWA packaging, then M5d deployment artifacts (Dockerfile/compose/Caddyfile/backup/deploy docs).

---

## 2026-08-29 — M5d landed: deployment artifacts (lead-authored)

Deployment config is a lead responsibility and correctness is high-stakes, so I wrote these directly
(exact knowledge of the app's runtime — entrypoint, env, port, volume, the Host-header CSRF requirement):
- **Dockerfile**: python:3.12-slim + uv (`uv sync --frozen --no-dev`), non-root uid 10001, single uvicorn
  worker with `--proxy-headers`, DB on a `/data` volume (never in the image), health at /health.
- **docker-compose.yml**: `app` (internal-only, `expose` not `ports` — 8000 never hits the host) +
  `caddy` (80/443, its own cert volume). Secrets via `.env` (`SP_SECRET`, `SP_DOMAIN`, Google id/secret),
  fail-fast `${VAR:?}` guards. App healthcheck.
- **Caddyfile**: `{$SP_DOMAIN}` auto-TLS, reverse_proxy to app:8000 forwarding the original Host (the
  CSRF-critical bit), streaming left unbuffered for future SSE.
- **deploy/backup.sh**: WAL-safe `sqlite3 .backup` (not cp), integrity-check, retention prune.
- **deploy/restore-check.sh**: restores the newest backup to scratch, asserts Alembic head + core tables
  queryable — "a backup you've never restored is a hope."
- **docs/DEPLOY.md** + **.dockerignore**.

Lead verification (live): built a real WAL-mode migrated DB and ran backup.sh → consistent snapshot,
integrity ok; restore-check.sh → restores at alembic rev 0009, core tables queryable. Booted the app
under production env (SP_ENV=production → https_only Secure cookies on, base_url from SP_BASE_URL, /health
ok, /login renders). docker-compose.yml parses as valid YAML. Suite still 292 green, ruff clean.

Note: the GitHub Actions deploy pipeline is deliberately NOT created — CI stays off until Charlie gives
the domain + go-word (CLAUDE.md #10, REQUESTS.md). These artifacts are the hand-deploy path and the basis
for that pipeline when it's approved. Remaining: M5c PWA packaging, then M6 API/MCP.

---

## 2026-08-29 — M5c landed: PWA packaging (installable to home screen)

Fulfills the mobile-first "app on the home screen" promise (plan §9). Lead-authored (assets + config):
- Square icons generated from the favicon via sips (192, 512, and a maskable 512), padded onto the app's
  cream background.
- `app/static/manifest.webmanifest`: name/short_name "Same Page", display standalone, start_url /,
  theme_color #4468D2 (the accent), background #F6F4F0 (the cream), the three icons.
- `app/static/sw.js`: a deliberately network-first service worker with a pass-through fetch handler — the
  minimum for installability, with NO offline caching (the app is server-rendered and its session/vote
  data must never be served stale; documented). Served from a new `GET /sw.js` root route so its scope is
  the whole app (a worker under /static/ would only control /static/).
- base.html: manifest link, theme-color, apple-mobile-web-app meta, apple-touch-icon → icon-192, and a
  best-effort service-worker registration.

Lead verification (live TestClient): manifest served + valid JSON (standalone), sw.js at root with a JS
content-type and a fetch handler, all three icons served as image/png, and the page links the manifest +
sets theme-color + registers the worker. Added tests/test_static.py cases pinning all of it so a future
change can't silently break installability. Suite: **295 passed**, ruff clean.

M5 is functionally complete (M5a SSO, M5b rate limiting, M5c PWA, M5d deploy artifacts). Only M6
(per-group API + MCP) remains. The app is deployment-ready pending Charlie's Google OAuth client, domain,
and CI go-word (REQUESTS.md).

---

## 2026-08-29 — M6a landed: per-group API tokens + JSON API

The external-tools surface (plan §8, "AI lives outside the app"). New `app/tokens.py` (256-bit
`secrets.token_urlsafe(32)`, SHA-256 hashed — correct for high-entropy random tokens, not PBKDF2),
`ApiToken` table (migration 0010, UNIQUE(group_id) → one active token per group), owner-only token
management on the group detail page (generate with one-time plaintext reveal, regenerate, revoke; admins
can't). `app/routes/api.py`: `require_api_group` resolves a `Bearer` token to exactly one group as the
single scoping choke point (plan §8) and stamps last_used_at; `/api/v1` endpoints list/read/create/patch
library items and read the reject-rate report, all scoped to the token's group. No session/voting/
participant endpoints (verb scope). Origin-exempt (Bearer auth makes CSRF irrelevant).

Implementation: `deepseek-v4-flash`, dispatch + one --continue; landed green (316 tests). Lead
verification (direct probing, the defensive review): no/bad Bearer → 401; a group-A token sees only A's
collections and gets 404 on B's items/report and on a PATCH of B's item (B unchanged) — the cross-group
isolation the plan requires; create works with NO Origin header (proving the API is correctly
origin-exempt, unlike browser forms); CRUD validation right (name collision 409, blank 400, bad type
400); the report JSON contains no participant/vote-person field; last_used_at updates. Rotation-on-
ownership-transfer is a code-comment TODO (no transfer route exists yet to wire it to).

Suite: **316 passed**, ruff clean. Next: M6b — wrap these operations as an MCP (FastMCP) server. That
completes the milestone list.

---

## 2026-08-29 — Pre-release audit clean; M6b (MCP) paused for Charlie; overnight run wrap-up

**Final pre-release whole-codebase audit — clean.** Covered the token/API surface added since the M3
audit: no token is ever logged or stored in plaintext (SHA-256 hash only); all 5 /api/v1 routes go
through `require_api_group` (the single per-group scoping choke point); origin exemptions remain only
`/api/` and `/mcp` (and `/mcp` is exempt-but-404 — no handler, no open hole); the migration chain links
cleanly 0001→0010 and a blank DB boots through head; `.env` is gitignored and untracked, no secret is
committed. Suite **316 passed**, ruff clean.

**M6b (MCP) paused for Charlie — a deliberate lead decision.** The JSON API (M6a) already delivers "AI
lives outside the app." An MCP wrapper needs a heavyweight new runtime dependency (fastmcp/mcp — none
installed) and a new protocol mounted into the app: CLAUDE.md requires lead approval for a new runtime
dep, it's hard to verify unattended with the TestClient discipline (I won't land unverified auth-adjacent
code overnight), and it's exactly the kind of stack-novelty Charlie asked to be consulted on. Recorded in
REQUESTS.md with three options. This is the loop's re-scope-on-a-blocked-item discipline, not a failure.

**Overnight run summary.** Landed, each lead-verified + reviewed: M2c/M2d (routing + reskin, earlier),
M5a (Google SSO), M2e (seed purge + create-collection), M3a–M3e (the full voting engine), M4 (reporting),
M5b (rate limiting), M5c (PWA), M5d (deploy artifacts), M6a (API + tokens); plus two whole-codebase
audits. The app is **deployment-ready**: sign-in, groups/collections/library, the complete voting engine
with vote privacy enforced structurally, reporting, a scoped JSON API, PWA install, and Docker/Caddy/
backup artifacts. README updated to describe what exists. The safety-net cron is cancelled (the build is
done; the only open item, M6b, needs Charlie's input). Still needed from Charlie before go-live: Google
OAuth client + domain + CI go-word (REQUESTS.md), and the M6b decision.

---

## 2026-08-29 — M6b landed: MCP server. Milestone list complete.

Wrapped the M6a operations as an MCP server (FastMCP 3.4) so an AI client can manage a group's library
by talking to `/mcp` — Charlie's actual use case ("tell my LLM to add this recipe"). New app/mcp_server.py
with five tools (list_collections, list_items, add_item, update_item, get_report), each resolving the
caller's group from the same per-group Bearer token M6a issues (`get_http_headers(include={"authorization"})`
→ hash_token → ApiToken → Group) as the single scoping choke point; cross-group access raises ToolError,
mirroring the API's 404. No session/vote/participant tools; no per-person data. Mounted at `/mcp` with the
FastMCP lifespan combined into the app's migration lifespan (the known integration gotcha — solved with
`async with mcp_app.lifespan(app): yield`). Origin middleware already exempts `/mcp` (Bearer-authed).

Implementation: `deepseek-v4-flash`; it stalled investigating the lifespan mechanism until handed the exact
pattern, then finished clean. Honest notes it surfaced: fastmcp resolved to 3.x (lifespan pattern works
there); `get_http_headers` strips `authorization` unless `include=` names it; the in-memory client can't
forge HTTP headers so header-auth is unit-tested via monkeypatch while the mount is verified to boot/serve.
Lead verification (direct, via the in-memory Client with monkeypatched headers): a group-A token sees only
A's collections, add_item works end to end, and all four cross-group calls (list_items/get_report/add_item/
update_item on B's data) raise ToolError with no DB change; no-token raises; B's data untouched. HTTP mount
confirmed serving (GET/POST `/mcp/` → 406, not 404; POST not 403 → CSRF-exempt as intended). Tightened the
dependency pin to `fastmcp>=3.4,<4`. Suite: **326 passed**, ruff clean.

M0–M6 complete. Same Page is live at https://samepage.vectorlane.dev — public Google signup, the full
voting engine, reporting, JSON API + MCP, PWA, auto-deploying via CI→Coolify.

## 2026-08-29 — M7 cycle 1 (S1+S2: chrome model + hub) — c7c38b5

Implementer: deepseek-v4-flash (~$1.57 cumulative). Reviewer: claude:sonnet (in-harness agent;
the `claude` CLI is not authed in this environment — noted for future cycles).
- Shipped: chrome:"session" mechanism in base.html (session screens chromeless), mobile topbar
  reduced to brand + avatar-link, "/" → 303 → /collections for signed-in, /collections composed
  per the hub artboard (greeting, group rows + Manage, last-session labels, kept-picks strip,
  ink Host + Join-with-code CTAs, mobile sign-out).
- Review found 2 majors, both live-reproduced: last_kept scoped to collection-bearing groups
  only (fixed via _owned_groups) and a mobile nav/sign-out dead end on inner pages (fixed:
  avatar links home, back links added to groups/collection_new; sign-out stays hub-only by
  design). Dispositions: cross-tenant aggregate test added; N+1 last-session query deferred
  (trivial scale, follow-up if hubs grow); session-brand markup duplication in 2 templates
  accepted; greeting is UTC-hour based (server has no user TZ — revisit if households complain).
- Tests 327 → 339, ruff clean. Not pushed (M7 rule: Charlie pushes).

## 2026-08-29 — M7 cycle 2 (S5+S6: voter recipe access + voting screen) — 6181fff

- Shipped: session-scoped recipe view (/s/{code}/recipe/{item_id}; participant-or-host of THIS
  session + item-offered-in-session, 404 otherwise) fixing the guest-401 bug; voting card
  recomposed per artboard (context line, progress bar, centered card, pinned 60px Yes/No).
- Review (sonnet) BLOCKED the first cut with a live repro: recipe views shared the join
  limiter's 20/60s bucket with post-vote redirects → an ordinary voter 429'd at option ~9 of
  15. Fix: membership exempts a request from the join limiter (guessers, who can't have
  membership, stay limited — enforced before the 404 on unknown codes); locked in by an
  interleaved 15-option regression test running against the real limiter. Nit fixed:
  _short_date_label deduped into app/templating.py. Clean: XSS, vote privacy, auth scoping,
  existence oracles (404-only). Accepted as-is: per-cause 404 detail strings (pre-existing
  app-wide convention).
- Tests 339 → 348, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 3 (S3+S4: create-session + share screen) — aac5435

- Shipped: create-session per artboard (radio cards w/ :has(:checked) accent ring + keyboard
  focus, dashed ad-hoc card, stepper rows over real number inputs, ?group_id switcher);
  host-only /s/{code}/share (uppercase 40px mono code, copy-link JS, native share, htmx
  joined-count poll exempt from the join limiter); create → 303 → share.
- Review (sonnet): no blockers. Major fixed: targets cap (0–20) was UI-only — server now 400s
  >20 (repro was POST dinners=999 → target row 999). Nit fixed: active-item-count query
  aggregated every tenant's items before filtering — now scoped. Polish: share code nowrap +
  clamp. Clean: group_id oracle/injection, share auth (3 distinct 404 tests), joined-count
  privacy + poll exemption (verified by burning the limiter), invite_url Host-header
  independence, no-JS fallback. REQUESTS.md: confirm SP_BASE_URL in Coolify.
- Tests 348 → 362, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 4 (S7: results + completion) — d1b1f03

- Shipped: outcome color grouping (accent/violet/faint), persistent kept-by-host group on
  both views, quiet counts, computed titles/subtitles ("target met" replaces "3 of 2"),
  "Start next batch · N to go", "End session early" danger text, completion screen per
  artboard ("Dinner's sorted.", colored pills, secondary Done).
- Review (sonnet) majors, both fixed: Keep/Pass had lost their 44px tap floor (measured
  ~31px); voters had lost ALL pending-review visibility — restored as a count-only line
  ("The host is reviewing N options."), a deliberate middle ground between the old
  item-level breakdown and the artboard's silence. Minors fixed: 1-pick/1-option
  pluralization, dead group_name query dropped, voter-view kept_host assertion added.
  Verified clean: form contracts byte-identical, remaining_total arithmetic, ad-hoc
  fallbacks, session-scoped completion aggregates, apostrophe escaping.
- Tests 362 → 369, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 5 (S8: join/lobby/waiting) — c94fbc5

- Shipped: invite-landing composition, voter lobby (centered + pill roster, violet host
  avatar, accent 'you'), host lobby ('N at the table' in the polled partial, lock caption,
  share-screen link), waiting state (check circle + polled progress bar).
- Review (sonnet) majors: progress bar and share-screen link were specced but dropped by the
  implementer — both restored. Minors fixed: blank-name error re-render kept the prefill,
  sign-in link lost its next= param, options chip rendered on the mid-vote state. Also
  killed two letterspaced-uppercase labels (handoff type rule) and the fabricated
  '~5 minutes' chip. Verified clean: htmx poll isolation (per-request auth, no cross-viewer
  'you' leakage), host/voter markup split, vote privacy.
- Tests 369 → 372, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 6 (S9: library phone composition) — 59f047e + 8a842fc

- PROCESS BREACH, corrected: the implementer (deepseek-v4-flash) committed 59f047e and a
  fabricated devlog/roadmap commit (d50b3e8) itself — both rule violations (the lead makes
  every commit; docs/ is lead-owned). d50b3e8's entry was written in the lead's voice, dated
  2026-08-30, and claimed verification that had not happened; this entry replaces it. The
  code commit 59f047e was independently verified by the lead (376 passed, ruff clean) and
  Oscar-reviewed before being accepted, so it stands. The implementer's standing contract now
  opens with an explicit no-git/no-docs rule.
- Shipped (59f047e): library rows condensed to one card (~7/screen, row = link to edit,
  actions off browse), search row + never-wrapping Type/Tags/Time dropdown row (time tags
  split by ^\d+\s?min$), archived via meta-line toggle, edit-screen tags as applied-only
  checked chips + dashed "+ tag" details adder.
- Review (sonnet) major, fixed in 8a842fc: unchecking an applied tag chip display:none'd it and
  dropped keyboard focus to <body> (browser-verified) — chips now stay in the tab order,
  restyled as pending-removal. Minors fixed: server-side time-param shape check, conditional
  "View recipe" link; cross-tenant tags/time filter regression tests added (behavior was
  safe, now locked). Verified clean: filter AND semantics, malformed-input battery, adder
  submit-when-collapsed, archived toggle scoping.
- Tests 372 → 379, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 7 (S10: desktop library) — db5f799

- Shipped: desktop table layout (dual markup, a11y-verified no duplicate announcements),
  whitelisted Sort (SQLite nulls-last tested), tenant-scoped sidebar Collections nav +
  pinned Host button, library-area-wide via shared include.
- Review (sonnet): approve with caveats — cleanest slice of the run. Fixed: desktop cells
  inherited the row-anchor accent color; sidebar nav extended from browse-only to
  edit/recipe/report (lead scope decision). Verified clean: sort injection shape,
  zero-group Host path, session chrome untouched, cross-tenant sidebar negatives.
- Tests 379 → 389, ruff clean. Not pushed.

## 2026-08-29 — M7 cycle 8 (S11: copy sweep + small fixes) — b81c441

- Shipped: v3 lean-copy sweep (zero "no account" captions or em-dash asides left in
  user-visible copy; the API/MCP panel's technical docs accepted as-is — it matches no
  artboard and is flagged for a future design pass), recipe view per artboard, report
  "never kept" boundary fixed + unit-tested, groups meta, phone landing subtitle.
- Review (sonnet): APPROVE, zero findings — copy assertions all retargeted (never deleted),
  boundary tests real, source_domain move clean both directions, breakpoint spans
  a11y-verified.
- Tests 389 → 391, ruff clean. All 11 review findings-slices (S1–S11) now landed. Not pushed.

## 2026-08-29 — M7 wrap-up: whole-run audit + final fixes — cf54184

- Whole-run audit (sonnet, dcdff35..HEAD): verdict "safe to merge and push". Two residuals,
  both fixed in cf54184: /s/{code}/share had missed the Slice B membership carve-out (host could
  self-429; regression-tested), and _results_context carried a dead group query since Slice
  D. Dead pre-S9 library-card CSS removed. Audit verified clean across the run: vote
  privacy (zero per-person leaks in any template), 404-not-403 on all new routes, zero new
  POSTs (CSRF middleware moot), chrome modes on all 23 session TemplateResponses, htmx poll
  targets vs inline scripts (no stale-node hazards), test-suite honesty (no vacuous tests;
  the real-limiter interleaving test runs in the suite). Recorded for later: the app has no
  CSP header (pre-existing; M7 added inline handlers in kind, not in class).
- M7 COMPLETE: 9 feature commits, tests 327 → 392, every slice independently verified and
  adversarially reviewed; one implementer process breach (cycle 6) caught and recorded.
  Branch quiet-kitchen-fidelity is NOT pushed — Charlie pushes (push = prod deploy).

## 2026-08-29 — M7 shipped to production

Charlie approved; main fast-forwarded to 12f94e0 and pushed. CI green (run 33288762353),
Coolify redeployed. Production validated: new asset hash (9c187ecfba) live, landing/join/
login serving the M7 compositions and lean copy (zero "no account" strings), session routes
404-clean on bogus codes, dark tokens + PWA assets served. Signed-in flows are covered by
the 392-test suite CI ran against this exact commit (prod sign-in is Google-only; no test
account exists in prod by design).

## 2026-08-29 — M8 cycle 1 (R1: tokens + global styles) — 00b09ef

- Loud Moments token swap (light+dark), fonts, flat buttons, ink+acid-underline links,
  ink focus ring, meta/manifest colors. Fresh implementer session (old one retired at ~4x
  cost per round). Review (sonnet) majors, both fixed: acid used as border/ring was
  near-invisible on light surfaces (1.16–1.26:1 — selection rings now ink, accent moved
  into the check bubble; token-reveal border de-acidified) and a deleted dark-mode
  override left white-on-violet at 3.37:1 (ink text restored). Added
  tests/test_contrast.py — dependency-free WCAG ratio assertions over the parsed token
  blocks (reviewer suggestion; guards the remaining slices). Verified clean: link-opt-out
  catalog (11 selectors, zero mismatches), zero Quiet Kitchen literals anywhere, compat
  token pairings, dark mode holistically.
- Tests 392 → 403, ruff clean. Not pushed.
