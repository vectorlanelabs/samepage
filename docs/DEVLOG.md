# Dev Log

Chronological record of work on Dinner Decider. Oldest at top.

## 2026-08-26 — Plan 1 (day 0)

- **Read** the repo: `README.md` (product concept — replace the D8/D20 spreadsheet-and-dice ritual, which "narrows the list but does not really solve the decision problem", with consensus voting) and `D20 Dinner Decider.xlsx` (the legacy data).
- **Audited the spreadsheet**: 8 tabs × up to 20 meals (~155 named meals); 4 recipe URLs (2 standalone cells, 2 embedded in meal names); 10 takeout entries; one exact duplicate ("Chicken parm" ×2); Sheet8 has 15 of 20 slots; `Times Rolled` column noted and deliberately ignored.
- **Scope refined with Charlie** (day-0 planning, not iterations): weekly planning sessions — set lunch/dinner targets; iterative 15–20-meal yes/no batches (same list for everyone, private votes); unanimous-yes meals kept until targets met. Binary votes. No dice (the thing being replaced). Grocery list out of scope. Library pre-seeded (no import feature). Kept-meal records (`times_kept`) seed favorites. Tags/categories as AI hooks. Recipes arrive via a future AI step (photo/link → recipe).
- **Architecture decided**: backend (FastAPI + SQLite), **VPS-hosted** on Charlie's Hostinger VPS behind HTTPS; single household passphrase as the access gate; daily DB backups — the library is the family recipe keeper (replacing the kitchen notebook).
- **Produced**: `CHARTER.md` (pending approval), `ROADMAP.md`, `docs/PLAN-v1-mvp.md`, `docs/POST-V1.md`, `CLAUDE.md`, `REQUESTS.md`, `seed/meals.json` (155 meals) + `seed/README.md`, `reference/README.md`; README gained a pointer to the operative docs.
- **Status**: committed & pushed. Awaiting charter approval before M0.
