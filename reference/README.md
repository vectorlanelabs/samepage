# reference/ — Legacy source data

## D20 Dinner Decider.xlsx

The household's existing meal-decision spreadsheet — *"8 tabs, 20 dinner options per tab; roll a D8 and a D20 and use the resulting indexed meal."*

This file is the **read-only migration source** for Dinner Decider's import pipeline (see `docs/PLAN-v1-mvp.md` §10). Do not edit it here — once the app has a meal library, that becomes the editable home for meals.

### Structure

- 8 sheets (`Sheet1`–`Sheet8`), each with a header row (`Roll Result | Dinner | Times Rolled`) plus up to 20 meal rows. Sheet position = D8 result; row number = D20 result.
- A few rows carry a recipe URL — either in a trailing cell (column D or E) or embedded at the end of the meal name (see audit below).

### Audit snapshot (2026-08-26, at planning time)

- **~155 named meals** — Sheet1–Sheet7 have all 20 slots filled; Sheet8 has 15 filled (rows 16–20 empty).
- **"Times Rolled"** populated on 34 rows (counts of 1–2); 37 historical dice rolls in total. **This column is ignored by the product** (Charlie's direction, 2026-08-26) — it is not carried into `seed/meals.json`.
- **4 recipe URLs**: TikTok (Sheet2, col E) and damndelicious.net (Sheet8, col D) as standalone cells; cookincanuck.com (Sheet5) and allrecipes.com (Sheet6) embedded at the end of the meal name.
- **Takeout entries present** (Chili's, Taco Bell, McDonald's, Chick Fil A, Panda Express, Raising Cane's, Whataburger, Subway, Los Hermanos, "Order Pizza") — these are intentional dinner answers, not noise.
- **Catch-all entries**: "Make do", "Leftovers", "yesterday's chicken".
- **One exact duplicate across tabs**: "Chicken parm" (Sheet1 row 16 and Sheet2 row 19). Several near-duplicates to eyeball (e.g. Chili / Chili Dogs / Chili Dog Casserole / Chili Cheese Dog Tater Tot Casserole).
- Two entries carry a `(LC)` suffix (likely "low carb"): "Baked Chicken Tenders (LC)", "Pizza Meatloaf (LC)".

### Data conventions used by the seed pipeline

- Sheet index (1–8) → category `Tab N` (renamable in-app later).
- `Times Rolled` → **ignored** (corrected direction 2026-08-26).
- Known restaurant names → auto-tagged `takeout` in the seed (curated list, not an AI guess).
- Embedded URLs are stripped from meal names into `source_url` during seed generation.
