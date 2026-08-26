# Requests (non-blocking channel)

Wanted-but-not-blocking ideas. The lead picks these up when appropriate, or Charlie decides. **Nothing here is promised.** Add freely.

- [ ] **Lunch starter set** — the seed is all `dinner`-type meals (faithful to the spreadsheet), so the lunch track starts empty until meals are added/retagged. Option: curate a "lunch/both" subset from the spreadsheet's lighter entries (grilled cheese, BLTs, chicken nuggets, deli sandwich bar, french toast, pancakes…) for the seed. Charlie's call.
- [ ] **"Chicken parm" duplicate** — the seed dedupes by normalized name and logs the skip (Tabs 1 & 2 both list it). If the household actually treats them as two different meals, rename one in `seed/meals.json`.
- [ ] **Batch size default** — plan says 15, settable 15–20 at session creation. Confirm 15 is the right default.
- [ ] **Track order** — plan runs dinner track first, then lunch. Confirm.
- [ ] **Over-target keeps** — when a batch agrees on more meals than the week needs, the starter picks which to keep (multi-select). Confirm that's the right behavior.
- [ ] **Dice ritual** — the D8/D20 roll is out of the MVP flow per the corrected direction. Optional: resurrect it later as a fun pick among kept meals (already in POST-V1 "later"). Charlie's call.
- [ ] **Hosting** — where will the app run (Mac mini? Raspberry Pi? VPS + Tailscale)? Affects the "Run it" docs in M5.
- [ ] **Adversarial plan review** — run Oscar (ai-grouch) over `docs/PLAN-v1-mvp.md` before M0, catch plan-level flaws while it's cheap.
- [ ] **Recipe display** — MVP stores recipe links (4 meals) and shows them; the clean cooking view/printing stays post-MVP. Confirm that's enough for v1.
- [ ] **CLAUDE.md refresh** — the implementer-constraints file still describes the old product shape (import spec). Needs a rewrite to the corrected direction; **write blocked** — protected file, requires Charlie's explicit approval.
