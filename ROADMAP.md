# Dinner Decider — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## v1 MVP (current target)

Product shape: **weekly planning sessions** — replacing the spreadsheet-and-dice ritual (the ritual is the problem this app exists to solve). Set lunch/dinner targets, iterate 15–20-meal yes/no batches (same list for everyone, private votes), keep unanimous-yes meals, repeat until the week is planned. Library **pre-seeded** from the legacy spreadsheet. No dice, no import feature, no grocery list.

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, session, CI | [ ] | First cycle after charter approval |
| M1 | Household profiles: people, PINs, device sessions | [ ] | |
| M2 | Meal library CRUD + pre-seeded data (seed loader + tests) | [ ] | `seed/meals.json` already committed |
| M3 | Planning sessions & voting: targets, batches, yes/no voting, keeps, completion | [ ] | Core loop; two-browser walkthrough |
| M4 | History & favorites signal (`times_kept`) | [ ] | |
| M5 | Hardening, polish, docs, run instructions | [ ] | Definition-of-done check |

Detailed build plan: `docs/PLAN-v1-mvp.md` · Scope & stop criteria: `CHARTER.md`

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Planning refinements & richer library**: recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, re-run last week, meal photos, lunch starter set, better filtering, looser keep rules if needed.
- **v2 — AI-assisted recipe intake & discovery**: parse recipe photos/links into structured recipes; evidence-based recipe discovery; favorites surfacing from `times_kept`; preference inference; adaptations; probation pool.
- **Later / explore**: grocery list generation (explicitly out of MVP), pantry mode, hosted multi-household + accounts, mobile apps, calendar/recurring rhythm, integrations, dice-ritual resurrection, data export.

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-26** — **Plan 1 committed.** Charter, v1 MVP build plan (weekly planning sessions, pre-seeded library), and post-MVP stubs; legacy spreadsheet moved to `reference/`; seed data generated (155 meals); architecture: backend, VPS-hosted. Awaiting charter approval.
