# Dinner Decider — Project Charter

| | |
|---|---|
| **Status** | **Approved by Charlie 2026-08-26 — M0+M1 complete, M2 next** (autonomous dev loop running) |
| **Repo** | `vectorlanelabs/dinnerdecider` |
| **Type** | Household web app — web-first, VPS-hosted |
| **Budget** | 25 directed cycles for v1 MVP (or milestone-list completion, whichever comes first) |
| **Source docs** | `README.md` (original concept) · `reference/D20 Dinner Decider.xlsx` (legacy data) · `docs/PLAN-v1-mvp.md` (operative build plan) |

## Target user

One household — Charlie's family (roughly 2–6 people who plan meals together). The household sits down (weekly) to decide the coming week's meals; one technically comfortable person (Charlie) runs and administers the app. No accounts, no installs, no onboarding ceremony. **Long-term, the app is expected to become the family's recipe keeper (replacing the hand-written dinner notebook in the kitchen), so the meal library is treated as durable family data, not throwaway app state.**

## Core use case

**Weekly meal planning.** The household opens a planning session, sets the number of dinners and lunches needed for the week, and the app runs the decision loop:

1. It presents a batch of **15 meal options** (the *same list for every participant*).
2. Each person privately votes **yes / no** on each option.
3. Meals where **everyone said yes** are kept for the week; meals with a **majority** are also shown in the results, and the **host can accept** any of them.
4. The app presents another batch, and repeats, **until the target counts are met**.

The output is the week's meal plan — which then feeds grocery planning done elsewhere. **Grocery-list building is explicitly out of scope.**

## Core mechanic

