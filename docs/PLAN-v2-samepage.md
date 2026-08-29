# SamePage — v2 Architecture: Multi-Tenant Decision Platform

> Status: **2026-08-29 — M2a and M2b landed; M3 onward reviewed and revised in light of what building
> M2a/M2b actually surfaced, still unapproved pending Charlie's sign-off.** Supersedes the identity,
> tenancy, and voting-mechanism decisions in `CHARTER.md` and `docs/PLAN-v1-mvp.md` (D2, D16 identity
> portions, D10, and the M3–M6 task lists). M0–M2 code stood as the starting point for M2a/M2b — it was
> generalized, not thrown away.
>
> This is a first architecture pass, not a fully task-broken-out plan — per this project's own convention
> ("don't design to death"), per-milestone task/acceptance detail gets filled in immediately before that
> milestone starts, not all at once here. §6, §6.1, and §8's M4–M6 rows were revised on 2026-08-29 to
> account for what multi-tenancy actually requires (tenant-scoped reporting, per-group API tokens) — these
> weren't visible until M2a/M2b's account/group model was real.

## 1. What changed and why

Building M0–M2 as a single-household meal planner surfaced something bigger: the actual reusable asset
here is a **consensus decision engine** (batch of options → private yes/no → unanimous-keep, host-may-accept-majority)
that has nothing to do with meals specifically. Charlie wants this to become **SamePage** — a platform any
family or friend group can host, with meal planning (renamed **Meal Planner**) as the first of several
**collections** (things to do, games owned, date-night options, ...) sharing one voting mechanism and one
reporting layer.

Two things forced a real architecture revision rather than an additive feature:

1. **The voting engine (`Vote`, `BatchMeal`, `Session.lunch_target`/`dinner_target`) is hard-coded to
   `meal_id`.** Nothing here was built yet (M3 is unbuilt), so this is the cheapest point in the project's
   life to generalize it — waiting until after M3 ships means redoing tested, reviewed, stateful code
   instead of writing new code once.
2. **The identity model conflicts with what's already shipped.** M1 built "no accounts, `Person` = name +
   PIN" (CHARTER D2). The new model needs real accounts for group owners/admins, no individual auth for
   regular participants at all (PINs are gone entirely — see §4), and voting sessions that don't require
   group membership to join. This isn't additive to M1, it replaces its identity layer.

## 2. Product shape

- **SamePage** is the platform/brand. **Meal Planner** (formerly "Dinner Decider") is the first
  **collection kind** it hosts.
