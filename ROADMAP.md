# Dinner Decider — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## v1 MVP (current target — corrected direction 2026-08-26)

Product shape: **weekly planning sessions** — set lunch/dinner targets, iterate 15–20-meal yes/no batches (same list for everyone, private votes), keep unanimous-yes meals, repeat until the week is planned. Library **pre-seeded** from the legacy spreadsheet. No dice, no import feature, no grocery list.

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

- **2026-08-26** — Planning pass. Charter, v1 MVP build plan, post-MVP stubs committed; legacy spreadsheet moved to `reference/`.
- **2026-08-26** — **Correction cycle** (Charlie's direction): product is now a weekly planning session (targets for lunch/dinner; iterative 15–20-meal yes/no batches; unanimous-yes kept until targets met). Dice ritual, not-tonight scale, and import feature removed. Library is pre-seeded (`seed/meals.json`, 155 meals, committed); Times Rolled column ignored; kept-meal records (`times_kept`) seed favorites. Awaiting charter approval.
- **2026-08-26** — **Architecture decision**: backend confirmed (FastAPI + SQLite) with explicit rationale in plan §7 (private voting state, durable family data as recipe keeper, AI key security, size headroom). Export/backup tracked as v1.5; AI keys server-side only. Awaiting charter approval.
- **2026-08-26** — **Deployment decision**: **VPS-hosted** (Charlie's Hostinger VPS, HTTPS via Caddy) — not local. Plan §7.1, charter D13 (passphrase access gate), M5 deploy/backup tasks added; CLAUDE.md refreshed. Awaiting charter approval.
