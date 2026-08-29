# SamePage — v2 Architecture: Multi-Tenant Decision Platform

> Status: **2026-08-29 — M2a and M2b landed; M3 onward reviewed and revised in light of what building
> M2a/M2b actually surfaced, still unapproved pending Charlie's sign-off.**
> **Revision 2026-08-29 (2): applied all seven fix items from the Oscar architecture review**
> (`docs/OSCAR-REVIEW-plan-2026-08-29.md` — implementable PKs in §5, vote-data lifecycle §5.5, session
> tenancy invariants, state machines §5.6, sharpened M4/M5/M6 rows) **and added §10: mobile-first client
> platform decisions** (Charlie's direction, 2026-08-29: voters and hosts are on phones; desktop remains
> for library/collection management comfort). Supersedes the identity,
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
- No grocery list. No randomized/chance-based selection of any kind — options get chosen by the group,
  not a roll; this is permanent, not a deferred feature.
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

session(id PK, code TEXT UNIQUE NOT NULL, status TEXT NOT NULL,    -- lobby|voting|complete|expired (§5.6)
        group_id FK NOT NULL, host_account_id FK -> account NOT NULL,
        collection_id FK NULL,                                     -- NULL = pure ad hoc session
        created_at DATETIME, finished_at DATETIME NULL)
        -- INVARIANTS (hard M3 requirements, enforced in the creation route, not assumed):
        --   (a) host_account_id must be an owner/admin of group_id — session creation goes
        --       through require_group_admin (app/auth.py), which already exists.
        --   (b) collection_id, when set, must belong to group_id — checked at creation AND
        --       re-checked at batch assembly. Without (b), a host could point their session at
        --       another group's collection and serve that group's entire library to voters:
        --       a full cross-tenant read through the one path M4's scoping rule doesn't cover.

