# Dinner Decider — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## v1 MVP (current target)

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, session, CI | [ ] | First cycle after charter approval |
| M1 | Household profiles: people, PINs, device sessions | [ ] | |
| M2 | Meal library CRUD + legacy spreadsheet import (CLI) | [ ] | Biggest slice; dedupe report |
| M3 | Rounds & voting: start, join, vote, common ground, roll/decide | [ ] | Core loop; two-browser walkthrough |
| M4 | History & favorites | [ ] | |
| M5 | Hardening, polish, docs, run instructions | [ ] | Definition-of-done check |

Detailed build plan: `docs/PLAN-v1-mvp.md` · Scope & stop criteria: `CHARTER.md`

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Recipes & a richer library**: URL/paste recipe ingestion, clean cooking view, first-class printing, photo upload, recency weighting, stale-meal suggestions, hard-no constraints, more common-ground rules.
- **v2 — Learning & AI**: preference modeling, AI recipe discovery (precision over novelty), AI normalization, inferred taste patterns (correctable hypotheses), suggested adaptations, probationary pool.
- **Later / explore**: pantry mode, hosted multi-household + accounts, mobile apps, meal planning, grocery lists, scanned-recipe intake, integrations.

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-26** — Planning pass. Charter, v1 MVP build plan, and post-MVP stubs committed; legacy spreadsheet moved to `reference/`. Awaiting charter approval.
