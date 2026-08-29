# Collection Templates & the Attribute Model (design plan)

> Status: **proposal, not yet approved or built** (2026-08-29). Written by the lead at Charlie's
> request. This plan generalizes the bespoke Meal Planner (migrations 0011/0012) into a reusable
> **attribute model** and defines the second template — **Games** — plus the path to user-defined
> custom collections. No code yet; this is the shape to react to before we build.

## 1. The idea

A collection is a generic thing: a group's shelf of options to vote on. A **template** is just a
**pre-built bundle of attributes** for a common domain — Meals, Games, Activities. A **custom
collection** is the same machinery with attributes the user defines themselves. Templates buy
convenience (sensible attributes out of the box); they are not special-cased in the engine.

Today "meal type" (breakfast/lunch/dinner) is *not* generic — it's a bespoke table with a hardcoded
domain, sitting next to an unused generic `category` table. This plan folds meal type, tags,
ingredients, and category into **one attribute model**, so a new template is **data, not code**.

## 2. Core concept: attributes (a.k.a. facets)

An **attribute** is one named dimension of an item in a collection. It has:

- **key / label** — e.g. `slot` / "Meal slot", `players` / "Players".
- **value type** — how values are shaped:
  - `single` — one value from a fixed list (e.g. complexity: light/medium/heavy)
  - `multi` — any subset of a fixed list (e.g. meal slot: breakfast/lunch/dinner)
  - `tags` — open-ended multi-value with a growing per-collection vocabulary (e.g. tags, ingredients, game mechanics)
  - `range` — a numeric min–max (e.g. players 2–4, playtime 30–60 min)
- **session role** — how it behaves when a session is hosted (the important part):
  - `track` — its values become **voting tracks**; the host sets a target count per value ("3 dinners, 2 lunches")
  - `filter` — its values **constrain the eligible pool** before voting ("5 players present", "≤ 60 min"), but don't create tracks
  - `none` — classification/search only; never touches a session
- **domain** — for `single`/`multi`, the allowed values; for `tags`, open; for `range`, the unit.
- display metadata — sort order, whether it shows on the card, etc.

Separately, a template can define **content fields** — free text / URL / media that describe an item
but aren't dimensions you filter or vote on (recipe method, rules link, where the game is stored).
These are **not** attributes; they're a small per-template set of typed fields.

The whole design rests on one distinction the current code half-has already: the voting engine's
tracks (`session_target.track_label`, `batch.track_label`) are **already generic strings**. What's
hardcoded today is only (a) the session-create form and (b) the track→items mapping. This plan makes
both attribute-driven.

## 3. Worked example A — Meals, re-expressed

| Attribute | key | type | role | domain |
|---|---|---|---|---|
| Meal slot | `slot` | multi | **track** | breakfast, lunch, dinner |
| Tags | `tags` | tags | none | open |
| Ingredients | `ingredients` | tags | none | open (own vocabulary; powers "meals with onion get voted out") |

Content fields: `method` (text), `source_url` (url).

Nothing about the meal experience changes for the user — this is the *same* Meal Planner, expressed
in the generic model. `meal_type` → the `slot` attribute; `tag`/`item_tag` → the `tags` attribute;
`ingredient`/`meal_ingredient` → the `ingredients` attribute; `meal_detail.recipe_text/source_url`
→ content fields. Ingredients being a `tags`-type attribute is what keeps its metric a clean
group-by rather than a special case.

## 4. Worked example B — Games (the second template)

Family game night: board games, card games, dice, party. The decision you're actually making is
"what do we play tonight, given who's here and how long we've got." That shapes the attributes:

| Attribute | key | type | role | domain / unit |
|---|---|---|---|---|
| Game type | `game_type` | multi | filter (optionally track) | board, card, dice, party, RPG, video |
| Players | `players` | range | **filter** | count (min–max supported) |
| Playtime | `playtime` | range | **filter** | minutes (typical min–max) |
| Complexity | `complexity` | single | filter | light, medium, heavy |
| Mechanics/tags | `tags` | tags | none | open (co-op, bluffing, deck-building, kids…) |

Content fields: `rules_url` (url), `location` (text — "hall closet"), `notes` (text), `bgg_url` (url).

