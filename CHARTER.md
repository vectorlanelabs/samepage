# Dinner Decider — Project Charter

| | |
|---|---|
| **Status** | **Pending Charlie's approval** (Plan 1 committed 2026-08-26; implementation not started) |
| **Repo** | `vectorlanelabs/dinnerdecider` |
| **Type** | Household web app — web-first, VPS-hosted |
| **Budget** | 25 directed cycles for v1 MVP (or milestone-list completion, whichever comes first) |
| **Source docs** | `README.md` (original concept) · `reference/D20 Dinner Decider.xlsx` (legacy data) · `docs/PLAN-v1-mvp.md` (operative build plan) |

## Target user

One household — Charlie's family (roughly 2–6 people who plan meals together). The household sits down (weekly) to decide the coming week's meals; one technically comfortable person (Charlie) runs and administers the app. No accounts, no installs, no onboarding ceremony. **Long-term, the app is expected to become the family's recipe keeper (replacing the hand-written dinner notebook in the kitchen), so the meal library is treated as durable family data, not throwaway app state.**

## Core use case

**Weekly meal planning.** The household opens a planning session, sets the number of dinners and lunches needed for the week, and the app runs the decision loop:

1. It presents a batch of **15–20 meal options** (the *same list for every participant*).
2. Each person privately votes **yes / no** on each option.
3. Meals where **everyone said yes** are kept for the week.
4. The app presents another batch, and repeats, **until the target counts are met**.

The output is the week's meal plan — which then feeds grocery planning done elsewhere. **Grocery-list building is explicitly out of scope.**

## Core mechanic

- **Consensus by unanimous yes, in batches.** Binary yes/no, iterated until the week is planned. The D8/D20 spreadsheet-and-dice ritual is the thing being replaced — it has no role in the app.
- **Private voting.** Votes are hidden until a batch closes; only the unanimous-yes results are shown. No tallies, no "who rejected what".
- **Pre-seeded library.** The legacy spreadsheet's meals (and the recipe links it has) ship with the app. No import feature.
- **Favorites emerge from data.** Every kept meal is recorded (`times_kept`), so favorites can be determined from successful matches over time.
- **A real backend** (FastAPI + SQLite, **VPS-hosted** on Charlie's Hostinger VPS behind HTTPS) — required for private simultaneous voting, durable family data, and future AI key security. Rationale in plan §7, deployment in §7.1.

## Non-goals (v1 MVP)

- **Grocery list / shopping list** — out of scope by explicit direction (the decision feed is the product).
- **Recipe ingestion** — no URL scraping, no photo parsing. (A future AI step will parse recipe images/links into recipes — see `docs/POST-V1.md`.)
- **No import UI/CLI** — data is pre-seeded; the spreadsheet is a one-time source, not a user flow.
- **No dice-roll ritual** in the MVP flow.
- **No AI of any kind** in MVP (tags/categories exist as hooks for later discovery).
- **No accounts / authentication / multi-household hosting** (identity = name + PIN).
- **No preference learning** beyond raw kept-meal records and stored votes.
- **No mobile apps**, no push notifications, no realtime sync beyond simple page refresh/polling.

## Locked decisions (reviewable — detail in `docs/PLAN-v1-mvp.md` §3)

| # | Decision | Choice |
|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 · HTMX + minimal vanilla JS. **No frontend build step, no Node.** |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN. Device identity via signed cookie session. |
| D3 | **Session codes** | `WORD-####` (e.g. `TACO-1234`), food-themed word list — same spirit as Pips' `generateCode()`. |
| D4 | **Vote scale** | Binary **yes / no** only. |
| D5 | **Keep rule** | A meal is kept iff **every participant who voted in the batch voted yes on it**. Kept meals count toward that track's target. |
| D6 | **Batch assembly** | 15–20 options per batch (default 15, set at session creation); drawn from the active track's pool (meal type matches track, or `both`), never repeating a meal already voted on in the session. |
| D7 | **Pre-seeding** | `seed/meals.json` (committed, generated from the spreadsheet) + `scripts/seed.py` loader. **No import feature.** |
| D8 | **Tags & categories** | First-class meal metadata, seeded (`takeout` auto-tag; `Tab 1..8` categories) — primarily hooks for future AI discovery. |
| D9 | **Favorites signal** | `meal.times_kept` + `last_kept_at` updated on every keep; raw votes stored. Favorites are *derived* later, not manually starred. |
| D10 | **Tracks** | Meals are typed `lunch` / `dinner` / `both`. Sessions set a target per track; tracks run **dinner first, then lunch**. |
| D11 | **Seed dedupe** | Loader dedupes by normalized name (casefold + collapsed whitespace); exact duplicates logged and skipped (e.g. the two "Chicken parm" rows). |
| D12 | **Polling, not websockets** | Page refresh / short poll on session pages. |
| D13 | **Over-target keeps** | If unanimous-yes meals exceed remaining slots, the starter chooses which to keep (multi-select, max = remaining). Kept = counted; dropped = recorded as voted, not kept. |
| D14 | **Deployment** | **VPS-hosted** (Hostinger) behind HTTPS (Caddy auto-TLS); single household passphrase (`DD_ACCESS_KEY`, once per device) as the access gate — no accounts, PINs unchanged; daily DB backup + provider snapshots (family recipes are irreplaceable). Reviewable. |

## Milestones (v1 MVP)

See `docs/PLAN-v1-mvp.md` §11 for task detail.

| ID | Milestone | Status |
|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, session, CI | [ ] |
| M1 | Household profiles: people, PINs, device sessions | [ ] |
| M2 | Meal library CRUD + pre-seeded data (seed loader + seed tests) | [ ] |
| M3 | Planning sessions & voting: targets, batches, yes/no voting, keeps, completion | [ ] |
| M4 | History & favorites signal | [ ] |
| M5 | Hardening, polish, docs, run instructions | [ ] |

## Definition of done (v1 MVP)

From household devices **anywhere** (the app is on the VPS behind HTTPS — phones just need a browser), with the pre-seeded library:

- A planning session starts with lunch and dinner targets set.
- Everyone joins by code, votes **yes/no** on the same 15–20-option batches, privately.
- Unanimous-yes meals are kept; batches continue **until the week's targets are met** (over-target keeps are resolved by choosing).
- Kept meals are recorded (`times_kept`, `last_kept_at`), and past sessions are viewable in history.
- Meals have title, type, category, tags, and recipe (link where the spreadsheet had one).
- Meals can be added, edited, and archived manually.

## Stop criteria

- **Budget exhausted** (25 cycles) → land whatever is in flight, leave the tree clean and pushed, ask for renewal.
- **The household stops using it** after a fair trial (2–3 weekly planning sessions).
- **The batch loop doesn't actually reduce planning friction** (e.g. unanimous-yes keeps are too rare to make progress) → pivot to looser keep rules or re-scope, not a fourth attempt at the same thing.
- **Charlie's call** at any point.

## Approval

This charter is **pending Charlie's sign-off**. Implementation cycles (M0+) begin only after approval. Every locked decision is reviewable — feedback welcome before M0.
