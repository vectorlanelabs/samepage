# Dev Log

Chronological record of work on Dinner Decider. Oldest at top.

## 2026-08-26 — Plan 1 (day 0)

- **Read** the repo: `README.md` (product concept — replace the D8/D20 spreadsheet-and-dice ritual, which "narrows the list but does not really solve the decision problem", with consensus voting) and `D20 Dinner Decider.xlsx` (the legacy data).
- **Audited the spreadsheet**: 8 tabs × up to 20 meals (~155 named meals); 4 recipe URLs (2 standalone cells, 2 embedded in meal names); 10 takeout entries; one exact duplicate ("Chicken parm" ×2); Sheet8 has 15 of 20 slots; `Times Rolled` column noted and deliberately ignored.
- **Scope refined with Charlie** (day-0 planning, not iterations): weekly planning sessions — set lunch/dinner targets; iterative 15-meal yes/no batches (same list for everyone, private votes); unanimous-yes meals kept until targets met. Binary votes. No dice (the thing being replaced). Grocery list out of scope. Library pre-seeded (no import feature). Kept-meal records (`times_kept`) seed favorites. Tags/categories as AI hooks. Recipes arrive via a future AI step (photo/link → recipe).
- **Architecture decided**: backend (FastAPI + SQLite), **VPS-hosted** on Charlie's Hostinger VPS behind HTTPS; single household passphrase as the access gate; daily DB backups — the library is the family recipe keeper (replacing the kitchen notebook).
- **Produced**: `CHARTER.md` (pending approval), `ROADMAP.md`, `docs/PLAN-v1-mvp.md`, `docs/POST-V1.md`, `CLAUDE.md`, `REQUESTS.md`, `seed/meals.json` (155 meals) + `seed/README.md`, `reference/README.md`; README gained a pointer to the operative docs.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Initial plan review applied

- **Read** `docs/INITIAL-PLAN-REVIEW.md` (12 findings: 6 required, 3 doc cleanup, 3 recommended). **All 12 accepted** and applied to the docs.
- **Substantive changes**: lobby/roster-freeze phase (late join disallowed; unanimity = explicit yes from every roster member); Alembic migrations from M0; WAL-safe backups (`VACUUM INTO` / backup API) with restore verification in M5; curated 27-meal `both` seed subset so the lunch track is populated (review option A); `Person.is_admin` + hashed PINs (PBKDF2) + secure cookies/origin checks + deactivate-not-delete; strengthened privacy invariant (individual votes never exposed in the normal UI, before or after close); batch size fixed at 15; idempotent session transitions; recipe-use experience (cooking view, printing) attached to v2 intake; README rewritten for the real product, original concept moved to `docs/ORIGINAL-CONCEPT.md`; post-v1 deployment wording corrected (v1 is already VPS-hosted).
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Majority-vote host acceptance (Charlie's change)

- **Change**: unanimous-yes meals stay auto-kept, but **majority-yes meals (non-unanimous, `yes > no`, ties excluded) are now shown in the batch results with aggregate counts** — everyone sees them, and the **host (session starter) may accept** them while slots remain.
- **Locked mechanics**: unanimous auto-kept first, majority offered after (capped by remaining slots; over-target resolves unanimous first); accepted majority meals recorded as `kept_by='host'` and count toward targets + `times_kept`; **privacy invariant unchanged** — aggregate counts only, individual votes never exposed; 2-person rosters have no majority (feature engages with 3+ voters).
- **Docs updated**: CHARTER (core use case, mechanic, D5/D9/D13, DoD), PLAN (header, D5/D9/D13, US5/US10, `batch_meal.kept_by`, §9.4–9.6, routes, tests, risks, open questions, M3), README, ROADMAP, CLAUDE.md, REQUESTS.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — AI lives outside the app (Charlie, with Claude Design)

- **Decision (D17)**: Dinner Decider never runs AI. It exposes a **token-authenticated JSON API (`/api/v1`, Bearer `DD_API_KEY`) + FastMCP server** (same auth) so Charlie's AI tools (ChatGPT/Claude/Hermes) can import meals/recipes and run discovery/trend analysis via MCP. No LLM keys, no in-app AI, now or later — eliminates the entire in-app AI build.
- **New milestone M6 — External API & MCP** (part of v1, not M0): meals/taxonomy CRUD, sessions/stats (aggregate-only — no raw per-person votes in any API response), MCP tools over `/mcp`.
- **Seeded recipe links**: default is **Option B** — leave the seed as-is; the 4 linked recipes become the first real MCP imports at M6, proving the path end-to-end. Option A (parse at seed time) available.
- **Docs updated**: CHARTER (mechanic, non-goals, D17, M6, DoD), PLAN (header, scope, D17, layout, §7.1, §8.1 API surface, M6, tests, risks, open questions), POST-V1 (v2 rewritten as external intelligence; recipe-use UI moved to v1.5), ROADMAP, README, CLAUDE.md, REQUESTS.
- **Status**: committed & pushed. Awaiting charter approval before M0.

## 2026-08-26 — Charter approved; M0 cycle 1 starts

- Charlie **fully approved the charter** and stepped away; the autonomous dev loop is now running. No further questions will be asked — REQUESTS.md is the only channel.
- **Design handoff ingested** (`Design Handoff/`): high-fidelity reference (10 screens, all v1 views) + `Dinner Decider.dc.html` prototype + design tokens (Fredoka/Nunito Sans, oklch palette: purple primary 300, terracotta dinner 25, green lunch 140; radii 999/24/16/12; shadows; desktop-first responsive with breakpoints; sidebar → top bar below 900px). Production = FastAPI+Jinja2+HTMX recreation; the prototype's client-side state is NOT copied. Fidelity: colors/type/spacing/copy final.
- **M0 scope locked** (plan §11): pyproject/uv scaffold, settings (DD_DB_PATH/SECRET/ACCESS_KEY/API_KEY/PORT/ENV), full §6 models, Alembic initial migration, FastAPI skeleton + session/origin-check middleware, design-system base template + home screen, CI. Design system rides in T0.4 (base template + static).
- **Safety net scheduled**: hourly resume-the-loop cron (repo is the memory; TUI delivery is local-only).
- **Status**: M0 dispatched to implementer (deepseek-v4-flash). Next: independent verify → adversarial review (strong-model override) → land.