**Why games stress-test the model (and meals didn't):**

1. **Numeric ranges.** "Players 2–4", "30–60 min" are min–max values, not picks from a list. New
   value type (`range`) and new filter operators ("supports N", "max ≤ X").
2. **Filter-then-pick, not multi-track.** Meals want *several* kept per session across tracks ("3
   dinners"). Game night usually wants to **pick one** (or a short list) for tonight, from the pool
   that fits the room. So games lean on **filter facets + a single "pick" track**, not per-value
   targets. This is essentially today's ad-hoc "picks" mode, but sourced from a *filtered
   collection* instead of free-typed options — so the voting engine needs **no new mechanic**, just
   a filtered eligible pool.
3. **Optional track use.** A host *could* target `game_type` as tracks ("1 board game + 1 card
   game"). The template marks a facet track-*capable*; the host chooses per session whether to use
   it as tracks or just as a filter. Default: games use `players`/`playtime` as filters and a single
   "pick 1–2" track.

## 5. Third sketch — Activities (to prove it generalizes past two)

"What do we do this weekend": attributes like `setting` (indoor/outdoor, multi, filter), `cost`
(free/$/$$, single, filter), `duration` (range, filter), `group_size` (range, filter), `tags`
(open). Same machinery, different seed. If Meals, Games, and Activities all fall out of one model,
custom collections are just "define your own rows."

## 6. How voting generalizes

Session creation, generalized:

1. Host picks a collection (or ad-hoc). The collection's attributes drive the form:
   - each **track** attribute → a target input per value (meals: breakfast/lunch/dinner counts).
   - each **filter** attribute → a constraint input (games: players present, max playtime,
     complexity ≤ …). Optional; unset filters don't constrain.
   - a collection with **no track attribute** → a single "How many to pick?" target (games,
     activities).
2. Eligible items for a track become:
   `items in collection, not archived, matching this track's attribute-value (if any), AND
   satisfying every session filter`.
3. Everything downstream — batch assembly, yes/no votes, unanimous-keep, majority-to-host, targets,
   completion — is **unchanged**. It already runs on opaque `track_label` strings.

Concretely, `_eligible_item_ids(session, track)` stops matching a hardcoded `meal_type` and instead
applies (track attribute-value) ∩ (session filters). `session_new` stops hardcoding
breakfast/lunch/dinner fields and renders from the collection's attributes.

## 7. Data model (sketch)

Generic tables (replace the bespoke meal ones):

- `collection.template` — which template seeded it (`meal` | `game` | `activity` | `custom`); purely
  informational once attributes exist.
- `attribute` — `(id, collection_id, key, label, value_type, session_role, sort_order, show_on_card)`.
- `attribute_option` — for `single`/`multi`: `(id, attribute_id, value, sort_order)`. (`tags` grow
  their vocabulary here on first use; `range` has none.)
- `item_attribute` — an item's values:
  - select/multi/tags → one row per value: `(item_id, attribute_id, option_id | text_value)`
  - range → `(item_id, attribute_id, num_min, num_max)`
- `session_target` — **already exists**; becomes `(session_id, attribute_id, option value, target_count)`
  for track facets (today it's keyed by the meal-slot string).
- `session_filter` — **new**: `(session_id, attribute_id, op, value | num_min | num_max)` for filter
  facets.
- content fields → a light `item_field(item_id, key, value)` or a JSON column on the item; template
  defines which keys/types it expects.

Templates ship as **seed rows** in `attribute`/`attribute_option` when a collection is created from a
template — no schema per template.

## 8. Migration path: meals (bespoke) → generic

Because prod launches blank and you're only now entering meals, the backfill is small, but the steps
are the same at any scale:

1. Add the generic tables (§7). Leave `meal_type`/`tag`/`ingredient`/`meal_detail` in place.
2. For each existing meal collection, seed the meal template's attributes (`slot`, `tags`,
   `ingredients`).
3. Backfill `item_attribute` from `meal_type`, `item_tag`, `meal_ingredient`; content fields from
   `meal_detail`.
4. Rewrite `_eligible_item_ids` + `session_new` to be attribute-driven; migrate `session_target`
   keying from the slot string to `(attribute_id, value)`.
5. Verify (the schema-parity test + the existing session/library suites) then drop the bespoke meal
   tables.
6. **Ship the Games template as seed data.** No new tables — that's the whole payoff.

## 9. Custom collections

Same tables, no template seed: the collection-create flow gets an "attributes" editor — add an
attribute, pick its type (single/multi/tags/range), mark its role (track/filter/none), fill the
domain. A custom "Wine cellar" or "Weekend trips" collection is then indistinguishable from a
templated one to the engine. Templates are just the "start from a preset" button on that same editor.

## 10. Proposed phasing (each a shippable slice)

- **P1 — Attribute model + migrate Meals onto it.** No user-visible change; proves the model against
  the kind we already have. Gated by the session/library suites staying green.
- **P2 — Session generalization.** Track vs filter facets; `session_filter`; attribute-driven
  `session_new` and eligibility. Unlocks filter-then-pick.
- **P3 — Games template.** Seed data + the `range` value type + range filter UI (the one genuinely
  new building block). Family game night works end to end.
- **P4 — Custom collections.** The attribute editor; "start from a template" presets.

## 11. Open questions for Charlie

1. **Game-night voting shape** — confirm the default is *filter-then-pick-one/two* (single track),
   with per-type tracks as an opt-in. That's my read of "what do we play tonight."
2. **Ranges** — is min–max enough (players 2–4, time 30–60), or do you want "best at N" as distinct
   from "supports N"? BoardGameGeek separates them; I'd start with supports-range only.
3. **How far to take custom now** — P1–P3 give you Meals + Games with zero custom UI. P4 (user-defined
   attributes) is more surface area; worth deferring until you've used two templates and know what
   the editor actually needs.
4. **Content fields storage** — small typed `item_field` table vs a JSON column. Lean toward the
   table (queryable, consistent with the rest); flag if you'd rather keep item content opaque.
