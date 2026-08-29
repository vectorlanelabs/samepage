# Oscar review — SamePage v2 architecture plan (2026-08-29)

> Reviewer: Oscar persona (`ai-grouch-claude` skill), run on the Fable model, Planning and debate mode.
> Target: `docs/PLAN-v2-samepage.md` as it stood on 2026-08-29, plus `CHARTER.md`, `ROADMAP.md`,
> `REQUESTS.md`, and the last five `docs/DEVLOG.md` entries for decision history. This is a review of the
> **architecture plan**, not shipped code — M3 (session-based voting) had not been built yet. A separate
> review of the actually-shipped code (M0/M2a/M2b) was run the same day; see its own file if present.
>
> Saved verbatim (with only formatting cleanup) after Charlie asked whether the review had been written
> anywhere durable — it hadn't been, until now. Status of each finding as of the time of writing: **not yet
> acted on** — this is the raw review, not a tracked disposition. Cross-reference `REQUESTS.md` and
> `docs/DEVLOG.md` for what happens to these findings next.

---

## Executive verdict

**Needs changes.**

The strongest version of this plan is genuinely good: generalizing the voting engine *before* M3 exists is the right call at the right time, single-shared-deployment over federation is correctly reasoned, and "record outcomes, not voters" is a real architectural improvement over "store raw votes forever but promise not to show them." I tried to knock those pillars over and couldn't. But the plan as written has one schema construct that cannot be implemented as specified, a privacy claim that is asserted rather than enforced (and then overclaimed as "structurally true" in REQUESTS.md), several missing invariants that are exactly the kind M3's implementer will silently invent (this project has already been burned by that once — M2a's `Account.is_admin`), and live docs that contradict the plan's freshly locked decisions. None of this invalidates the architecture; all of it should be fixed in the doc before M3 is approved, because this doc is the binding spec and its gaps become the implementer's guesses.

Coverage limitation: there is no M3 code, so async integrity and API-contract fidelity were reviewed only as far as the spec goes; data-access semantics were checked against the schema and the landed M2a/M2b code, not against queries that don't exist yet.

## Blocking issues

### 1. `batch_item` / `batch_response` primary keys are pseudo-SQL that cannot be built as written
- **severity**: blocking (for plan approval — this is the core M3 table)
- **evidence**: §5, `PK(batch_id, COALESCE(item_id, ad_hoc_label))` on `batch_item`, and `PK(batch_id, session_participant_id, COALESCE(item_id, ad_hoc_label))` on `batch_response`.
- **why it breaks**: SQLite does not allow expressions in a PRIMARY KEY constraint, and SQLAlchemy can't model one. The implementer *must* deviate from the spec here, and the spec doesn't say how — so the actual uniqueness semantics (the thing the PK exists to guarantee: one row per option per batch, one response per participant per option) are left to whoever builds M3. The real shape is a surrogate `id` PK plus two partial unique indexes (`UNIQUE(batch_id, item_id) WHERE item_id IS NOT NULL`, `UNIQUE(batch_id, ad_hoc_label) WHERE ad_hoc_label IS NOT NULL`) plus a `CHECK` that exactly one of `item_id`/`ad_hoc_label` is set (the comment says "exactly one set" but no constraint enforces it). Same treatment for `batch_response`, which additionally needs its (item_id, ad_hoc_label) pair constrained to reference an option *actually in that batch* — as written, nothing stops a response row for an item the batch never offered, which would silently corrupt the rollup counts.
- **what would change my mind**: nothing — this is a factual SQLite limitation. The fix is a paragraph in §5, not a redesign.

### 2. The "no durable per-person vote" invariant is a policy hope, not a mechanism — and the docs already overclaim it
- **severity**: blocking (it's the plan's headline privacy claim)
- **evidence**: §5 note ("`batch_response` is explicitly operational, not historical… **Safe to prune** after a batch closes"), §5.4, and REQUESTS.md's Resolved section: "Now **structurally true**, not just a policy: the v2 schema never stores a durable per-person vote in the first place."
- **why it breaks**: `batch_response` ties a vote choice to `session_participant_id`, and `session_participant.account_id` ties that to a real account. "Safe to prune" is not "is pruned." The plan never *requires* deletion — no lifecycle rule, no transition step, nothing. If the M3 implementer ships rollup-without-delete (the natural lazy implementation, since deleting is extra work with no visible feature), every logged-in participant's per-item votes persist forever, and the schema is exactly the old "stored raw, never shown" design wearing a better label. The claim in REQUESTS.md that this is "structurally true" is false as specified — it's true only if a rule the plan doesn't state gets implemented. Second gap in the same invariant: sessions have an `expired` status but no expiry mechanism, owner, or trigger is specified anywhere. A session abandoned mid-`voting` retains its `batch_response` rows and its `session_participant` rows (display names + account links, i.e., "who was in the room") indefinitely. §4 calls participants "Ephemeral (kept only as long as the session record exists)" — and nothing ever ends the session record.
- **what would change my mind**: §5 stating, as a hard M3 requirement: (a) `batch_response` rows for a batch are deleted in the same transaction that closes the batch and writes the rollup; (b) what transitions a session to `expired`/`complete`, and what happens to `session_participant` rows then. Then the "structurally true" language is earned.

### 3. Two missing tenancy invariants on `session` — the exact class of gap the M4/M6 decisions were made to close
- **severity**: blocking
- **evidence**: §5: `session(group_id FK NOT NULL, host_account_id FK NOT NULL, collection_id FK NULL)`. Nowhere in §5, §4, or §8's M3 row does the plan state (a) that `host_account_id` must be an owner/admin of `session.group_id`, or (b) that `session.collection_id`, when set, must belong to `session.group_id`.
- **why it breaks**: Without (a), any signed-up account (signup is open, the app is internet-facing) can create sessions attributed to any group. Without (b), an account can host a session under its own group but point `collection_id` at another group's collection — and the batch-assembly logic will happily serve that group's entire item library to the session's voters. That is a full cross-tenant read of exactly the data M4's scoping rule was written to protect, reachable through the voting path M4's rule doesn't cover. The plan just spent two locked decisions (M4 scoping, M6 per-group tokens) closing cross-tenant leaks; it left the same leak open in the M3 schema it's approving.
- **what would change my mind**: the invariants stated in §5 as requirements (and, ideally, a note that session-creation routes go through `require_group_admin`, which already exists in `app/auth.py`).

## Major concerns

### 4. No rate limiting or attempt limiting anywhere, now that accounts are the *sole* security boundary
- **severity**: major
- **evidence**: Decision #1 (2026-08-29): no site gate, "real accounts are the security boundary." Charter D16's PIN-attempt limiting died with PINs in M2a. `grep -ri 'rate|limit|attempt|lockout|throttle'` over `app/` finds nothing; `app/routes/auth.py` `POST /login` will verify passwords as fast as an attacker can post them. Nothing in the v2 plan's M5 row reintroduces it.
- **impact**: An internet-facing deployment with open signup, unlimited online password guessing against the only boundary the platform has. Related and worse than the tracked timing side-channel: `POST /signup` returns "That email is already in use" (`app/routes/auth.py:111`), so email enumeration is already trivially available through signup — the ~60ms timing channel REQUESTS.md tracks is the *hard* way to get information the signup form hands out for free. The REQUESTS.md item's framing ("fix is cheap… before any public launch") is fine for the timing channel itself, but the follow-ups list is missing the two bigger siblings: login throttling and the signup oracle. To answer the direct question I was asked: the timing side-channel does *not* need to jump the queue — it's the least of the three; the missing rate limiting is the one that shouldn't wait past M5.
- **suggested fix**: add to M5 (or REQUESTS.md follow-ups) as hard pre-deployment items: login attempt limiting, a decision on whether email enumeration is accepted (if not, signup must go non-revealing, which is awkward without email — say so explicitly), and rate limiting on session-code join once M3 exists (see #7).

### 5. M4's scoping rule has the right intent but not enough teeth, and as literally written it misses ad hoc data
- **severity**: major
- **evidence**: §6: "Every reporting query must filter through `collection.group_id` to groups the requesting account actually belongs to."
- **impact**: Two problems. First, the rule names one join path — `collection.group_id` — but ad hoc `batch_item` rows have no `item_id` and hence no collection; their only tenant linkage is `batch → session → group_id`. Any session-level or mixed report scoped "through `collection.group_id`" as instructed either silently drops ad hoc outcomes or, if the implementer joins sessions in without re-scoping, leaks them. The rule needs to say: scope through `session.group_id` for session-derived data, `collection.group_id` for library-derived data, and both must agree. Second, it's a per-query discipline requirement with no structural enforcement — one forgotten filter is a silent full-tenant leak (see #6), and this codebase's own history (M2a's invented `is_admin`, caught only by line-by-line review) says implementer discipline is not the control to bet on. The fix is cheap: mandate that every M4 route takes a `group_id`, guards it with the existing `require_group_admin`, and starts every query from that group's id — one choke point instead of N remembered filters — plus a required negative test per endpoint ("account in group B requesting group A's report gets 403/404, and group A's ad hoc and library data never appear in group B's numbers").
- **suggested fix**: amend §6's requirement with the dual join-path rule, the single-choke-point pattern, and cross-tenant negative tests as acceptance criteria. That's three sentences and it converts "scope it" into something an implementer can't quietly cut.

### 6. §6.1 is honest about the decision but silent about blast-radius containment
- **severity**: major
- **evidence**: §6.1 locks single-shared-SQLite with app-layer isolation and says nothing about how a missed `group_id` filter is caught.
- **impact**: The decision itself is right at this scale — database-per-tenant for a handful of groups on one VPS is real operational cost for no benefit, and the plan's reasoning (backups, migrations, routing) is sound. But the blast radius of one missed filter is *every group's data*, read or written, with no storage-layer backstop and no proposed detection. The plan should own that tradeoff explicitly and buy the cheap mitigations: the choke-point pattern from #5 applied everywhere, cross-tenant tests as a standing requirement for every new tenant-owned query (not just M4), and — worth a line — the fact that the current code already violates the isolation story: `/library`'s `_get_meal_collection()` (`app/routes/library.py:54`) selects the first meal collection *globally* with no group filter, and library mutations gate on "any signed-in account." REQUESTS.md calls this "fine while there's one group in practice" — but signup is open and nothing enforces one group. It's contained only because M5 deployment hasn't happened. That follow-up must be re-labeled a hard pre-deployment blocker, not "tighten before real multi-group usage, whenever."
- **suggested fix**: one paragraph in §6.1 naming the failure mode and the two mitigations; promote the library-gating and single-collection-routing follow-ups to explicit M3-or-M5 blockers.

> **Note added post-review (2026-08-29, same day):** this exact `_get_meal_collection()` gap was found independently by Charlie clicking through the running app a few hours after this review was written — not by reading this review — and fixed the same day (see `docs/DEVLOG.md`). Confirms this was a real, live bug, not a theoretical one.

### 7. M3's state-transition story is "carries over from a spec this document voids"
- **severity**: major
- **evidence**: §8 M3 row: "old M3 spec (§9 of plan v1) is **void** — roster-freeze/batch-assembly/unanimous+majority *mechanics* carry over, identity plumbing does not." §5.3 similarly points at "D6, D13, §9.3/§9.6 in the old plan."
- **impact**: The binding spec for M3's core mechanics is a superseded document, with the live/dead boundary defined by one adjective ("mechanics"). Concrete ambiguities an implementer must resolve by guessing: Does roster-freeze survive at all, given §2's "anyone with the link/code can join"? (If yes, "anyone can join" is only true during `lobby` — what does a mid-`voting` visitor see? If no, what's the unanimity denominator?) What are `batch.status`'s values beyond `'open'`? What transitions a session `lobby→voting→complete`, and are they idempotent (CLAUDE.md non-negotiable #7 demands it, and `times_kept`/`times_offered` increments at batch close are exactly where double-submit corrupts data)? Is `batch.track_label` constrained to `session_target` rows? Does the host vote? The plan's own convention ("per-milestone task detail gets filled in immediately before that milestone starts") legitimately defers *task* detail — but a state machine's states and transitions are architecture, not task detail, and this doc supersedes the only place they were written down.
- **suggested fix**: a short §5.6: session and batch state machines (states, transitions, who triggers them, idempotency note), the roster rule under the new join model, and an explicit list of which old-plan decisions (D5, D6, D13) are re-adopted by reference as still-binding.

### 8. Duplicate participants can wedge a session, and no host remedy exists
- **severity**: major
- **evidence**: §5: `session_participant` has no uniqueness on `(session_id, account_id)` and anonymous participants can't be deduped at all; carry-over rule D5: auto-close requires *every* roster member to vote on *every* option.
- **impact**: One person opening the session link on two devices (or a joiner who immediately leaves) creates a roster entry that never votes — auto-close never fires and unanimity is mechanically unreachable. Manual close (missing = no) is the escape hatch *if* it carries over, but the plan doesn't say so, and there is no "host removes a participant" action anywhere in the schema or backlog. For a product whose keep rule is unanimity over the roster, "a ghost participant makes unanimity impossible" is a first-session-with-real-family failure, not an edge case. To be clear about what I'm *not* flagging: multi-voting by anonymous link-holders is inherent to "no auth to vote" and is an acceptable product stance for a trust-based family tool — but the plan should say that stance out loud, and give the host the kick/remove control that makes the trust model operable.
- **suggested fix**: host-side participant removal (pre-close) in the M3 scope; state whether manual-close-as-no carries over; one sentence acknowledging the trust model.

### 9. M6's per-group token decision locks the right headline and leaves the operable parts unspecified
- **severity**: major
- **evidence**: §8 M6 row: owner generates/revokes; "MCP tools operate on generic `item`/`collection` endpoints… scoped the same way as M4's reporting."
- **impact**: The decision itself is correct and the leak reasoning is real. What's missing, in order of bite: (a) **Ownership transfer** — §4 makes ownership transferable; the departing owner still knows the token. Nothing says transfer forces (or even prompts) rotation. That's the difference between "revocable" and "revoked when it matters." (b) **Storage** — nothing says tokens are stored hashed. This codebase hashes every other credential; say it, or an implementer will store plaintext for the lookup convenience. (c) **Scope semantics** — read vs. write, whether a token can drive sessions/voting or only library/reporting, is unstated; "scoped the same way as M4" covers *which group*, not *which verbs*. (d) **MCP tool scoping is asserted, not specified** — no tool list exists anywhere, and the mechanism (token→group binding resolved once at auth, with every tool operating inside that binding, vs. per-tool checks) is exactly the kind of thing that gets hand-implemented inconsistently across tools. (a)–(c) are one sentence each; (d) is legitimately M6-time detail but should be named as an open design item rather than implied to be settled.
- **suggested fix**: add those sentences to the M6 row; leave the tool list for M6 planning but require "token resolves to exactly one group before any tool logic runs" as the stated mechanism.

### 10. Live docs contradict the plan's own locked decisions
- **severity**: major (doc-integrity, not code — but these docs are the implementer's contract)
- **evidence**:
  - `ROADMAP.md` M5 row still reads "**Open question for Charlie**: does the old site-wide passphrase gate still fit… Tracked in REQUESTS.md" — that question was answered and locked on 2026-08-29; REQUESTS.md and the plan both say so. The roadmap missed the sweep.
  - `CLAUDE.md` non-negotiable #5: "**PINs are stored hashed** (PBKDF2, per-person salt) — no plaintext PINs anywhere." PINs were removed entirely in M2a; the banner's claim that "everything below still applies to the M0–M2 code as it stands" is no longer true of this line.
  - `CLAUDE.md` #6: "admin-only routes enforced server-side (`is_admin`)" — `is_admin` was removed in M2a (its removal is documented in the DEVLOG as a *blocking finding*), and "Every `/api/v1` and `/mcp` route requires the Bearer token (`SP_API_KEY`)" plus the product-shape bullet's "Bearer `SP_API_KEY`" directly contradict M6's locked per-group-token decision. CLAUDE.md's product-shape section also still describes the meal-specific single-household session ("lunch/dinner targets… batches of 15 meals") as the binding product.
  - `CHARTER.md`: the banner scopes supersession to "identity (D2, D16…) and meal-specific (D10)" — but the Core-mechanic bullet "**Raw votes stay server-side for future learning**" and D9's "raw votes stored" are neither identity nor D10, so by the banner's own terms they're still active, and they contradict the v2 plan's central privacy claim. The banner's supersession list needs to name the vote-retention language too.
- **impact**: M3's implementer is instructed to read CLAUDE.md as binding constraints and will be following removed concepts and a superseded auth model. This project already learned (M2a) what happens when the implementer's written contract diverges from intent.
- **suggested fix**: one doc-sweep slice before M3 kickoff: ROADMAP M5 row, CLAUDE.md #5/#6 and product-shape, CHARTER banner scope line.

## Minor concerns and nits

Real minors:
- **§5.5 doesn't exist.** The plan cites "§5.5" three times (§3, §4, §5's notes) for its most important claim; sections stop at §5.4. Renumber or retitle — a binding spec shouldn't dangle its own load-bearing cross-reference.
- **Session codes are now a cross-tenant guessing surface.** `WORD-####` was fine for one household on a LAN-ish deployment; on a shared internet-facing platform, a guessed code drops a stranger into some family's live session. Needs: joins refused for `complete`/`expired` sessions (implied, not stated), and join-by-code rate limiting (ties to #4). Also `code TEXT UNIQUE` is unique *forever* across all sessions — fine, but then codes never recycle and the generator needs collision retry; say which.
- **Rollup matching for ad hoc options is by label string.** `batch_response` and `batch_item` correlate ad hoc rows via `ad_hoc_label` text equality; if labels are host-editable mid-batch, responses orphan. Cheapest fix is making responses reference the `batch_item` surrogate id from blocking issue #1 — which is another reason to fix that PK properly.
- **Hosting an ad hoc "what bar tonight" session requires creating a group first** (`session.group_id NOT NULL`). Probably fine — but it means the zero-setup pitch in §5.2 is really "zero setup after account + group creation." Worth one honest sentence.
- **`Category.legacy_sheet_index` still exists in `app/models.py:77`** — consistent with REQUESTS.md's "next time the seed pipeline is touched," just noting the plan/code delta is known and tracked, not missed.

Nits (taste, take or leave):
- `ROADMAP.md`'s M0 row still lists "CI" in the milestone description while non-negotiable #10 bans CI outright.
- `session_target.target_count` has no `> 0` check; `batch.seq` uniqueness exists but nothing says it's gapless or ordered — harmless, but a CHECK costs nothing.

## What the plan gets right

I came in expecting a pivot-shaped mess and did not find one. Plainly:

- **The pivot timing argument is airtight.** M3 was never built; generalizing `Vote`/`BatchMeal` before writing them is the one moment this refactor is nearly free, and the plan says exactly that instead of dressing it up.
- **Single shared deployment over federation** is the correct call, and the stated reason (federation is a distributed-identity problem; shared deployment dissolves the cross-group-invite feature into "everyone's already here") is the *actual* reason, not a rationalization.
- **Outcome-not-history is a real design improvement**, not privacy theater — `batch_item` with aggregate counts genuinely supports everything §6 wants (reject rate by tag, trends via `batch.closed_at`) without a person dimension. My blocking issue #2 is that the enforcement is missing, not that the design is wrong.
- **The restraint is disciplined throughout**: `*_detail` extension tables deferred until a second collection kind proves the pattern; cross-collection reporting explicitly not spec'd; ad hoc options reusing a column the backlog feature already needed; §6.1 refusing per-tenant databases the deployment doesn't need. This is the opposite of the generic-platform planning failure.
- **The decision history is real.** The DEVLOG shows M2a's review catching an invented `is_admin` flag line-by-line and M2b getting a genuine live smoke test — the process this plan will be executed under has teeth, which raises my confidence that the fixes above will actually land.
- Two suspicions I checked and dropped: the identity model is *internally consistent* — every place that touches `session_participant` (§2, §4, §5, DEVLOG) agrees account linkage is pre-fill-only and confers nothing; and the M2b clean-slate migration was legitimate (no real user data existed). The prompt asked whether any spot quietly assumes more identity than the model provides — I looked, and inside the plan itself, no spot does. The problems are the unstated *host* authorization (#3) and unstated response lifecycle (#2), not the participant model.

## Best next moves

Shortest path to an approvable doc — all spec edits, no code:

1. **Fix §5's two PKs** (surrogate id + partial uniques + exactly-one-of CHECK; responses reference `batch_item.id`). Kills blocking #1 and the label-matching minor at once.
2. **Write the lifecycle rule**: `batch_response` deleted in the batch-close transaction; define what expires a session and what happens to `session_participant` then. Kills blocking #2 and earns the "structurally true" claim REQUESTS.md already makes.
3. **State the two session invariants** (host must be owner/admin of `session.group_id`; `collection.group_id` must equal `session.group_id`). Kills blocking #3 in two sentences.
4. **Add §5.6 state machines** and re-adopt D5/D6/D13 by explicit reference; include host participant-removal.
5. **Sharpen M4** (dual join path, choke-point pattern, cross-tenant negative tests) and **add four sentences to M6** (hashed storage, rotation-on-transfer, verb scope, token-resolves-to-one-group mechanism).
6. **One doc-sweep slice**: ROADMAP M5 row, CLAUDE.md #5/#6/product-shape, CHARTER banner's supersession scope, the §5.5 dangling references.
7. **Re-file the security follow-ups**: add login rate limiting and the signup email oracle to the pre-deployment list; leave the timing side-channel where it is (it's the smallest of the three); promote library group-gating and collection routing from "eventually" to hard pre-deployment blockers.

That's roughly a day of spec work, and afterward this plan is approvable.

## Debate addendum

- **Strongest case for the other side**: "This is a first architecture pass by its own declaration — §5.6-style detail, token mechanics, and lifecycle rules are exactly the per-milestone detail the project's 'don't design to death' convention defers. You're demanding M3 task-planning inside the architecture doc."
- **Where that case fails**: The convention defers *task* detail, not *invariants*. "Responses must not outlive their batch," "the host must belong to the group," and "this PK is implementable" are architectural claims the doc already makes or depends on — §5.4 stakes the plan's headline privacy posture on a pruning behavior it never requires, and REQUESTS.md has already converted that hope into the closed status "structurally true." When a doc's *claims* outrun its *requirements*, that gap is the architecture review's business, precisely because everything downstream (M4's queries, M6's token scoping, the Resolved list) is already building on the claims. The doc-contradiction findings (#10) aren't design-to-death either — they're the implementer's binding contract disagreeing with the spec it implements, which this project has already paid for once.
- **What evidence would resolve the disagreement**: If Charlie rules that lifecycle and invariants are M3-planning-time material, fine — but then §5.4's claim should be softened to "will be made structurally true by M3's close-transaction rule," REQUESTS.md's "structurally true, not just a policy" line should be reverted to pending, and blocking #1 still stands regardless, because an unimplementable PK is wrong at any altitude.

---

**Bottom line for Charlie**: the architecture survives scrutiny — pivot, tenancy model, identity tiers, and outcome-only recording are all defensible and I'd concede the core design is better than what it replaced. It is not approvable *as written* because the spec's most important table can't be built as specified, its most important promise isn't required by anything, and three of its supporting documents currently disagree with it. All fixes are prose; none require touching landed code except the eventual rate limiting.
