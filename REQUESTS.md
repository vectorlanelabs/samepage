# Requests (non-blocking channel)

Wanted-but-not-blocking ideas. The lead picks these up when appropriate, or Charlie decides. **Nothing here is promised.** Add freely.

- [ ] **Lunch `both` subset sanity check** — the seed now tags a curated 27-meal lunch-capable subset as `both` (list in `seed/README.md`; resolved from the plan review, option A). If any of those feel wrong for lunch, or meals were missed, say so — it's a one-line edit in the seed curation and a regenerate.
- [ ] **Track order** — plan runs dinner track first, then lunch. Confirm.
- [ ] **Over-target keeps** — when a batch agrees on more meals than the week needs, the starter picks which to keep (multi-select). Confirm that's the right behavior.
- [ ] **Dice ritual** — the D8/D20 roll (the thing being replaced) stays out of the MVP. Optional: resurrect it later as a fun pick among kept meals (already in POST-V1 "later"). Charlie's call.
- [ ] **Recipe display** — MVP stores recipe links (4 meals) and shows them; the clean cooking view/printing stays post-MVP (v2, with recipe intake). Confirm that's enough for v1.
- [ ] **CI disabled (per Charlie, 2026-08-26)** — all GitHub Actions workflows removed: error emails on every commit; CI will be re-added when Charlie provides a hosting environment to publish to. Until then, local gates (`uv run ruff check .` + `uv run pytest -q`) are the verification. Root cause of the failing runs was never determined (runs died in ~12s with zero recorded steps and 404 logs — GitHub-side, not the workflow steps, which all pass locally on a clean clone); revisit at re-enable.
- [ ] **Multi-worker bootstrap guard** — `_bootstrap_lock` is in-process only; a multi-worker uvicorn deployment needs a DB-level singleton-admin guard. Deployment is single-process (M5 will confirm); revisit at M5.
- [ ] **Login UX** — unauthenticated `/people` returns a bare 403; nicer to redirect to `/login`. Polish pass (M3+).
- [ ] **Library export** — JSON export of meals + recipes as backup/portability (v1.5 candidate; MVP ships WAL-safe DB backups in M5).
- [ ] **Admin bootstrap** — plan says the first person created on an empty install becomes admin (there's no signup flow). Confirm that's acceptable, or name an env-var approach you'd prefer.
- [ ] **Majority rule confirm** — locked as: strict `yes > no`, ties excluded, missing votes = no; host = session starter; aggregate counts only (privacy intact); accepted majority recorded as `kept_by='host'`; unanimous always auto-kept first. Say the word if you want a looser or tighter rule.
- [ ] **Seeded recipe links (M6)** — plan default is **Option B**: leave the seed as-is and use the 4 links as the first real MCP imports to prove the API/MCP path end-to-end. Option A (parse the links into `recipe_text` at seed time) is available if you'd rather bake them in.
- [ ] **API auth shape** — single household `DD_API_KEY` (Bearer) is the plan; per-tool tokens can come later.
- [ ] **Raw votes via API** — default is **no** (aggregates only, consistent with the privacy invariant); say so if your analysis genuinely needs raw per-person data.

- [ ] **Login timing side-channel** — `POST /login` returns instantly for an unknown email (no hash computed) but takes ~60ms for a known email with a wrong password (full 600k-iteration PBKDF2 run), live-measured during M2a review. Lets an attacker enumerate valid account emails by response time even though the error message itself is generic. Inherited from the M1 PIN-login code this replaced (same early-return shape), not introduced by M2a — but real and unaddressed. Fix is cheap (always run a dummy hash on the unknown-email path) — worth doing before any public launch.
- [ ] **Library CRUD gating is interim** — gates `/library` create/edit/archive on "any signed-in account" (not group/collection-scoped). Now that M2b's `Collection`/`Group` link exists, tightening this to "must be an owner/admin of the group that owns this collection" is a small, well-scoped follow-up — do it before any real multi-group usage.
- [ ] **Single-collection routing is a deliberate M2b simplification** — `/library` always resolves to "the first meal-kind collection that exists," not a specific `collection_id` in the URL. Fine while there's exactly one collection in practice; needs real `/collections/{id}/...` routing once a second collection kind is actually built (things-to-do, games, ...) or once multiple groups each want their own meal collection.

## Resolved (2026-08-26)

- ~~Batch size default~~ — fixed at 15 (not a setup choice); revisit after real sessions.
- ~~Lunch starter set~~ — resolved via the curated 27-meal `both` seed subset (plan review #4, option A).
- ~~Adversarial plan review~~ — fulfilled by `docs/INITIAL-PLAN-REVIEW.md`; all 12 findings accepted and applied.
- ~~Hosting~~ — VPS (Hostinger), decided.
- ~~CLAUDE.md refresh~~ — done.
