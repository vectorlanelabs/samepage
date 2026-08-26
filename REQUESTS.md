# Requests (non-blocking channel)

Wanted-but-not-blocking ideas. The lead picks these up when appropriate, or Charlie decides. **Nothing here is promised.** Add freely.

- [ ] **Lunch `both` subset sanity check** — the seed now tags a curated 27-meal lunch-capable subset as `both` (list in `seed/README.md`; resolved from the plan review, option A). If any of those feel wrong for lunch, or meals were missed, say so — it's a one-line edit in the seed curation and a regenerate.
- [ ] **Track order** — plan runs dinner track first, then lunch. Confirm.
- [ ] **Over-target keeps** — when a batch agrees on more meals than the week needs, the starter picks which to keep (multi-select). Confirm that's the right behavior.
- [ ] **Dice ritual** — the D8/D20 roll (the thing being replaced) stays out of the MVP. Optional: resurrect it later as a fun pick among kept meals (already in POST-V1 "later"). Charlie's call.
- [ ] **Recipe display** — MVP stores recipe links (4 meals) and shows them; the clean cooking view/printing stays post-MVP (v2, with recipe intake). Confirm that's enough for v1.
- [ ] **Library export** — JSON export of meals + recipes as backup/portability (v1.5 candidate; MVP ships WAL-safe DB backups in M5).
- [ ] **Admin bootstrap** — plan says the first person created on an empty install becomes admin (there's no signup flow). Confirm that's acceptable, or name an env-var approach you'd prefer.
- [ ] **Majority rule confirm** — locked as: strict `yes > no`, ties excluded, missing votes = no; host = session starter; aggregate counts only (privacy intact); accepted majority recorded as `kept_by='host'`; unanimous always auto-kept first. Say the word if you want a looser or tighter rule.
- [ ] **Seeded recipe links (M6)** — plan default is **Option B**: leave the seed as-is and use the 4 links as the first real MCP imports to prove the API/MCP path end-to-end. Option A (parse the links into `recipe_text` at seed time) is available if you'd rather bake them in.
- [ ] **API auth shape** — single household `DD_API_KEY` (Bearer) is the plan; per-tool tokens can come later.
- [ ] **Raw votes via API** — default is **no** (aggregates only, consistent with the privacy invariant); say so if your analysis genuinely needs raw per-person data.

## Resolved (2026-08-26)

- ~~Batch size default~~ — fixed at 15 (not a setup choice); revisit after real sessions.
- ~~Lunch starter set~~ — resolved via the curated 27-meal `both` seed subset (plan review #4, option A).
- ~~Adversarial plan review~~ — fulfilled by `docs/INITIAL-PLAN-REVIEW.md`; all 12 findings accepted and applied.
- ~~Hosting~~ — VPS (Hostinger), decided.
- ~~CLAUDE.md refresh~~ — done.
