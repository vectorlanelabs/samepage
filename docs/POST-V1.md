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
- **Lunch library starter set**: a curated lunch/lunch-dinner set so the lunch track starts populated.
- **Better library filtering**: multi-tag, type, "kept N+ times" filters.
- **More keep rules**: e.g. "everyone yes OR at least N yes with no hard-no" — only if the unanimous rule stalls in practice (tracked, not improvised).

**Dependencies:** MVP data model only. No AI.

---

## v2 — AI-assisted recipe intake & discovery

**What:** Two AI jobs, both serving the meal pool — the app never gets a "personality" (README principle: precision over novelty).

**Trigger:** v1.5 in steady use with meaningful kept-meal/vote data, and Charlie greenlights AI spend. This is the most likely place to overbuild — the charter's non-goal discipline applies hardest here.

**Stub scope:**
- **Recipe intake (AI)**: parse a **photo of a recipe or a link to one online** into a structured recipe (title, ingredients, instructions, servings, timing) — Charlie's stated direction. Stores a clean household copy + original source.
- **Recipe discovery (AI)**: suggest meals the household has a meaningful chance of accepting, each suggestion self-explaining from actual evidence (kept meals, yes/no votes, tags, categories). Ten plausible suggestions beat ten bizarre ones.
- **Favorites surfacing**: derive favorites from `times_kept` + recency (the MVP already records successful matches).
- **Preference inference**: ingredient/texture/cuisine patterns from real votes — hypotheses, inspectable and correctable.
- **Recipe adaptation**: near-matches made acceptable (e.g. "household tends to reject cooked onions — make it with onion powder") — explicit, never silent.
- **Probationary pool**: new/AI-suggested meals enter a probation pool before becoming regular candidates.

**Dependencies:** v1.5 library, accumulated votes/keeps, LLM provider + budget decision (deferred to planning time). **AI provider keys live server-side only — never in client code** (architecture, plan §7).

---

## Later / explore (not committed)

One-liners on purpose — each gets a PLAN doc only if/when it becomes real:

- **Grocery list generation from the planned week** — explicitly out of MVP scope (the decision feed is the product); the natural extension since planning exists to feed grocery shopping.
- **Pantry mode**: "meals using ingredients on hand" as a session filter.
- **Hosted deployment + multi-household + real accounts**: only if remote participation becomes useful.
- **Mobile apps**: native or PWA — responsive web probably suffices for a long time.
- **Meal planning calendar / recurring weekly rhythm** beyond single sessions.
- **Integrations**: grocery delivery, kitchen tablets / smart displays.
- **"Used to work, fell out of favor" detection**: meals whose keeps decayed over time.
- **Archived-meal reconsideration**: periodically re-offer archived meals.
- **The dice ritual, resurrected**: optional D20-flavored pick among kept meals, for fun (the original spreadsheet ritual — Charlie's call if it comes back).
- **Data export / portability.**

---

*Nothing in this file is a promise. If an item stops making sense, it gets deleted — that's a success, not a loss.*
