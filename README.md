# Dinner Decider

A household web app for planning a week of meals that everyone will actually eat — replacing the D8/D20 spreadsheet-and-dice ritual, which narrows the list but never solves the decision problem.

## What it does

The household runs a **weekly planning session**:

1. Someone starts a session and sets how many **dinners** and **lunches** the week needs.
2. The app serves a batch of **15 meal options** — the same list for every participant.
3. Each person votes **yes / no** privately.
4. Meals where **everyone said yes** are kept for the week.
5. The app serves another batch, and repeats, **until the week's targets are met**.

Votes stay private — individual votes are never shown, before or after a batch closes. Only the outcome is revealed: the meals everyone agreed on. Every kept meal is recorded (`times_kept`), which is how favorites will be determined from actual use.

The output is the week's meal plan, which then feeds grocery planning done elsewhere. **Dinner Decider does not build the grocery list.**

## What's in v1

- Pre-seeded meal library (155 meals from the household spreadsheet, including its recipe links; lunch-capable meals tagged for the lunch track)
- Household profiles (name + PIN, no accounts)
- Weekly planning sessions: lunch/dinner targets → iterative yes/no batches → unanimous-yes keeps until the week is planned
- Kept-meal records and session history
- Manual meal add/edit/archive

The meal library is expected to become the family's recipe keeper over time — it's durable data, backed up on the server.

## What's after v1

- **v1.5** — recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, meal photos, looser keep rules if needed
- **v2** — AI-assisted recipe intake (photo or link → structured recipe) with a clean cooking view and printing, plus evidence-based recipe discovery
- **Later** — grocery-list generation, pantry mode, multi-household hosting, mobile apps, integrations

Full intent statements: [`docs/POST-V1.md`](docs/POST-V1.md).

## Project docs

- **Charter** — [`CHARTER.md`](CHARTER.md) — scope, non-goals, locked decisions, definition of done, stop criteria *(pending approval)*
- **Roadmap** — [`ROADMAP.md`](ROADMAP.md) — milestone status
- **v1 MVP build plan** — [`docs/PLAN-v1-mvp.md`](docs/PLAN-v1-mvp.md) — data model, routes, session algorithm, seed spec, M0–M5
- **Post-MVP stubs** — [`docs/POST-V1.md`](docs/POST-V1.md)
- **Original concept** — [`docs/ORIGINAL-CONCEPT.md`](docs/ORIGINAL-CONCEPT.md) — the full narrative that started this project (preserved; not operative)
- **Legacy spreadsheet (read-only seed source)** — [`reference/D20 Dinner Decider.xlsx`](reference/D20%20Dinner%20Decider.xlsx), provenance in [`reference/README.md`](reference/README.md)

## Run it

_Setup and run instructions land with M5 (local dev: `uv sync` → `uv run scripts/seed.py` → `uv run uvicorn app.main:app`; production: VPS behind HTTPS per `docs/PLAN-v1-mvp.md` §7.1)._

## Success criterion

Dinner Decider succeeds if the household can answer **"what are we eating tonight?"** faster, with less negotiation, while gradually building a better list of meals everyone can actually agree on.
