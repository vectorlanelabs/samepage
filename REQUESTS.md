# Requests (non-blocking channel)

Genuinely needs Charlie's judgment — not decidable from the architecture or from what's already been
built. **Nothing here is promised.** Add freely.

- [ ] **Site access gate vs. open signup.** The original plan had a site-wide passphrase (`DD_ACCESS_KEY`,
  now `SP_ACCESS_KEY`) gating the whole app before login — reasonable for a single-household app nobody
  else was meant to reach. Now that the platform is meant to let other groups self-serve sign up (a
  friend creates their own account, their own group), a blanket site passphrase works against that: they
  can't even reach the signup page without you handing them a separate passphrase first. Real accounts
  (M2a) already provide the actual security boundary. Options: drop the site gate entirely and rely on
  accounts; keep it but scope it to something else (e.g. an invite code required at signup, not a
  whole-site gate); or keep it as-is if you want the platform to stay closed to anyone you haven't
  personally let in. This is a real product tradeoff, not an engineering detail — needs your call before
  M5 builds the deployment story around it.
- [ ] **Lunch `both` subset sanity check.** The seed tags a curated 27-meal lunch-capable subset as `both`
  (list in `seed/README.md`). If any of those feel wrong for lunch, or meals were missed, say so — it's a
  one-line edit in the seed curation and a regenerate. Only you can judge this; no urgency.
- [ ] **Dice ritual.** The D8/D20 roll (the thing Meal Planner replaced) stays out of scope. Purely
  optional: resurrect it later as a fun pick among kept meals, if you ever want it. No action needed
  unless you bring it up.

## Known engineering follow-ups (decided, not blocking, no input needed)

Tracked so they don't get lost — these are settled calls, not open questions.

- [ ] **Login timing side-channel** — `POST /login` returns instantly for an unknown email but takes
  ~60ms for a known email with a wrong password (full 600k-iteration PBKDF2 run), letting an attacker
  enumerate valid account emails by response time. Inherited from the old PIN-login code, not new. Fix is
  cheap (always run a dummy hash on the unknown-email path). Worth doing before any public launch.
- [ ] **Library CRUD gating is interim** — gates `/library` create/edit/archive on "any signed-in
  account," not "must be an owner/admin of the group that owns this collection." Fine while there's one
  group in practice; tighten before real multi-group usage.
- [ ] **Single-collection routing is a deliberate M2b simplification** — `/library` always resolves to
  "the first meal-kind collection that exists," not a `collection_id` in the URL. Needs real
  `/collections/{id}/...` routing once a second collection or a second group's meal collection exists.
- [ ] **Bare 401s instead of a login redirect** — unauthenticated requests to `/groups`, `/library`
  mutations, etc. return a bare 401 rather than redirecting to `/login`. Polish pass, whenever convenient.
- [ ] **Library export** — JSON export of items + recipes as backup/portability. M5 ships DB-level
  backups regardless; this would be a user-facing export on top. Low priority.

## Resolved

- ~~Batch size default~~ — fixed at 15 (not a setup choice); revisit after real sessions.
- ~~Lunch starter set~~ — resolved via the curated 27-meal `both` seed subset.
- ~~Adversarial plan review~~ — fulfilled by `docs/INITIAL-PLAN-REVIEW.md`; all 12 findings accepted.
- ~~Hosting~~ — VPS (Hostinger), decided.
- ~~Track order~~ — dinner first, then lunch. Working default, never contested; not re-litigating it.
- ~~Over-target keeps~~ — host/starter picks which to keep when a batch agrees on more than the target.
  Working default, carried through the v2 design unchanged.
- ~~Majority rule~~ — strict `yes > no`, ties excluded, host accepts, unanimous always kept first,
  aggregate counts only. Confirmed by repeated use across the whole design process, not re-asking.
- ~~Recipe display~~ — built and working (M2/M2b): link and/or free text, shown on the recipe view page.
- ~~Raw votes via API~~ — no, aggregates only. Now structurally true, not just a policy: the v2 schema
  (`docs/PLAN-v2-samepage.md` §5.4) never stores a durable per-person vote in the first place.
- ~~API auth shape~~ — superseded by a real decision, not left open: per-group tokens, not one shared
  household key. See `docs/PLAN-v2-samepage.md` §8 (M6).
- ~~Seeded recipe links (M6 Option A vs B)~~ — Option B stands (prove the MCP import path on the 4
  existing links when M6 is built) unless raised again; not worth Charlie's time to re-confirm a default
  nobody's objected to.
- ~~CI disabled~~ — not an open question, a standing decision: off until Charlie provides a hosting
  target and explicitly re-approves it (`CLAUDE.md` non-negotiable #10). Documented there, not tracked
  here as pending.
- ~~Admin bootstrap~~ — obsolete. The old "first person on an empty install becomes admin" concept doesn't
  exist anymore; M2a's signup is always open, no bootstrap race to guard.
- ~~Multi-worker bootstrap guard~~ — obsolete for the same reason: the in-process `_bootstrap_lock` it
  referred to was removed with `Person` in M2a. `account.email`'s `UNIQUE` constraint already makes
  concurrent signups safe at the database level — no in-process lock needed, multi-worker or not.
- ~~CLAUDE.md refresh~~ — done.