- **Consensus by unanimous yes, in batches — with a host escape hatch.** Binary yes/no, iterated until the week is planned. **Unanimous-yes meals are kept automatically; majority-yes meals (non-unanimous) are shown in the results with aggregate counts, and the host may accept them** if the household agrees. The D8/D20 spreadsheet-and-dice ritual is the thing being replaced — it has no role in the app.
- **Private voting.** Individual votes are **never exposed in the normal UI, before or after a batch closes** — only aggregate outcomes are shown (meals everyone agreed on, no-match state, kept meals). Raw votes stay server-side for future learning.
- **Pre-seeded library.** The legacy spreadsheet's meals (and the recipe links it has) ship with the app. No import feature.
- **Favorites emerge from data.** Every kept meal is recorded (`times_kept`), so favorites can be determined from successful matches over time.
- **AI lives outside the app.** Dinner Decider never runs AI — it exposes a token-authenticated **JSON API + MCP server** so Charlie's AI tools (ChatGPT/Claude/Hermes) can import meals/recipes, look for trends, and drive discovery. No LLM keys in the codebase, now or later.
- **A real backend** (FastAPI + SQLite, **VPS-hosted** on Charlie's Hostinger VPS behind HTTPS) — required for private simultaneous voting, durable family data, and a safe external API surface for AI tools. Rationale in plan §7, deployment in §7.1.

## Non-goals (v1 MVP)

- **Grocery list / shopping list** — out of scope by explicit direction (the decision feed is the product).
- **Recipe parsing/ingestion** — no URL scraping, no photo parsing, **no in-app AI of any kind, now or later**: recipe parsing (photo/link → recipe) and discovery/trend analysis are done *externally* by Charlie's AI tools through the app's API/MCP (D17).
- **No import UI/CLI** — data is pre-seeded; the spreadsheet is a one-time source, not a user flow.
- **No dice-roll ritual** in the MVP flow.
- **No AI features built into the app** — the app provides data + mutation APIs; intelligence is external (see D17). Tags/categories exist as hooks for that external discovery.
- **No accounts / authentication / multi-household hosting** (identity = name + PIN).
- **No preference learning** beyond raw kept-meal records and stored votes.
- **No mobile apps**, no push notifications, no realtime sync beyond simple page refresh/polling.

## Locked decisions (reviewable — detail in `docs/PLAN-v1-mvp.md` §3)

| # | Decision | Choice |
|---|---|---|
| D1 | **Stack** | Python 3.12+ · uv · FastAPI · SQLAlchemy 2.x · SQLite · Jinja2 · HTMX + minimal vanilla JS. **No frontend build step, no Node.** |
| D2 | **Identity** | No accounts. `Person` = name + 4-digit PIN, **stored hashed** (PBKDF2, per-person salt — stdlib, no new deps). Device identity via signed cookie session. |
| D3 | **Session codes** | `WORD-####` (e.g. `TACO-1234`), food-themed word list — same spirit as Pips' `generateCode()`. |
| D4 | **Vote scale** | Binary **yes / no** only. |
| D5 | **Keep rule & roster** | The participant roster **freezes when the starter begins voting** (lobby phase first; late join is disallowed in v1). **Unanimous**: a meal qualifies automatically iff **every required participant has an explicit `yes` vote**. **Majority** (host-optional): non-unanimous meals where `yes > no` (ties excluded; missing votes count as `no` on manual close) are shown in the results with **aggregate counts only** — the **host (session starter) may accept** them while slots remain. Auto-close requires every roster member to vote on every meal; manual close treats missing votes as `no`. |
| D6 | **Batch assembly** | **15 options per batch, fixed** (an implementation tuning parameter, not a household setup choice — revisit after real use); drawn from the active track's pool (meal type matches the track, or `both`), never repeating a meal already voted on in the session. |
| D7 | **Pre-seeding** | `seed/meals.json` (committed, generated from the spreadsheet) + `scripts/seed.py` loader. **No import feature.** |
| D8 | **Tags & categories** | First-class meal metadata, seeded (`takeout` auto-tag; `Tab 1..8` categories) — primarily hooks for future AI discovery. |
| D9 | **Favorites signal** | `meal.times_kept` + `last_kept_at` updated on every keep (unanimous **and** host-accepted); `batch_meal.kept_by` (`unanimous`\|`host`) records how it was kept; raw votes stored. Favorites are *derived* later, not manually starred. |
| D10 | **Tracks** | Meals are typed `lunch` / `dinner` / `both`. Sessions set a target per track; tracks run **dinner first, then lunch**. **The seed carries a curated `both` subset (27 meals) so the lunch track is populated from a fresh install.** |
| D11 | **Seed dedupe** | Loader dedupes by normalized name (casefold + collapsed whitespace); exact duplicates logged and skipped (e.g. the two "Chicken parm" rows). |
| D12 | **Polling, not websockets** | Page refresh / short poll on session pages. |
| D13 | **Over-target keeps** | Resolved **unanimous first** (starter chooses which, max = remaining slots). Majority offers are then capped by whatever slots remain; if none, majority meals are recorded as voted, not kept. Kept = counted; dropped = recorded as voted, not kept. |
| D14 | **Deployment** | **VPS-hosted** (Hostinger) behind HTTPS (Caddy auto-TLS); single household passphrase (`DD_ACCESS_KEY`, once per device) as the access gate — no accounts, PINs unchanged; **backups via the SQLite backup API / `VACUUM INTO` (WAL-safe — never a raw copy of a live `.db`), with restore verified in M5**; provider snapshots. Reviewable. |
| D15 | **Migrations** | **Alembic from M0**; every schema change after initial creation ships as a migration (`create_all` is dev/test only). The library is durable family data with a long growth path. |
| D16 | **Administration & security** | `Person.is_admin` gates admin actions (managing people, changing PINs, archiving/unarchiving meals, maintenance ops). Secure cookie flags (`Secure`, `HttpOnly`, `SameSite`) + CSRF/origin checks on state-changing requests; PIN-verify attempt limiting. **People are deactivated, never deleted** — history and referential integrity preserved. |
| D17 | **External API & MCP — AI lives outside the app** | The app exposes a token-authenticated JSON API (`/api/v1`, Bearer `DD_API_KEY`) plus an **MCP server** (FastMCP, same auth) — meal/recipe create/update/archive, library queries, session/history/aggregate stats — so Charlie's AI tools can import meals/recipes and run discovery/trend analysis. **No in-app AI, no LLM keys — now or later.** Raw per-person votes stay server-side; the API exposes aggregates only. Reviewable. |

## Milestones (v1 MVP)

See `docs/PLAN-v1-mvp.md` §11 for task detail.

| ID | Milestone | Status |
|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, **Alembic migrations**, session, CI | [ ] | First cycle after charter approval |
| M1 | Household profiles: people (hashed PINs, admin flag), deactivate-not-delete | [ ] | |
| M2 | Meal library CRUD + pre-seeded data (seed loader + seed tests) | [ ] | `seed/meals.json` already committed |
| M3 | Planning sessions & voting: lobby/roster freeze, targets, batches, yes/no voting, keeps, completion | [ ] | Core loop; two-browser walkthrough |
| M4 | History & favorites signal | [ ] | |
| M5 | Hardening, polish, deployment docs, backup restore check | [ ] | Definition-of-done check |
| M6 | External API + MCP server (for Charlie's AI tools; **no in-app AI**) | [ ] | Proves recipe import + trend queries via MCP |

## Definition of done (v1 MVP)

From household devices **anywhere** (the app is on the VPS behind HTTPS — phones just need a browser), with the pre-seeded library:

- A planning session starts with lunch and dinner targets set; the starter **freezes the roster**, then everyone votes **yes/no** on the same 15-option batches, privately.
- Unanimous-yes meals are kept; **majority-yes meals are shown in the results and the host may accept them**; batches continue **until the week's targets are met** (over-target keeps are resolved by choosing).
- Kept meals are recorded (`times_kept`, `last_kept_at`), and past sessions are viewable in history.
- Meals have title, type, category, tags, and recipe (link where the spreadsheet had one).
- Meals can be added, edited, and archived manually.
- The app exposes an **authenticated API + MCP server**; an AI tool can create a meal/recipe and query session/keep history through it (D17).

## Stop criteria

- **Budget exhausted** (25 cycles) → land whatever is in flight, leave the tree clean and pushed, ask for renewal.
- **The household stops using it** after a fair trial (2–3 weekly planning sessions).
- **The batch loop doesn't actually reduce planning friction** (e.g. unanimous-yes keeps are too rare to make progress) → pivot to looser keep rules or re-scope, not a fourth attempt at the same thing.
- **Charlie's call** at any point.

## Approval

This charter was **approved by Charlie on 2026-08-26** ("charter fully approved"; design handoff in `Design Handoff/`). Implementation cycles (M0+) are authorized and running autonomously. Every locked decision remains reviewable — feedback lands via `REQUESTS.md`.
