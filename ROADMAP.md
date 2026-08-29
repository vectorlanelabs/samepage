# SamePage — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## ⚠ Architecture pivot in progress (2026-08-28)

**M3 onward is unapproved.** Building M0–M2 as a single-household meal planner surfaced a bigger, more
useful shape: a generalized multi-tenant consensus-voting platform (**SamePage**), with meal planning
(**Meal Planner**) as its first collection. This changes identity/tenancy (M1 is being redone as M2a) and
generalizes the meal-specific schema (M2 is being redone as M2b) before M3 (planning sessions & voting,
never built) starts. Full architecture: `docs/PLAN-v2-samepage.md`. `docs/PLAN-v1-mvp.md` and
`CHARTER.md`'s identity/D10 decisions are superseded by that doc — left in place for history, not deleted.

## v2 (current target)

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, **Alembic migrations**, session, security middleware, CI | [x] | Landed 2026-08-26 (`0a786dc`); 22 tests; review fixes applied. Stands as-is — no identity/tenancy coupling. |
| ~~M1~~ → **M2a** | ~~Household profiles (PINs)~~ → **Identity & tenancy**: `Account` (email+password), `Group`/`group_admin`, replaces `Person`+PIN entirely | [x] landed 2026-08-28 | PINs fully removed. Library CRUD gated on "any signed-in account" (interim — proper group-scoping lands in M2b, tracked in REQUESTS.md). See `docs/PLAN-v2-samepage.md` §4/§8. |
| **M2b** | **Generic collections & items**: `Collection`/`Item`/`meal_detail`, scoped `Category`/`Tag`, migrate the 155 seeded meals | [x] landed 2026-08-28 | Clean-slate schema (matches M2a's precedent — no real user data to preserve); `scripts/seed.py` now requires a `group_id` and is idempotent per-collection. `/library` URLs unchanged; multi-collection routing deferred (tracked in REQUESTS.md). Revises the M2 work (`6d22054`). §5 |
| M3 | Session-based voting engine: group/account-hosted sessions, account-optional participants, ad hoc + library-backed items, outcome-only recording (no per-person vote history) | [ ] unapproved | Mechanics (batch size, unanimous/majority-host-accept) carry over from the old spec; identity plumbing does not. §5/§8 |
| M4 | Reporting & discovery (tag/category trend analysis on vote outcomes) | [ ] | Supersedes "history & favorites" — broader than `times_kept` alone. **Every query scoped to the requesting account's own groups** — new hard requirement under multi-tenancy. §6 |
| M5 | Hardening, polish, deployment docs, WAL-safe backup + restore check | [ ] | Single shared SQLite DB, not per-tenant (§6.1). **Open question for Charlie**: does the old site-wide passphrase gate still fit a platform meant to let other groups self-serve sign up? Tracked in REQUESTS.md. |
| M6 | External API + MCP server (**no in-app AI**) | [ ] | **Locked**: tokens are per-group, not one shared key — a global key would leak one group's data to another group's AI tools on the same deployment. Each group's owner generates/revokes their own token. §8 |

Detailed build plan: `docs/PLAN-v2-samepage.md` (current) · `docs/PLAN-v1-mvp.md` (superseded, kept for
history) · Scope & stop criteria: `CHARTER.md` (identity/D10 sections superseded — see pivot note above)

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Planning refinements & richer library**: recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, re-run last week, meal photos, **recipe-use experience (cooking view, printing)**, better filtering, looser keep rules if needed.
- **v2 — External intelligence via API & MCP (no in-app AI)**: recipe parsing (photo/link → recipe), discovery, trend analysis, and favorites surfacing all run in Charlie's AI tools through the app's API/MCP (D17) — no LLM keys or AI code in the product.
- **Later / explore**: grocery list generation (explicitly out of MVP), pantry mode, multi-household hosting + real accounts + public deployment, mobile apps, calendar/recurring rhythm, integrations, dice-ritual resurrection, data export.

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-28** — **Architecture pivot: SamePage.** Renamed from Dinner Decider; multi-tenant consensus
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
