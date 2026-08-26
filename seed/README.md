# seed/ — Pre-seeded meal data

`meals.json` is the **pre-seeded meal library** for the app. There is **no import feature** — the app comes up with this data baked in.

## Provenance

- **Generated from** `reference/D20 Dinner Decider.xlsx` (the legacy household spreadsheet).
- Regenerate with `scripts/build_seed.py` (dev-time tool, M2; uses openpyxl — dev dependency only, **not a runtime dependency**).
- The JSON is committed and reviewable; diff it to see exactly what gets seeded.

## Schema

```json
{
  "generated_from": "reference/D20 Dinner Decider.xlsx",
  "generated_at": "2026-08-26",
  "meal_count": 155,
  "meals": [
    {
      "name": "Hot Dogs",
      "category": "Tab 1",          // legacy sheet position 1..8 (D8 mapping preserved as category)
      "type": "dinner",             // lunch | dinner | both (seed is all "dinner"; editable in-app)
      "tags": ["takeout"],          // auto-tagged for the known takeout set; AI hooks later
      "source_url": null            // recipe link, where the spreadsheet had one (4 meals)
    }
  ]
}
```

## Seed decisions (locked)

- **155 meals**, 8 categories (`Tab 1`–`Tab 8`; Tab 8 has 15 — faithful to the source).
- **Times Rolled column is ignored** — not carried into the seed.
- **Type mapping** (plan review #4): most meals are `dinner`; a curated **27-meal lunch-capable subset is `both`** so the lunch track has a pool from a fresh install. The curated list (lunch/brunch items, sandwiches, soups, simple kids' meals, leftovers/catch-alls):

  `Hot Dogs · Pancakes · bacon and eggs · Frozen pizza · nachos · baked potato bar · Hot Pockets · taco soup · chicken nuggets · quesadillas · chicken noodle soup · deli sandwich bar · pizza rolls · baked potato soup · french toast · Eggs in a basket · Breakfast burritos · Homemade mcgriddles · ramen (but fancy) · BLTs · grilled cheese · Leftovers · Broccoli Cheese Soup · fish sticks and mac and cheese · BBQ Sandwiches · pigs in a blanket · Pepperoni rolls`

  Adjustable: edit the `CURATED_BOTH` list in `scripts/build_seed.py` (or this JSON) and regenerate. Household can always retag in-app.

- **Embedded URLs stripped from meal names** → `source_url` (4 meals: TikTok, cookincanuck, allrecipes, damndelicious).
- **Takeout auto-tag**: the 10 known restaurant entries carry `["takeout"]`.
- **Dedupe**: loader dedupes by normalized name (`casefold`, whitespace-collapsed); "Chicken parm" appears twice in the spreadsheet → the loader keeps the first, logs the skip. To keep both, rename one in this JSON.
- `recipe_text` is empty for all seeded meals (recipes arrive via the future AI intake step; links are already captured).