- **Single shared deployment, multi-tenant.** One instance (Charlie's VPS) hosts many independent
  **groups** (households, friend circles). This was chosen over per-family self-hosted instances +
  federation — federation between independent instances is a real distributed-identity problem; a shared
  deployment with real accounts avoids it entirely while still supporting "invite a friend from another
  group to vote," because everyone's account already lives in the same system.
- **A group owns zero or more collections** (a meal library, a things-to-do list, a game shelf, ...) and
  can **host voting sessions** against any of them, or against no collection at all (pure ad hoc voting —
  "what bar should we hit tonight," options typed in on the spot, never saved anywhere).
- **Voting sessions are decoupled from group membership.** Anyone with the link/code can join and vote,
  logged in or not, member of the hosting group or not. Login only pre-fills your display name — it is a
  convenience, never a gate.

## 3. Non-goals carried forward / superseded

Still true (unchanged from `CHARTER.md`):

- No in-app AI, no LLM keys, ever — recipe parsing/discovery/trend analysis stay external via API/MCP.
- No grocery list, no dice ritual.
- Vote privacy is still a hard invariant — **stronger now**: individual votes were never *shown*; under
  this design they are largely never *durably stored against an identity* at all (§5.5).
- Deactivate/archive-not-delete; schema changes ship as Alembic migrations.

Explicitly superseded:

- ~~D2/D16 "no accounts, `Person` = name + PIN"~~ → real `Account` for hosts/admins; no PINs anywhere
  (§4).
- ~~"No accounts / multi-household hosting" (non-goal)~~ → multi-tenancy is now core (§2).
- ~~D10 "meals typed lunch/dinner/both, session has `lunch_target`/`dinner_target`"~~ → generalized to
  per-collection, per-session **targets** (§5.3); Meal Planner keeps dinner/lunch tracks as *its* config,
  not an engine-level concept.

## 4. Identity model

Three tiers, none of them PIN-based:

| Tier | What it is | Durable? |
|---|---|---|
| **Account** | Real login (email + password to start — see below). Can own/administer groups, host sessions, pre-fill a display name when voting. | Yes |
| **Group membership** | An account attached to a group as `owner` (exactly one, set on the group, transferable) or `admin` (any number, added by the owner or another admin). Membership grants management of that group's collections, sessions, and reports. | Yes |
| **Session participant** | Whoever joined a specific voting session — a display name, optionally linked to an `Account` for pre-fill. Not a household roster entry; scoped to that one session. | Ephemeral (kept only as long as the session record exists) |

**Auth mechanism (recommendation, reviewable):** email + password (PBKDF2 or Argon2 hash, matching the
project's existing hashing approach), no transactional email required for v1 — "forgot password" is a
manual admin action (script), not a self-serve flow. This avoids adding an SMTP dependency for a
small-scale, invite-only platform. Passwordless magic-links were considered and rejected for v1 solely
because they *require* outbound email; revisit if the user base grows past what manual resets can handle.

**Why no PINs at all, not even for regulars:** the only thing PINs were protecting was "which specific
person cast this vote," and the platform no longer needs that (§5.5 — outcomes are tracked, voters are
not). A household member who votes every week doesn't need any credential; the account layer exists
purely for group *administration*, not participation.

## 5. Data model (supersedes `CHARTER.md` §6 / plan §6)

```
account(id PK, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        display_name TEXT NOT NULL, created_at DATETIME)

group(id PK, name TEXT NOT NULL, owner_account_id FK -> account NOT NULL,
      created_at DATETIME)

group_admin(group_id FK, account_id FK, added_at DATETIME, PK(group_id, account_id))
      -- additional admins beyond the owner; owner is NOT duplicated here

collection(id PK, group_id FK NOT NULL, kind TEXT NOT NULL,        -- 'meal' | 'generic' (extensible)
           name TEXT NOT NULL, created_at DATETIME)

category(id PK, collection_id FK NOT NULL, name TEXT NOT NULL, sort_order INT)
                                                                     -- scoped per collection now, not global

tag(id PK, group_id FK NOT NULL, name TEXT NOT NULL, UNIQUE(group_id, name))
                                                                     -- scoped per group, reusable across
                                                                     -- that group's collections

item(id PK, collection_id FK NOT NULL, name TEXT NOT NULL,
     description TEXT, category_id FK NULL,
     is_active BOOL DEFAULT 1, archived_at DATETIME NULL,
     times_offered INT DEFAULT 0, times_kept INT DEFAULT 0, last_kept_at DATETIME NULL,
                                                                     -- moved up from `meal` — the success
                                                                     -- signal applies to any collection kind
     created_at DATETIME, updated_at DATETIME)

item_tag(item_id FK, tag_id FK, PK(item_id, tag_id))

meal_detail(item_id FK PK -> item, type TEXT NOT NULL DEFAULT 'dinner',   -- lunch|dinner|both
            ingredients TEXT, recipe_text TEXT, source_url TEXT)
                                                                     -- 1:1 extension; meal-kind collections
                                                                     -- only. Future kinds (game, outing) get
                                                                     -- their own *_detail table the same way.

session(id PK, code TEXT UNIQUE NOT NULL, status TEXT NOT NULL,    -- lobby|voting|complete|expired
        group_id FK NOT NULL, host_account_id FK -> account NOT NULL,
        collection_id FK NULL,                                     -- NULL = pure ad hoc session
        created_at DATETIME, finished_at DATETIME NULL)

session_target(session_id FK, track_label TEXT NOT NULL, target_count INT NOT NULL,
               PK(session_id, track_label))
                                                                     -- generalizes lunch_target/dinner_target;
                                                                     -- Meal Planner writes rows
                                                                     -- ('dinner', N), ('lunch', M); a
                                                                     -- single-track collection writes one row

session_participant(id PK, session_id FK NOT NULL, account_id FK NULL,
                     display_name TEXT NOT NULL, joined_at DATETIME)
                                                                     -- account_id set only if logged in at
                                                                     -- join time; purely for pre-fill, confers
                                                                     -- no permission

batch(id PK, session_id FK NOT NULL, seq INT, track_label TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'open', closed_at DATETIME NULL, UNIQUE(session_id, seq))

batch_item(batch_id FK, item_id FK NULL, ad_hoc_label TEXT NULL,   -- exactly one of item_id/ad_hoc_label set
           sort_order INT, yes_count INT DEFAULT 0, no_count INT DEFAULT 0,
           outcome TEXT NULL,                                      -- 'kept_unanimous' | 'kept_host' | 'not_kept' | NULL (open)
           PK(batch_id, COALESCE(item_id, ad_hoc_label)))           -- durable per-item OUTCOME log — no person_id.
                                                                     -- this is what reporting/discovery reads (§6).

batch_response(batch_id FK, session_participant_id FK, item_id FK NULL, ad_hoc_label TEXT NULL,
               choice TEXT NOT NULL, responded_at DATETIME,
               PK(batch_id, session_participant_id, COALESCE(item_id, ad_hoc_label)))
                                                                     -- EPHEMERAL, in-batch-only state used to
                                                                     -- detect "has everyone responded" and to
                                                                     -- roll up yes_count/no_count onto
                                                                     -- batch_item at close. Safe to prune after
                                                                     -- a batch closes — batch_item is the
                                                                     -- durable record, this is not history.
```

Notes:

- **No table anywhere ties a vote choice to a durable identity.** `session_participant` is scoped to one
  session and can be discarded with it; `batch_response` is explicitly operational, not historical. This
  is a *stronger* privacy posture than the old "never shown, but stored raw forever" design — answers §5.5
  below.
- `item.times_kept`/`last_kept_at` replace `meal.times_kept`/`last_kept_at` — same signal, generalized.
- Ad hoc, never-persisted options (the "let everyone throw in an option before reveal" feature, still
  backlog per §7) slot in via `batch_item.ad_hoc_label` — an item that only ever exists inside one batch
  unless a host explicitly promotes it into the collection as a real `item` row.

### 5.1 Meal Planner mapping

The 155 seeded meals migrate mechanically: each existing `meal` row becomes one `item` row (name,
description←none, category_id, is_active, times_kept, last_kept_at, created_at/updated_at) plus one
`meal_detail` row (type, ingredients, recipe_text, source_url) with matching `item_id`. `category` and
`tag` get a `group_id`/`collection_id` backfilled to Charlie's single existing group. This is a bounded,
mechanical migration — no data loss, no manual re-entry.

### 5.2 Collections aren't required for voting

`session.collection_id` is nullable specifically so a host can start a vote with zero setup — "where
should we eat," "what movie," typed in as ad hoc `batch_item.ad_hoc_label` rows, nothing ever touching a
database. This is table stakes for the "date night" / "what do we do today" use cases Charlie described,
and it costs nothing extra in the schema above (`ad_hoc_label` already has to exist for the pre-reveal
submission backlog item).

### 5.3 Targets replace hard-coded tracks

`session_target` generalizes `lunch_target`/`dinner_target`. Meal Planner sessions still run dinner-first
then lunch (same UX as before — write two `session_target` rows). A collection with no natural tracks
(games, activities) writes one row, e.g. `('picks', 3)`. The batch-assembly and progression logic (D6, D13,
§9.3/§9.6 in the old plan) is otherwise unchanged — it just reads `session_target` instead of two fixed
columns.

### 5.4 Outcome, not history — answering "would this require keeping vote records?"

Yes, but scoped narrowly: **`batch_item`** is the durable record — one row per (item or ad hoc option,
batch, outcome, aggregate yes/no counts). It has no `person_id` and never will. It's enough to answer "how
often has this been rejected," "is it trending down," "does the `fish` tag correlate with no-votes" — all
of §6 — without ever knowing or storing *who* voted which way. `batch_response` is the only thing that
looks like a per-person vote, and it's explicitly disposable operational state, not a history table.

## 6. Reporting & discovery

Built on `batch_item` (outcome + aggregate counts, durable) joined against `item_tag`/`tag` and
`category`. Enables, without any new tables:

- Reject rate by tag/category ("everything tagged `fish` gets voted no ~70% of the time").
- Trend over time (rolling reject rate per item or tag, using `batch_item.outcome` timestamps via its
  parent `batch.closed_at`).
- "Haven't been offered/kept lately" (via `item.times_offered`/`last_kept_at`).
- Cross-collection reporting is possible in principle (same shape of data per collection) but not
  spec'd — first real second collection (post-Meal-Planner) should confirm the reporting queries
  generalize before building a cross-collection reporting UI.

This directly feeds the "discover new recipes based on what similar items succeed/fail" idea from
Charlie's own framing — it's a query over existing data, not a new subsystem, once `batch_item`+`tag`
exist.

**Tenant scoping is load-bearing here, not optional.** Every reporting query must filter through
`collection.group_id` to groups the requesting account actually belongs to (owner or admin). This didn't
matter under the old single-household design; it matters now because the database holds other people's
groups too. A report endpoint that forgets this filter leaks one family's reject rates and meal history to
another. Locked as a hard requirement for M4, not a nice-to-have.

## 6.1 Single shared database, not database-per-tenant

One SQLite database serves every group on the deployment — the same file M0–M2b already write to.
Isolation between groups is enforced at the application layer (every tenant-owned table traces back to a
`group_id`), not at the storage layer. This was implicit in the schema (§5) but is worth stating as a
locked decision: database-per-tenant would mean per-group backup/restore, per-group migrations, and a
routing layer to pick the right DB file per request — real infrastructure this deployment doesn't need at
its current scale (Charlie's VPS, a handful of groups). Revisit only if the platform outgrows a single
SQLite file, not preemptively.

## 7. Explicitly still backlog (not blocking M2a/M2b/M3)

- **Pre-reveal ad hoc option submission** — participants add options before the batch is revealed; host
  may promote a submitted ad hoc item into the collection afterward. Schema already accommodates it
  (`batch_item.ad_hoc_label` + a promote-to-`item` action); no engine changes needed, just UI/routes,
  whenever it's prioritized.
- **Cross-collection reporting UI.**
- **A second collection kind** (things-to-do, games, ...) — build when there's real want, not
  speculatively; that's the moment to confirm the `*_detail` extension pattern actually generalizes.
- **Owner vs. admin distinction beyond membership** (e.g. can an admin remove the owner, can the owner
  leave without transferring ownership first) — small access-control detail, resolve at M2a build time,
  not architecturally significant.

## 8. Revised milestones

| ID | Milestone | Relationship to old plan | Status |
|---|---|---|---|
| M0 | Foundation (FastAPI skeleton, migrations, security middleware) | **Stands as-is** — no identity/tenancy coupling here | [x] landed |
| **M2a** | **Identity & tenancy**: `Account` (email+password), `Group`/`group_admin`, replace `Person`+PIN entirely | **Replaces M1** in full (PINs, lockout, `Person.is_admin` all removed) | [x] landed |
| **M2b** | **Generic collections & items**: `Collection`/`Item`/`meal_detail`/scoped `Category`/`Tag`, migrate the 155 meals (§5.1), library UI becomes collection-aware | **Revises M2** (CRUD/seed logic mostly reusable, schema underneath changes) | [x] landed |
| M3 | **Session-based voting engine**: group/account-hosted sessions, account-optional participants, `session_target`, ad hoc + library-backed `batch_item`, outcome-only recording | Net-new build against this doc; old M3 spec (§9 of plan v1) is void — roster-freeze/batch-assembly/unanimous+majority *mechanics* carry over, identity plumbing does not | [ ] unapproved until this doc is approved |
| M4 | **Reporting & discovery** (§6) — supersedes "history & favorites" (broader scope: trend/tag correlation, not just `times_kept`). **Every query scoped to the requesting account's own groups (§6)** — a new hard requirement multi-tenancy introduces that didn't exist in the old single-household plan. | Expanded from old M4 | [ ] |
| M5 | Hardening, deployment docs, backup/restore. Single shared SQLite DB (§6.1) — backup/restore story unchanged (still one file). **Open question: does the old `DD_ACCESS_KEY`-style site-wide passphrase gate still make sense** now that real accounts exist and the platform is meant to let other groups self-serve sign up? A blanket site passphrase blocks exactly the "invite a friend's group to join" flow the platform is for. Needs Charlie's call — tracked in REQUESTS.md, not resolved here. | Access-gate question is new; backup/restore mechanics otherwise unchanged | [ ] |
| M6 | External API + MCP. **Locked change from the old plan: tokens are per-group, not one shared household key.** A single global `DD_API_KEY`/`SP_API_KEY` would let one group's AI tools read every other group's data on the same deployment — a real leak now that other people's groups live in this database, not a hypothetical. Each group's owner generates and can revoke their own group's token; MCP tools operate on generic `item`/`collection` endpoints (not meal-specific), scoped the same way as M4's reporting. "AI lives outside the app" still holds — it now applies per-group, not just to Charlie's own tools. | Token-scoping question from the original table is now a locked decision, not an open item | [ ] |

## 9. Rename

Product: **SamePage**. This collection/module: **Meal Planner** (was "Dinner Decider"). Repo, package
name, and env var prefix (`DD_*` → `SP_*`) updated alongside this doc; see commit for the mechanical diff.
GitHub repo renamed `vectorlanelabs/dinnerdecider` → `vectorlanelabs/samepage` on 2026-08-28, per Charlie's
explicit go-ahead. Local clone directory renamed to match (`samepage-app`).
