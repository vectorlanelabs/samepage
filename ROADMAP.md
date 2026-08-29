# Same Page — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## ⚠ Architecture pivot in progress (2026-08-28)

**M3 onward is unapproved.** Building M0–M2 as a single-household meal planner surfaced a bigger, more
useful shape: a generalized multi-tenant consensus-voting platform (**Same Page**), with meal planning
(**Meal Planner**) as its first collection. This changes identity/tenancy (M1 is being redone as M2a) and
generalizes the meal-specific schema (M2 is being redone as M2b) before M3 (planning sessions & voting,
never built) starts. Full architecture: `docs/PLAN-v2-samepage.md`. `docs/PLAN-v1-mvp.md` and
`CHARTER.md`'s identity/D10 decisions are superseded by that doc — left in place for history, not deleted.

## v2 (current target)

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, **Alembic migrations**, session, security middleware, CI (built, then removed — CI is banned per CLAUDE.md non-negotiable #10; listed here as history) | [x] | Landed 2026-08-26 (`0a786dc`); 22 tests; review fixes applied. Stands as-is — no identity/tenancy coupling. |
| ~~M1~~ → **M2a** | ~~Household profiles (PINs)~~ → **Identity & tenancy**: `Account` (email+password), `Group`/`group_admin`, replaces `Person`+PIN entirely | [x] landed 2026-08-28 | PINs fully removed. Library CRUD gated on "any signed-in account" (interim — proper group-scoping lands in M2b, tracked in REQUESTS.md). See `docs/PLAN-v2-samepage.md` §4/§8. |
| **M2b** | **Generic collections & items**: `Collection`/`Item`/`meal_detail`, scoped `Category`/`Tag`, migrate the 155 seeded meals | [x] landed 2026-08-28 | Clean-slate schema (matches M2a's precedent — no real user data to preserve); `scripts/seed.py` now requires a `group_id` and is idempotent per-collection. `/library` URLs unchanged; multi-collection routing deferred (tracked in REQUESTS.md). Revises the M2 work (`6d22054`). §5 |
| **M2c** | **Pre-M3 correctness & routing**: Oscar code-review punch list (crash/oracle/redirect fixes, cross-tenant test band, dead-weight purge) + collection-scoped library routing (`/collections/{id}`, plan §9) | [~] in progress 2026-08-29 | Closes the multi-group dead end before M3 builds on the single-collection assumption. Visual/template work explicitly excluded — held for the design reskin (plan §9). |
| M3 | Session-based voting engine: group/account-hosted sessions, account-optional participants, ad hoc + library-backed items, outcome-only recording with the §5.5 lifecycle rules (vote rows deleted at batch close; participants deleted at session end) | [ ] unapproved | State machines and roster rules now in plan §5.6 (D5/D6/D13 re-adopted by reference). Mobile-first: voting is one option at a time (plan §9). |
| M4 | Reporting & discovery (tag/category trend analysis on vote outcomes) | [ ] | Supersedes "history & favorites" — broader than `times_kept` alone. **Every query scoped to the requesting account's own groups** — new hard requirement under multi-tenancy. §6 |
| M5 | Hardening, polish, deployment docs, WAL-safe backup + restore check, **PWA packaging** (manifest/icons/installable — plan §9) | [ ] | Single shared SQLite DB, not per-tenant (§6.1). Gate question **resolved 2026-08-29: no site gate; accounts are the boundary.** Hard pre-deployment security items (plan §8 M5): login attempt limiting, the signup email-enumeration decision, join-by-code rate limiting, login timing-side-channel fix. |
| M6 | External API + MCP server (**no in-app AI**) | [ ] | **Locked**: tokens are per-group, not one shared key — a global key would leak one group's data to another group's AI tools on the same deployment. Each group's owner generates/revokes their own token. §8 |

Detailed build plan: `docs/PLAN-v2-samepage.md` (current) · `docs/PLAN-v1-mvp.md` (superseded, kept for
history) · Scope & stop criteria: `CHARTER.md` (identity/D10 sections superseded — see pivot note above)

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Planning refinements & richer library**: recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, re-run last week, meal photos, **recipe-use experience (cooking view, printing)**, better filtering, looser keep rules if needed.
- **v2 — External intelligence via API & MCP (no in-app AI)**: recipe parsing (photo/link → recipe), discovery, trend analysis, and favorites surfacing all run in Charlie's AI tools through the app's API/MCP (D17) — no LLM keys or AI code in the product.
- **Later / explore**: grocery list generation (explicitly out of MVP), pantry mode, mobile apps, calendar/recurring rhythm, integrations, data export. (Multi-household hosting + real accounts + public deployment are no longer "later" — they landed in M2a/M2b.)

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-29 (2)** — **Oscar reviews applied + mobile-first locked.** Both 2026-08-29 Oscar reviews
  (plan + shipped code, saved in `docs/`) dispositioned: plan §5 PKs made implementable, vote-data
  lifecycle written as §5.5 (deletion is now a requirement, not a hope), session tenancy invariants and
  §5.6 state machines added, M4/M5/M6 rows sharpened, security follow-ups promoted to M5 blockers.
  New plan §9 locks Charlie's client direction: **mobile-first responsive web app, no SPA**
  (server-rendered + htmx/SSE), PWA at M5, one-option-at-a-time voting on mobile, collection-scoped
  library routing before M3. Design rework (Claude Design) re-briefed mobile-first via
  `docs/DESIGN-BRIEF-mobile.md`; visual/template changes held for that pass. New M2c row tracks the
  pre-M3 correctness/routing slice. Doc sweep fixed CLAUDE.md's stale PIN/`is_admin`/global-API-key
  lines and CHARTER's banner scope.
- **2026-08-28** — **Architecture pivot: Same Page.** Renamed from Dinner Decider; multi-tenant consensus
  platform (`docs/PLAN-v2-samepage.md`) with Meal Planner as the first collection. Real accounts +
  group ownership/admin replace `Person`+PIN entirely (no PINs anywhere); meals generalize to
  `collection`/`item`; voting outcomes are recorded per-item with aggregate yes/no counts and **no
  person-level history**, keeping the privacy invariant even stronger than before. M3+ unapproved until
  this doc is signed off; M1 becomes M2a (identity/tenancy), M2 becomes M2b (generic collections).
  Pre-reveal ad hoc option submission logged as backlog, not blocking.
- **2026-08-26** — **Plan 1 committed.** Charter, v1 MVP build plan (weekly planning sessions, pre-seeded library), and post-MVP stubs; legacy spreadsheet moved to `reference/`; seed data generated (155 meals); architecture: backend, VPS-hosted. Awaiting charter approval.
- **2026-08-26** — **Initial plan review applied** (`docs/INITIAL-PLAN-REVIEW.md`, 12/12 findings accepted): roster-freeze lobby phase, Alembic migrations (M0), WAL-safe backups with restore verification (M5), curated 27-meal `both` seed subset (lunch track populated), admin/PIN-hashing/CSRF security, strengthened vote-privacy invariant, README rewritten (concept moved to `docs/ORIGINAL-CONCEPT.md`), deployment wording fixed, recipe-use experience attached to v2 intake, batch size fixed at 15, idempotent session transitions, deactivate-not-delete. Awaiting charter approval.
- **2026-08-26** — **Majority-vote host acceptance** (Charlie): unanimous auto-kept; majority-yes meals (`yes > no`, ties excluded) shown with aggregate counts; host accepts while slots remain; `kept_by='host'` recorded. Awaiting charter approval.
- **2026-08-26** — **AI lives outside the app** (Charlie): new M6 — token-authenticated JSON API (`/api/v1`, `DD_API_KEY`) + FastMCP server so Charlie's AI tools import meals/recipes and run discovery/trends via MCP. No in-app AI, no LLM keys, ever. Seeded recipe links: Option B (real MCP imports prove the path at M6); Option A available. Awaiting charter approval.
