# Post-MVP — Stub Descriptions

> **Intent statements, not specs.** Each section gets a full plan document (like `docs/PLAN-v1-mvp.md`) when its trigger condition fires. Nothing here is committed to ship; ordering is a suggestion, not a schedule. The MVP ships first.

---

## v1.5 — Recipes & a richer library

**What:** Make the library a real recipe keeper and make the rounds smarter without any AI.

**Trigger:** MVP in consistent household use for ~1 month, or Charlie asks for any item.

**Stub scope:**
- **Recipe intake**: paste a recipe URL → extract title/image/ingredients/instructions/servings/timing; paste arbitrary recipe text → normalize into structure; store clean household copy + original source URL.
- **Clean cooking view**: large-type ingredients and steps, no life story, keep-screen-awake where the platform allows.
- **First-class printing**: printable layout that fits cleanly on paper — not an accidental browser printout.
- **Meal photos**: upload flow (MVP is URL-only).
- **Better filtering/categories**: richer category UX, multi-tag filters.
- **"Haven't had this lately" weighting**: recency-weighted random choice (not just the not-recently sort).
- **Automatic stale-meal suggestions**: repeatedly-rejected / never-selected / duplicates surfaced for keep-archive-merge-update — always recommendations, never silent deletion.
- **Hard-no constraints**: per-person "never suggest this" surfaced in rounds (data model already leaves room — enum + constraint table).
- **More common-ground rules**: no-hard-no + ≥N yes; allow one abstention; parents pick among children's accepted meals.
- **Web import UI**: replace/augment the CLI import.
- **Probationary pool** for newly added meals (see open question in the MVP plan).

**Dependencies:** MVP data model (vote enum extensible), no AI needed.

---

## v2 — Learning & AI

**What:** The app starts learning from actual behavior — **precision over novelty** (README: ten bizarre generated recipes nobody will eat are worse than one plausible new dinner).

**Trigger:** v1.5 in steady use with meaningful voting data volume, and Charlie greenlights AI spend. This is the most likely place for the project to overbuild — the charter's non-goal discipline applies here hardest.

**Stub scope:**
- **Preference modeling**: evidence from yes/not-tonight/no/hard-no votes, whether the meal was actually cooked, repeat acceptance, repeated household-wide rejection, recency semantics (rejecting something eaten yesterday ≠ rejecting it six months later). Hypotheses, not truths; inspectable and correctable.
- **AI-assisted recipe discovery**: suggest meals the household has a meaningful chance of accepting, each suggestion self-explaining (e.g. "you regularly accept chicken, rice bowls, mild Mexican flavors, and meals without cooked peppers…").
- **AI-assisted recipe normalization**: messy pasted recipes / screenshots / poorly structured pages → clean recipe records.
- **Inferred household taste patterns**: ingredients, textures, cuisines, sauces, spice tolerance, prep methods, combos that work/fail — correctable.
- **Suggested recipe adaptations**: near-matches made acceptable (e.g. "the household tends to reject cooked onions; make this with onion powder instead") — explicit, never silently altering the source.
- **Probationary pool** for AI-suggested recipes.

**Dependencies:** v1.5 recipe model, accumulated votes, LLM provider + budget decision (deferred to when this is planned).

---

## Later / explore (not committed)

One-liners on purpose — each gets a PLAN doc only if/when it becomes real:

- **Pantry mode**: "meals using ingredients on hand" pool mode (needs an ingredients/pantry model).
- **Hosted deployment + multi-household + real accounts**: only if remote participation becomes useful.
- **Mobile apps**: native or PWA — responsive web probably suffices for a long time.
- **Meal planning / calendar / weekly view**: beyond "tonight".
- **Grocery list export** from planned meals.
- **Photo / document recipe intake**: images, screenshots, PDFs, scanned recipe cards.
- **Integrations**: grocery delivery, kitchen tablets / smart displays.
- **"Used to work, fell out of favor" detection**: meals whose acceptance decayed over time.
- **Archived-meal reconsideration**: periodically re-offer archived meals.
- **Multi-household data portability / export.**

---

*Nothing in this file is a promise. If an item stops making sense, it gets deleted — that's a success, not a loss.*
