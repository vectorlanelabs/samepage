# Dinner Decider — Project Charter

| | |
|---|---|
| **Status** | **Pending Charlie's approval** (plan committed 2026-08-26; implementation not started) |
| **Repo** | `vectorlanelabs/dinnerdecider` |
| **Type** | Household web app — self-hosted, local-network friendly |
| **Budget** | 25 directed cycles for v1 MVP (or milestone-list completion, whichever comes first) |
| **Source docs** | `README.md` (product concept) · `reference/D20 Dinner Decider.xlsx` (legacy data) |

## Target user

One household — Charlie's family (roughly 2–6 people who eat dinner together most nights). Participants vote from phones/browsers around the house; one technically comfortable person (Charlie) runs and administers the app. No accounts, no installs, no onboarding ceremony.

## Core use case

Each night, answer **"what are we eating tonight?"** faster and with less negotiation:

1. Start a round over a pool of candidate meals.
2. Everyone privately votes **yes / not-tonight / no**.
3. Reveal only the meals everyone is willing to eat (common ground).
4. Roll or pick from the survivors.
5. The app remembers what was eaten.

## Core mechanic (from README)

Replace the D8/D20 spreadsheet-and-dice ritual with a lightweight shared decision system that gets better with use. **Randomness is useful only after obviously unacceptable options are removed.** The dice ritual is preserved as a digital flourish for the final selection.

## Non-goals (v1 MVP)

Explicitly out of scope until post-MVP (stubs in `docs/POST-V1.md`):

- **No AI of any kind** — no recipe discovery, preference inference, normalization, or adaptation.
- **No recipe ingestion** — no URL import, paste import, or photo/PDF/scanned intake.
- **No printing**, no photo *upload* (image URL only).
- **No pantry** / "ingredients on hand" pool mode.
- **No accounts / authentication / multi-household hosting** (identity = name + PIN).
- **No preference learning** or statistics beyond raw round history.
- **No mobile apps**, no push notifications, no realtime sync beyond simple page refresh/polling.

## Locked decisions (reviewable — detail in `docs/PLAN-v1-mvp.md` §3)

| # | Decision | Choice |
|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 · HTMX + minimal vanilla JS. **No frontend build step, no Node.** |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN. Device identity via signed cookie session. |
| D3 | **Round codes** | `WORD-####` (e.g. `TACO-1234`), food-themed word list — same spirit as Pips' `generateCode()`. |
| D4 | **Vote scale** | `yes` / `not-tonight` / `no`. Hard-no is a V1.5 item; schema leaves room (extensible enum). |
| D5 | **Common-ground rule (MVP)** | A meal survives iff **every participant who voted in the round voted yes on it**. "Not tonight" excludes the meal tonight but is stored distinctly (neutral for future learning). |
| D6 | **Pool modes (MVP)** | `all` · `category` · `tag` · `favorites` · `not-eaten-recently` (sort) · `surprise` (random 10). |
| D7 | **Import** | CLI script (`scripts/import_legacy.py`): dry-run report → `--apply`. Duplicates flagged, never auto-merged. Categories = `Tab 1..8` (renamable). Known takeout entries auto-tagged. |
| D8 | **Favorites** | Household-level (one list), not per-person. |
| D9 | **History** | Rounds where a meal was decided. Meal `times_cooked` / `last_cooked_at` updated on decision. |

## Milestones (v1 MVP)

See `docs/PLAN-v1-mvp.md` §11 for task detail.

| ID | Milestone | Status |
|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, session, CI | [ ] |
| M1 | Household profiles: people, PINs, device sessions | [ ] |
| M2 | Meal library CRUD + legacy spreadsheet import (CLI) | [ ] |
| M3 | Rounds & voting: start, join, vote, common ground, roll/decide | [ ] |
| M4 | History & favorites | [ ] |
| M5 | Hardening, polish, docs, run instructions | [ ] |

## Definition of done (v1 MVP)

The household can, from their own devices on the home network:

- Import the legacy spreadsheet into the meal library with a reviewable report.
- Start a round; everyone joins by code and votes privately.
- See common-ground survivors and roll or pick dinner.
- Have the app record it, and view history.
- Manually archive meals.

And the README's success criterion holds: **"what are we eating tonight?" is answered faster, with less negotiation, while the household gradually builds a better list of meals everyone can actually agree on.**

## Stop criteria

- **Budget exhausted** (25 cycles) → land whatever is in flight, leave the tree clean and pushed, ask for renewal.
- **The household stops using it** after a fair trial (2–3 weeks of real nights).
- **Common ground is too often empty/unsatisfying** with the default rule — signals a pivot to looser rules (designed for V1.5), not a fourth attempt at the same thing.
- **Charlie's call** at any point.

## Approval

This charter is **pending Charlie's sign-off**. Implementation cycles (M0+) begin only after approval. Every locked decision above is reviewable — corrections welcome before M0.
