# Requests (non-blocking channel)

Genuinely needs Charlie's judgment — not decidable from the architecture or from what's already been
built. **Nothing here is promised.** Add freely.

*(empty — the three items that were here on 2026-08-29 are all resolved; see below.)*

## Known engineering follow-ups (decided, not blocking, no input needed)

Tracked so they don't get lost — these are settled calls, not open questions.

- [ ] **M5 pre-deployment security blockers** (revised 2026-08-29 after Charlie locked Google-only
  SSO, plan §4/M5a): the M5a SSO slice itself (its landing deletes password auth and with it the
  login-rate-limiting, timing-side-channel, and signup-email-oracle blockers), plus join-by-code rate
  limiting once M3 sessions exist. Until M5a lands, the password endpoints stay un-throttled — one
  more reason nothing gets publicly deployed before M5a.
- [ ] **NEEDED FROM CHARLIE before go-live — Google OAuth client + domain.** (1) In Google Cloud
  Console: create a project (or reuse one) → "APIs & Services" → "OAuth consent screen" (External,
  app name "Same Page", your email; no scopes beyond the defaults; publish) → "Credentials" →
  "Create credentials → OAuth client ID → Web application"; add the authorized redirect URI
  `https://<your-domain>/auth/google/callback` (and `http://localhost:8000/auth/google/callback`
  for local testing). Provide the client ID and secret as `SP_GOOGLE_CLIENT_ID` /
  `SP_GOOGLE_CLIENT_SECRET` env vars (never commit them). (2) The production domain itself — needed
  here, in Caddy, and in the deploy pipeline. (3) The explicit go-word for creating the GitHub
  Actions workflow once (2) exists.
- [ ] **Seed data removed from HEAD, not from git history** (Charlie 2026-08-29: no seeding, no
  XLSX, no dice provenance in the repo). The files are deleted from the current tree; git history
  still contains them. If history must be scrubbed too, that is a destructive rewrite — Charlie's
  explicit call, not assumed.
- [ ] **Phantom account indicator on a stale session** — `app/templating.py` trusts the session's
  `account_name` without a DB check (deliberate: no DB hit per render; names aren't editable). If an
  account-deletion/deactivation path ever lands, a surviving session cookie shows a live-looking
  indicator while every real route 401s. Revisit the context processor in the same slice that adds any
  account-removal capability. (Oscar M2c review, 2026-08-29 — minor, consciously deferred.)
- [ ] **Library export** — JSON export of items + recipes as backup/portability. M5 ships DB-level
  backups regardless; this would be a user-facing export on top. Low priority.
- [ ] **Drop `Category.legacy_sheet_index`.** This column persists a meal's position on the old dice
  spreadsheet — Charlie's call (2026-08-29) is that nothing about the dice mechanic, including its data
  provenance, belongs in this product going forward. Small, mechanical migration: drop the column, stop
  deriving it in `scripts/seed.py` (the `_category_index`/"Tab N" parsing), update `tests/test_seed.py`
  and `tests/test_models.py` accordingly. `Category.sort_order` stays — a display-order concept, not a
  dice-sheet artifact — but no longer gets populated from spreadsheet position. Do this in the same slice
  that next touches the seed pipeline (e.g. when the meal library gets re-curated with fresh, non-dice
  category names), not urgent on its own.

## Resolved

- ~~reference/D20 Dinner Decider.xlsx~~ — resolved 2026-08-29 by Charlie: delete it, along with the
  entire seed pipeline (seed/, scripts/seed.py + build_seed.py, test_seed.py) and
  `Category.legacy_sheet_index`. Production launches with a blank, unseeded database. Cycle B.
- ~~Bare 401s instead of a login redirect~~ — fixed 2026-08-29 (`main.py` 401 handler redirects browser
  navigations to `/login?next=...`; tests in `tests/test_auth.py`).
- ~~Library CRUD gating is interim~~ — effectively closed by the 2026-08-29 tenancy fixes:
  `_get_meal_collection` scopes to the signed-in account's groups, `_get_owned_item_or_404` guards every
  item mutation (with a cross-tenant test on each route), and creates insert into the account's own
  collection. Remaining structural piece is the routing item below.
- ~~Single-collection routing~~ — promoted to a milestone: **M2c** (ROADMAP), collection-scoped URLs per
  plan §9, landing before M3. No longer a someday-item.
- ~~Batch size default~~ — fixed at 15 (not a setup choice); revisit after real sessions.
- ~~Lunch starter set~~ — resolved via the curated 27-meal `both` seed subset.
- ~~Adversarial plan review~~ — fulfilled by `docs/INITIAL-PLAN-REVIEW.md`; all 12 findings accepted.
- ~~Hosting~~ — VPS (Hostinger), decided.
- ~~Track order~~ — dinner first, then lunch. Working default, never contested; not re-litigating it.
- ~~Over-target keeps~~ — host/starter picks which to keep when a batch agrees on more than the target.
  Working default, carried through the v2 design unchanged.
- ~~Majority rule~~ — strict `yes > no`, ties excluded, host accepts, unanimous always kept first,
  aggregate counts only. Confirmed by repeated use across the whole design process, not re-asking.
- ~~Recipe display~~ — built and working (M2/M2b): link and/or free text, shown on the recipe view page.
- ~~Raw votes via API~~ — no, aggregates only. Now structurally true, not just a policy: the v2 schema
  (`docs/PLAN-v2-samepage.md` §5.4) never stores a durable per-person vote in the first place.
- ~~API auth shape~~ — superseded by a real decision, not left open: per-group tokens, not one shared
  household key. See `docs/PLAN-v2-samepage.md` §8 (M6).
- ~~Seeded recipe links (M6 Option A vs B)~~ — Option B stands (prove the MCP import path on the 4
  existing links when M6 is built) unless raised again; not worth Charlie's time to re-confirm a default
  nobody's objected to.
- ~~CI disabled~~ — not an open question, a standing decision: off until Charlie provides a hosting
  target and explicitly re-approves it (`CLAUDE.md` non-negotiable #10). Documented there, not tracked
  here as pending.
- ~~Admin bootstrap~~ — obsolete. The old "first person on an empty install becomes admin" concept doesn't
  exist anymore; M2a's signup is always open, no bootstrap race to guard.
- ~~Multi-worker bootstrap guard~~ — obsolete for the same reason: the in-process `_bootstrap_lock` it
  referred to was removed with `Person` in M2a. `account.email`'s `UNIQUE` constraint already makes
  concurrent signups safe at the database level — no in-process lock needed, multi-worker or not.
- ~~CLAUDE.md refresh~~ — done.
- ~~Site access gate vs. open signup~~ (2026-08-29, Charlie) — **accounts.** No site-wide passphrase; real
  accounts are the security boundary. `Settings.access_key`/`SP_ACCESS_KEY` removed (it was never
  actually enforced by any middleware, so this is a clean deletion, not a migration). M5's deployment
  story no longer includes a gate-middleware task.
- ~~Lunch `both` subset sanity check~~ (2026-08-29, Charlie) — moot. This seed data gets replaced entirely;
  not worth curating a dataset that's going away.
- ~~Dice ritual~~ (2026-08-29, Charlie) — **removed, permanently, not a backlog item.** The dice mechanic
  is not coming back in any form, including as an optional feature, a data-provenance detail, or a design
  reference. Every "dice ritual, maybe later" mention across the repo's live docs was deleted, not
  deferred — see `docs/DEVLOG.md` for the full sweep.
