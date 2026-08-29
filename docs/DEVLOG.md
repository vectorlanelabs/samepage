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
