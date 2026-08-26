# Dinner Decider — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## v1 MVP (current target)

Product shape: **weekly planning sessions** — replacing the spreadsheet-and-dice ritual (the ritual is the problem this app exists to solve). Set lunch/dinner targets, iterate 15-meal yes/no batches (same list for everyone, private votes), keep unanimous-yes meals (host may accept majority-yes ones), repeat until the week is planned. Library **pre-seeded** from the legacy spreadsheet. No dice, no import feature, no grocery list.

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, **Alembic migrations**, session, security middleware, CI | [x] | Landed 2026-08-26 (`0a786dc`); 22 tests; review fixes applied |
| M1 | Household profiles: people (hashed PINs, admin flag), deactivate-not-delete | [x] | Landed 2026-08-26 (`e8a83d2`); 58 tests; atomic lockout + fail-closed Origin |
| M2 | Meal library CRUD + pre-seeded data (seed loader + tests) | [ ] | `seed/meals.json` already committed |
| M3 | Planning sessions & voting: lobby/roster freeze, targets, batches, yes/no voting, keeps, completion | [ ] | Core loop; two-browser walkthrough |
| M4 | History & favorites signal (`times_kept`) | [ ] | |
| M5 | Hardening, polish, deployment docs, WAL-safe backup + restore check | [ ] | Definition-of-done check |
| M6 | External API + MCP server (for Charlie's AI tools; **no in-app AI**) | [ ] | Proves recipe import + trend queries via MCP |

Detailed build plan: `docs/PLAN-v1-mvp.md` · Scope & stop criteria: `CHARTER.md`

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Planning refinements & richer library**: recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, re-run last week, meal photos, **recipe-use experience (cooking view, printing)**, better filtering, looser keep rules if needed.
- **v2 — External intelligence via API & MCP (no in-app AI)**: recipe parsing (photo/link → recipe), discovery, trend analysis, and favorites surfacing all run in Charlie's AI tools through the app's API/MCP (D17) — no LLM keys or AI code in the product.
- **Later / explore**: grocery list generation (explicitly out of MVP), pantry mode, multi-household hosting + real accounts + public deployment, mobile apps, calendar/recurring rhythm, integrations, dice-ritual resurrection, data export.

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-26** — **Plan 1 committed.** Charter, v1 MVP build plan (weekly planning sessions, pre-seeded library), and post-MVP stubs; legacy spreadsheet moved to `reference/`; seed data generated (155 meals); architecture: backend, VPS-hosted. Awaiting charter approval.
- **2026-08-26** — **Initial plan review applied** (`docs/INITIAL-PLAN-REVIEW.md`, 12/12 findings accepted): roster-freeze lobby phase, Alembic migrations (M0), WAL-safe backups with restore verification (M5), curated 27-meal `both` seed subset (lunch track populated), admin/PIN-hashing/CSRF security, strengthened vote-privacy invariant, README rewritten (concept moved to `docs/ORIGINAL-CONCEPT.md`), deployment wording fixed, recipe-use experience attached to v2 intake, batch size fixed at 15, idempotent session transitions, deactivate-not-delete. Awaiting charter approval.
- **2026-08-26** — **Majority-vote host acceptance** (Charlie): unanimous auto-kept; majority-yes meals (`yes > no`, ties excluded) shown with aggregate counts; host accepts while slots remain; `kept_by='host'` recorded. Awaiting charter approval.
- **2026-08-26** — **AI lives outside the app** (Charlie): new M6 — token-authenticated JSON API (`/api/v1`, `DD_API_KEY`) + FastMCP server so Charlie's AI tools import meals/recipes and run discovery/trends via MCP. No in-app AI, no LLM keys, ever. Seeded recipe links: Option B (real MCP imports prove the path at M6); Option A available. Awaiting charter approval.