session_target(session_id FK, track_label TEXT NOT NULL,
               target_count INT NOT NULL CHECK (target_count > 0),
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

batch_item(id PK, batch_id FK NOT NULL, item_id FK NULL, ad_hoc_label TEXT NULL,
           sort_order INT, yes_count INT DEFAULT 0, no_count INT DEFAULT 0,
           outcome TEXT NULL,                                      -- 'kept_unanimous' | 'kept_host' | 'not_kept' | NULL (open)
           CHECK ((item_id IS NULL) != (ad_hoc_label IS NULL)))     -- exactly one of the two set, DB-enforced
           -- plus two PARTIAL unique indexes (SQLite forbids expressions in a PRIMARY KEY,
           -- so the earlier COALESCE pseudo-PK cannot be built as written):
           --   CREATE UNIQUE INDEX ... ON batch_item(batch_id, item_id)      WHERE item_id IS NOT NULL;
           --   CREATE UNIQUE INDEX ... ON batch_item(batch_id, ad_hoc_label) WHERE ad_hoc_label IS NOT NULL;
           -- durable per-option OUTCOME log — no person_id. This is what reporting reads (§6).

batch_response(id PK, batch_item_id FK -> batch_item NOT NULL,
               session_participant_id FK NOT NULL,
               choice TEXT NOT NULL, responded_at DATETIME,
               UNIQUE(batch_item_id, session_participant_id))
                                                                     -- EPHEMERAL, in-batch-only state used to
                                                                     -- detect "has everyone responded" and to
                                                                     -- roll up yes_count/no_count onto
                                                                     -- batch_item at close. DELETED at batch
                                                                     -- close — a hard rule, not a "safe to
                                                                     -- prune" suggestion; see §5.5.
                                                                     -- Referencing batch_item.id (not a
                                                                     -- (item_id, ad_hoc_label) pair) means a
                                                                     -- response can only ever point at an
                                                                     -- option actually in the batch, and
                                                                     -- relabeling an ad hoc option can't
                                                                     -- orphan its responses.
```

Notes:

- **No table anywhere ties a vote choice to a durable identity — because §5.5 requires deletion, not
  because rows are merely "prunable."** `session_participant` is scoped to one session and is deleted
  with it; `batch_response` is operational, not historical, and is deleted at batch close. This is a
  *stronger* privacy posture than the old "never shown, but stored raw forever" design — but it is only
  true if the lifecycle rules in §5.5 ship as part of M3. They are acceptance criteria, not suggestions.
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
submission backlog item). One honest caveat: `session.group_id` is NOT NULL, so "zero setup" really
means "zero setup after account + group creation" — a brand-new host creates an account and a group
before their first ad hoc session. Accepted: the group is the tenancy anchor everything else scopes
through, and it's a one-time 30-second step.

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
looks like a per-person vote, and §5.5 makes its disposal a requirement rather than an intention.

### 5.5 Vote-data lifecycle (hard M3 requirements — this is what makes the privacy claim structural)

The claim "no durable per-person vote" is earned by these rules, all of them M3 acceptance criteria
with tests:

1. **`batch_response` rows are deleted in the same transaction that closes their batch** and writes the
   rollup (`yes_count`/`no_count`/`outcome`) onto `batch_item`. Not a background sweep, not "prunable
   later" — the close transaction that commits the aggregate also removes the per-person rows. A batch
   that is closed has zero `batch_response` rows, ever, and a test asserts exactly that.
2. **`session_participant` rows are deleted when their session reaches `complete` or `expired`.** What
   survives a finished session: the `session` row itself (code, timestamps, group), `batch` rows, and
   `batch_item` outcome rows — nothing that names a voter or links an account to participation.
3. **Session expiry is defined, not implied.** A session left in `lobby` or `voting` becomes `expired`
   after **24 hours of inactivity** (no join, no response, no host action). Enforcement is lazy — any
   route that loads a session first applies the expiry check-and-transition — plus the host's explicit
   "end session" action, which moves `voting → complete` (treating missing responses per the manual-close
   rule, §5.6). Lazy enforcement means no scheduler dependency; the invariant is "no expired-eligible
   session is ever *served*," not "a daemon marks rows on time."
4. **Aborted sessions clean up the same way.** Expiry (rule 3) triggers the participant deletion of
   rule 2 and deletes any `batch_response` rows of a batch that never closed — an abandoned mid-vote
   batch does not preserve votes just because nobody clicked close. Its `batch_item` rows keep
   `outcome = NULL` and their counts stay 0: unclosed means unreported.

### 5.6 Session & batch state machines (M3 spec of record)

Re-adopted from plan v1 by explicit reference, still binding: **D5** (manual close counts missing
responses as "no"), **D6** (batch assembly/ordering mechanics), **D13** (over-target resolution: host
picks which keeps stay when a batch agrees on more than the remaining target). Everything else about
M3 state lives here, not in the old doc:

- **`session.status`: `lobby → voting → complete`, with `expired` reachable from `lobby` or `voting`**
  (only via the inactivity rule in §5.5; `complete` only via the host). Transitions are host-triggered
  (`start voting`, `end session`), require the host guard (the session's `host_account_id`, re-checked
  server-side), and are **idempotent** — a double-submitted transition applies once (CLAUDE.md
  non-negotiable #7); replaying `start voting` on a `voting` session is a no-op, not an error, and
  `times_offered`/`times_kept` increments happen only in the single batch-close transaction.
- **`batch.status`: `open → closed`.** Two values, no others. A batch closes automatically when every
  current roster member has responded to every option, or manually by the host (missing = "no", per D5).
  Close is idempotent; the rollup-and-delete of §5.5 happens exactly once.
- **Roster rule under open join:** joining is open (link/code) **only while the session is in `lobby`
  or between batches in `voting`** — a participant cannot join mid-batch (the unanimity denominator for
  an open batch is frozen at that batch's start). A visitor hitting a mid-batch session sees a waiting
  state, not a ballot. Joins are refused outright for `complete`/`expired` sessions.
- **The host is also a participant** if and only if they join the roster like anyone else — hosting
  controls (start, close, accept-majority, end) come from `host_account_id`, never from roster
  membership, and the host's ballot carries no extra weight.
- **Host participant removal exists (M3 scope, not backlog).** The host can remove a participant while
  no batch is open; removal deletes the participant row (and, mid-`lobby`, is invisible). Rationale:
  the keep rule is unanimity over the roster, so one ghost row — a second device, a joiner who left —
  makes unanimity mechanically unreachable. Duplicate joins are otherwise allowed (no auth to vote
  means no dedup key; that's the accepted trust model of a family tool, stated here deliberately), so
  the remedy has to be a host control rather than a constraint.
- **Session codes:** generated with collision retry against the permanent `UNIQUE(code)` (codes never
  recycle); join-by-code gets rate limiting at M5 (§8) since codes are now a cross-tenant guessing
  surface on a shared deployment.

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

**Tenant scoping is load-bearing here, not optional — and it has two join paths, not one.**
Library-derived data scopes through `collection.group_id`; session-derived data (including every ad hoc
`batch_item`, which has no `item_id` and therefore *no collection*) scopes through
`batch → session.group_id`. A query that only follows the collection path silently drops ad hoc outcomes
at best and leaks them at worst. Where a report joins both, the two group ids must agree.

Enforcement is structural, not per-query discipline: **every M4 route takes a `group_id`, guards it with
the existing `require_group_admin`, and starts every query from that group id** — one choke point instead
of N remembered filters. Acceptance criteria for every M4 endpoint include a cross-tenant negative test:
an account in group B requesting group A's report gets 404, and group A's ad hoc *and* library outcomes
never appear in group B's numbers. This didn't matter under the old single-household design; it matters
now because the database holds other people's groups, and this project has already shipped (and fixed)
exactly this class of leak twice — see `docs/OSCAR-REVIEW-code-2026-08-29.md`.

## 6.1 Single shared database, not database-per-tenant

One SQLite database serves every group on the deployment — the same file M0–M2b already write to.
Isolation between groups is enforced at the application layer (every tenant-owned table traces back to a
`group_id`), not at the storage layer. This was implicit in the schema (§5) but is worth stating as a
locked decision: database-per-tenant would mean per-group backup/restore, per-group migrations, and a
routing layer to pick the right DB file per request — real infrastructure this deployment doesn't need at
its current scale (Charlie's VPS, a handful of groups). Revisit only if the platform outgrows a single
SQLite file, not preemptively.

**The blast radius of this decision, owned explicitly:** with no storage-layer backstop, one missed
`group_id` filter exposes *every* group's data, read or write. The mitigations are cheap and standing:
(1) the choke-point pattern from §6 applies to every tenant-owned query in the app, not just M4 —
routes derive scope from a guarded `group_id`/ownership helper, never ad hoc per query; (2) every new
tenant-owned route ships with a cross-tenant negative test as a matter of course (the mutation-route
test band added 2026-08-29 is the template). History justifies the paranoia: `/library`'s unscoped
`_get_meal_collection()` and the home page's platform-wide counts both shipped, and were both found
live on 2026-08-29 before deployment made them incidents.

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
| M3 | **Session-based voting engine**: group/account-hosted sessions, account-optional participants, `session_target`, ad hoc + library-backed `batch_item`, outcome-only recording per §5.5's lifecycle rules, state machines per §5.6, host participant removal. **Mobile-first UI (§10): the voter flow presents one option at a time** — full-screen card, yes/no, progress — not a 15-row grid. | Net-new build against this doc; old M3 spec (§9 of plan v1) is void except D5/D6/D13, re-adopted by explicit reference in §5.6 — everything else about M3 state lives in this doc now | [ ] unapproved until this doc is approved |
| M4 | **Reporting & discovery** (§6) — supersedes "history & favorites" (broader scope: trend/tag correlation, not just `times_kept`). **Every query scoped to the requesting account's own groups (§6)** — a new hard requirement multi-tenancy introduces that didn't exist in the old single-household plan. | Expanded from old M4 | [ ] |
| M5 | Hardening, deployment docs, backup/restore. Single shared SQLite DB (§6.1) — backup/restore story unchanged (still one file). **Locked (2026-08-29): no site-wide passphrase gate.** Real accounts (M2a) are the security boundary. `Settings.access_key`/`SP_ACCESS_KEY` already removed — dead code, never enforced. **Hard pre-deployment items (accounts being the sole boundary makes these blockers, not polish):** (1) login attempt limiting — unlimited online password guessing is currently possible; (2) a decision on email enumeration: signup's "That email is already in use" is an email oracle today; either accept that openly or make signup non-revealing (awkward without outbound email — if accepted, record it as accepted, not overlooked); (3) join-by-code rate limiting (§5.6 — codes are a cross-tenant guessing surface); (4) the login timing side-channel fix (dummy hash on unknown email — the smallest of the four, tracked in REQUESTS.md). Plus **PWA packaging (§10)**: manifest + icons + installability, so voters get a home-screen app without app stores. | Gate question resolved; security items promoted from REQUESTS.md follow-ups to M5 blockers per the 2026-08-29 Oscar plan review | [ ] |
| M6 | External API + MCP. **Locked change from the old plan: tokens are per-group, not one shared household key.** A single global `DD_API_KEY`/`SP_API_KEY` would let one group's AI tools read every other group's data on the same deployment — a real leak now that other people's groups live in this database, not a hypothetical. Each group's owner generates and can revoke their own group's token; MCP tools operate on generic `item`/`collection` endpoints (not meal-specific), scoped the same way as M4's reporting. Four requirements stated now so M6's implementer doesn't invent them: **(a) tokens are stored hashed**, like every other credential in this codebase — the plaintext is shown once at generation; **(b) ownership transfer forces token rotation** — the departing owner knows the token, so transfer revokes it and prompts the new owner to generate a fresh one; **(c) verb scope: tokens can read/write the group's library items and read its reports — they cannot create, drive, or vote in sessions** (voting is a humans-in-a-room mechanism; an AI tool with a vote is out of scope by the charter's own no-in-app-AI stance); **(d) a token resolves to exactly one group at auth time, before any tool logic runs** — per-tool scoping checks are exactly the hand-rolled inconsistency this platform keeps getting burned by. The MCP tool list itself is M6-planning-time detail, deliberately open. "AI lives outside the app" still holds — it now applies per-group, not just to Charlie's own tools. | Token-scoping question from the original table is now a locked decision, not an open item | [ ] |

## 9. Client platform & design (locked 2026-08-29)

Charlie's direction: the people *voting* — and usually the host *starting* a vote — are on phones; the
person curating collections is often at a desktop. That ordering now drives the client decisions:

- **Mobile-first, as a responsive web app.** Every M3+ screen is designed for a phone viewport first;
  desktop is the adaptation. The library/collection-management screens may stay desktop-comfortable, but
  they still have to work on a phone. Existing M0–M2b templates get brought under this rule by the
  design reskin (below), not piecemeal.
- **No SPA — server-rendered pages plus htmx and SSE.** The voting flow is taps and reveals, not a rich
  client app. Live behavior (lobby roster filling in, batch closing, results reveal) uses SSE or
  short-poll via htmx — which is already vendored — keeping the charter's no-build-step/no-Node rule
  intact. This is a decision, not a deferral: an SPA proposal reopens it only with Charlie's word.
- **PWA packaging at M5**: web manifest, icons, installability — an app-on-the-home-screen experience
  with no app store. Native apps are explicitly not planned; if they ever happen, M6's API is the path
  and the backend does not change.
- **Batch presentation on mobile is one option at a time** (M3): full-screen card, large yes/no
  targets, "4 of 15" progress. Same batch mechanics, same schema — presentation only. Desktop may show
  a denser list.
- **Collection-scoped routing**: the library moves from the implicit "first collection that exists" to
  honest URLs — `/collections/{id}` (browse) and `/collections/{id}/items/{item_id}` (detail/edit),
  with a collections index as the post-login hub and `/library` kept as a redirect to the account's
  first meal collection. This closes the multi-group dead end found in the 2026-08-29 code review
  (accounts in two groups could never reach the second group's library) and matches the data model that
  already exists. Lands before M3 so the voting engine never builds on the single-collection assumption.
- **Design rework is in flight** (Claude Design). The current handoff bundle in `Design Handoff/` is
  explicitly desktop-first and predates this section — it is superseded as a *layout* reference. The
  corrected brief for the design pass is `docs/DESIGN-BRIEF-mobile.md`. Visual/template changes to the
  running app wait for that pass and land as one reskin slice; until then, code slices stay
  template-light.

## 10. Rename

Product: **SamePage**. This collection/module: **Meal Planner** (was "Dinner Decider"). Repo, package
name, and env var prefix (`DD_*` → `SP_*`) updated alongside this doc; see commit for the mechanical diff.
GitHub repo renamed `vectorlanelabs/dinnerdecider` → `vectorlanelabs/samepage` on 2026-08-28, per Charlie's
explicit go-ahead. Local clone directory renamed to match (`samepage-app`).
