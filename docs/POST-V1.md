# Post-MVP — Stub Descriptions

> **Intent statements, not specs.** Each section gets a full plan document (like `docs/PLAN-v1-mvp.md`) when its trigger condition fires. Nothing here is committed to ship; ordering is a suggestion, not a schedule. The MVP ships first.

---

## v1.5 — Planning refinements & a richer library

**What:** Make the weekly planning loop smarter and the library richer — still no AI.

**Trigger:** MVP in consistent household use for ~1 month (a few real weekly sessions), or Charlie asks for any item.

**Stub scope:**
- **Recency weighting**: batch assembly favors meals not kept recently (`last_kept_at`), so the pool rotates.
- **Stale-meal suggestions**: meals never kept after many appearances surfaced for archive/retag — recommendations, never silent deletion.
- **Per-person hard constraints**: "never suggest this meal to this person" (person-level), surfaced as pre-filtered options — the binary vote stays binary.
- **Planned-week view**: calendar-style view of the week's kept meals (the session already produces the plan; this renders it).
- **Re-run last week**: start a new session preloaded with last week's targets and settings.
- **Meal photos**: upload flow (MVP has no photos at all).
- **Library export/backup**: JSON export of meals + recipes, and better backup docs — the library is the family recipe keeper, so data portability is hygiene.
- **Lunch library starter set**: _resolved in the v1 seed — a curated 27-meal `both` subset populates the lunch track from install; this item now only covers a bigger/later curated expansion._
- **Recipe-use experience** (review #9): the UI that makes stored recipes usable — **clean cooking view** (large-type ingredients and steps), **print-friendly layout/stylesheet** (first-class printing), and household notes/substitutions. Intake itself is external (MCP); the use experience is in-app.
- **Better library filtering**: multi-tag, type, "kept N+ times" filters.
- **More keep rules**: e.g. "everyone yes OR at least N yes with no hard-no" — only if the unanimous rule stalls in practice (tracked, not improvised).

**Dependencies:** MVP data model only. No AI.

---

## v2 — External intelligence via API & MCP (no in-app AI)

**What:** AI capability is exercised **entirely outside the app**, through its token-authenticated API + MCP server (D17). The app stays a data-rich, AI-free product; Charlie's AI tools (ChatGPT/Claude/Hermes) do the thinking.

**Trigger:** M6 shipped (API/MCP live in v1), plus meaningful kept-meal/vote data. **No LLM integration work will ever be built into the app** — if a capability can be exercised through the API/MCP, it is, by definition, external.

**Stub scope (all executed from AI tools via MCP, not built into the app):**
- **Recipe parsing** (photo or link → structured recipe): done by Charlie's AI tools through the MCP tools (`create/update meal`, recipe fields). The **4 seeded recipe links are the first real proof** (M6, Option B). LLM keys live in Charlie's tools, never in the codebase.
- **Discovery & trend analysis**: MCP queries over `/api/v1/stats` and library data — `kept_by` mix, `times_kept`, yes-rates, categories/tags, recency — to surface "meals worth retrying", "haven't had lately", and candidate new dinners.
- **Favorites surfacing**: derived externally from `times_kept`/`kept_by`/recency, presented by Charlie's tools.
- **Preference inference**: external analysis over aggregate vote/keep data — hypotheses, inspectable and correctable (corrections applied via MCP updates, e.g. retagging).
- **Recipe adaptation**: external suggestions for near-matches; applied explicitly via MCP updates (never silent).
- **Probationary pool**: an app-side flag/tag on new meals, exercised via MCP.

**Dependencies:** M6 API/MCP (v1), recipe-use experience UI (v1.5), accumulated data. **No LLM provider, no budget line, no keys — the app never touches AI.**

---

## Later / explore (not committed)

One-liners on purpose — each gets a PLAN doc only if/when it becomes real:

- **Grocery list generation from the planned week** — explicitly out of MVP scope (the decision feed is the product); the natural extension since planning exists to feed grocery shopping.
- **Pantry mode**: "meals using ingredients on hand" as a session filter.
- **Multi-household hosting + real accounts + public/self-service deployment**: only if remote participation beyond the household becomes useful (v1 is already VPS-hosted).
- **Mobile apps**: native or PWA — responsive web probably suffices for a long time.
- **Meal planning calendar / recurring weekly rhythm** beyond single sessions.
- **Integrations**: grocery delivery, kitchen tablets / smart displays.
- **"Used to work, fell out of favor" detection**: meals whose keeps decayed over time.
- **Archived-meal reconsideration**: periodically re-offer archived meals.
- **The dice ritual, resurrected**: optional D20-flavored pick among kept meals, for fun (the original spreadsheet ritual — Charlie's call if it comes back).
- **Data export / portability.**

---

*Nothing in this file is a promise. If an item stops making sense, it gets deleted — that's a success, not a loss.*
