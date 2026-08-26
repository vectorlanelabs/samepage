# Dev Log

Chronological record of work on Dinner Decider. Oldest at top.

## 2026-08-26 — Planning pass (no code shipped)

- **Read** the repo: `README.md` (product concept: common-ground voting + dice roll, V1/V1.5/V2 sketch) and `D20 Dinner Decider.xlsx` (legacy data).
- **Spreadsheet audit**: 8 tabs × up to 20 meals (~155 named meals); `Times Rolled` counts on ~35 rows; 4 recipe URLs; takeout entries; one exact duplicate (`Chicken parm` in Tab 1 & 2); Sheet8 has 5 empty slots; two `(LC)`-suffixed entries. Full audit: `reference/README.md`.
- **Checks against the family**: Pips' room-code pattern (`WORD-####` via `generateCode()`) confirmed — Dinner Decider round codes mirror it with a food-themed word list.
- **Created**: `CHARTER.md` (scope, non-goals, locked decisions, DoD, stop criteria), `ROADMAP.md`, `docs/PLAN-v1-mvp.md` (full MVP build plan: data model, routes, common-ground algorithm, import spec, M0–M5), `docs/POST-V1.md` (v1.5 / v2 / later stubs), `CLAUDE.md` (implementer constraints), `REQUESTS.md`, `.gitignore`.
- **Reorganized**: legacy spreadsheet moved to `reference/` with provenance note.
- **Status**: committed & pushed. **Awaiting Charlie's charter approval before M0.**

## 2026-08-26 — Correction cycle (Charlie's direction — no code shipped)

- **Product shape changed**: the app is now a **weekly planning session**, not a dice-roll. The household sets lunch + dinner targets; the app serves 15–20-meal batches (same list for everyone); private **binary yes/no** votes; unanimous-yes meals kept; batches repeat until targets met.
- **Removed from MVP**: dice ritual, "not-tonight" vote scale, pool modes, import UI/CLI, `legacy_rolls` (Times Rolled column ignored).
- **Added**: meal `type` (lunch/dinner/both) with per-track targets; iterative batch lifecycle (`batch`, `batch_meal.kept`, `vote`); kept-meal records (`times_kept`, `last_kept_at`) as the favorites signal; tags/categories as AI-discovery hooks.
- **Pre-seeding**: generated and committed `seed/meals.json` (155 meals, 8 categories, 4 recipe URLs with embedded names cleaned, 10 takeout-tagged, chicken-parm dup noted). No import feature — the spreadsheet is a one-time source.
- **Docs updated**: CHARTER, ROADMAP, `docs/PLAN-v1-mvp.md` (full rewrite), `docs/POST-V1.md` (recipe intake is now a future AI step per Charlie), `reference/README.md`, README banner, REQUESTS.
- **Blocked**: `CLAUDE.md` rewrite is a protected file — pending Charlie's explicit OK (it still references the old import spec; the plan it points to is corrected, so no danger).
- **Status**: committed & pushed. **Still awaiting charter approval before M0.**

## 2026-08-26 — Architecture decision (Charlie's question: backend or not?)

- Charlie asked whether a backend is warranted (original concept floated "no backend"; library may grow large as the family recipe keeper; AI connectivity security matters).
- **Decision: backend, self-hosted local** (FastAPI + SQLite — the plan's existing shape, now explicitly justified). Reasons: (1) private simultaneous voting needs server-enforced state, (2) the library is durable family data (recipe keeper replacing the kitchen notebook), (3) AI keys must never live in client code, (4) data-size headroom is a non-issue for SQLite with a file-based image store and a Postgres path via SQLAlchemy. No-backend only fits a single-device, throwaway, no-privacy app.
- Plan §7 gained a "Why a backend" section; CHARTER notes the recipe-keeper durability framing; POST-V1 adds library export/backup (v1.5) and server-side-only AI keys (v2); REQUESTS tracks the export item.
- **Status**: committed & pushed. **Still awaiting charter approval before M0.**
