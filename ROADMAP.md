# Same Page — Roadmap

Status legend: `[ ]` not started · `[~]` in progress · `[x]` done

## ⚠ Architecture pivot in progress (2026-08-28)

**M3 onward is unapproved.** Building M0–M2 as a single-household meal planner surfaced a bigger, more
useful shape: a generalized multi-tenant consensus-voting platform (**Same Page**), with meal planning
(**Meal Planner**) as its first collection. This changes identity/tenancy (M1 is being redone as M2a) and
generalizes the meal-specific schema (M2 is being redone as M2b) before M3 (planning sessions & voting,
never built) starts. Full architecture: `docs/PLAN-v2-samepage.md`. `docs/PLAN-v1-mvp.md` and
`CHARTER.md`'s identity/D10 decisions are superseded by that doc — left in place for history, not deleted.

## v2 (current target)

| ID | Milestone | Status | Notes |
|---|---|---|---|
| M0 | Foundation: scaffolding, FastAPI skeleton, SQLite models, **Alembic migrations**, session, security middleware, CI (built, then removed — CI is banned per CLAUDE.md non-negotiable #10; listed here as history) | [x] | Landed 2026-08-26 (`0a786dc`); 22 tests; review fixes applied. Stands as-is — no identity/tenancy coupling. |
| ~~M1~~ → **M2a** | ~~Household profiles (PINs)~~ → **Identity & tenancy**: `Account` (email+password), `Group`/`group_admin`, replaces `Person`+PIN entirely | [x] landed 2026-08-28 | PINs fully removed. Library CRUD gated on "any signed-in account" (interim — proper group-scoping lands in M2b, tracked in REQUESTS.md). See `docs/PLAN-v2-samepage.md` §4/§8. |
| **M2b** | **Generic collections & items**: `Collection`/`Item`/`meal_detail`, scoped `Category`/`Tag`, migrate the 155 seeded meals | [x] landed 2026-08-28 | Clean-slate schema (matches M2a's precedent — no real user data to preserve); `scripts/seed.py` now requires a `group_id` and is idempotent per-collection. `/library` URLs unchanged; multi-collection routing deferred (tracked in REQUESTS.md). Revises the M2 work (`6d22054`). §5 |
| **M2c** | **Pre-M3 correctness & routing**: Oscar code-review punch list (crash/oracle/redirect fixes, cross-tenant test band, dead-weight purge) + collection-scoped library routing (`/collections/{id}`, plan §9) | [x] landed 2026-08-29 | Closes the multi-group dead end before M3 builds on the single-collection assumption. Visual/template work explicitly excluded — held for the design reskin (plan §9). |
| **M2d** | **Quiet Kitchen reskin**: app.css rewritten on the `--sp-*` token system (light + dark), all templates restyled phone-first, CSS wordmark + favicon/PWA icon, focus-visible styling | [x] landed 2026-08-29 | Design bundle in `Design Handoff/`; session/voting screens arrive with M3 on this system. |
| **M3a** | **Voting schema + pure logic**: six session/batch tables (migration 0009 with the implementable partial-unique keys), `session_logic.py` (batch assembly, unanimity, majority, over-target, idempotent transitions), tests-first per non-negotiable #2 | [x] landed 2026-08-29 | Foundation for M3b–M3e; no routes yet. |
| **M3b** | **Session create + join + lobby**: host creates a session (tenancy-guarded, targets), join-by-code with no account, live lobby (htmx polling), host start/remove-participant | [x] landed 2026-08-29 | Voting UI is placeholder — batches are M3c. |
| **M3c** | **Voting flow**: start assembles batch #1 (track-ordered, meal-type-filtered, empty-pool-guarded), one-option-at-a-time cards, first-vote-stands submit, progress/waiting states (htmx-polled) | [x] landed 2026-08-29 | Batch close/rollup/results are M3d. |
| **M3e** | **Session progression & teardown**: next-batch with target tracking, host-decides-when-to-stop, finish (participant deletion §5.5), lazy 24h expiry, completion summary | [x] landed 2026-08-29 | Completes the voting engine. |
| **M3d** | **Batch close + results**: rollup to aggregate yes/no, outcome classification, per-person vote deletion (§5.5), times_kept/offered, results screen (aggregate-only), host majority accept/pass — all idempotent | [x] landed 2026-08-29 | Next-batch/targets/over-target/complete/expiry are M3e. |
| ~~M3~~ **DONE** | Session-based voting engine — built in slices M3a–M3e | [x] landed 2026-08-29 | Engine complete end-to-end: create → join (no account) → one-at-a-time voting → close/rollup/results → batch progression → finish. §5.5 lifecycle enforced (vote rows deleted at close, participants at session end, 24h lazy expiry). D13 over-target replaced by host-decides-when-to-stop (REQUESTS.md note). |
| ~~M4~~ **DONE** | Reporting & discovery (per-collection reject rates by item + tag, not-offered-lately) | [x] landed 2026-08-29 | Every query scoped through the guarded collection (§6 choke-point); cross-tenant 404 + isolation tested. |
| ~~M2e~~ **DONE** | **Seed purge + create-collection UI**: delete seed/, scripts/, reference/ (XLSX), test_seed.py; drop `Category.legacy_sheet_index`; add the create-collection flow a blank production DB needs (Charlie 2026-08-29: production deploys unseeded, no dice provenance in the repo) | [x] landed 2026-08-29 | Production DB is now blank/unseeded; users create collections in-app. |
| ~~M5a~~ **DONE** | **Google sign-in (pure SSO)**: modular provider interface + `auth_identity` table, Google OIDC flow, delete all password auth (code, column, tests). Locked by Charlie 2026-08-29 — Google only for now; Apple/others are later modules, Facebook ruled out. Plan §4. | [x] landed 2026-08-29 (pulled ahead of M3 per Charlie) | Local testing via mocked provider; real redirect URIs land with the domain. Kills the password-related M5 security blockers. |
| **M5b** | **Join-code rate limiting** (last pre-deploy security blocker): in-memory sliding-window per IP on the two code-guessing routes, polls exempt | [x] landed 2026-08-29 | SSO already removed the password-guessing blockers; this closes §8 M5's security list. |
| **M5c** | **PWA packaging**: web manifest, 192/512 + maskable icons, root-scope service worker, theme-color/apple meta — installable to home screen (plan §9) | [x] landed 2026-08-29 |
| **M5d** | **Deployment artifacts**: Dockerfile, docker-compose (app+Caddy), Caddyfile, WAL-safe backup + restore-check scripts, DEPLOY.md, .dockerignore | [x] landed 2026-08-29 | Single shared SQLite DB, not per-tenant (§6.1). Gate question **resolved 2026-08-29: no site gate; accounts are the boundary.** Hard pre-deployment security items (plan §8 M5): the M5a SSO slice (deletes the password surface and its three blockers) and join-by-code rate limiting. **Deploy path (Charlie, 2026-08-29): public-facing; container prepped externally now; GitHub Actions deploy pipeline set up by the lead AT M5 with Charlie's explicit go-ahead — the no-CI rule stands until then.** |
| **M6a** | **Per-group API tokens + JSON API**: owner-minted per-group Bearer token (256-bit, SHA-256 hashed, one-time reveal), `/api/v1` for library items + reports, scoped to one group, no sessions/votes | [x] landed 2026-08-29 | Delivers "AI lives outside the app" via a plain JSON API. |
| **M6b** | **MCP server** (FastMCP wrapper over the M6a operations) | [ ] **paused — needs Charlie** | Deferred by a lead decision (2026-08-29): adds a heavyweight new runtime dependency + a new protocol, hard to verify unattended, and the JSON API already covers the use case. See REQUESTS.md. |

## M8 — Loud Moments reskin (design handoff v5)

Source: `Design Handoff/README.md` (v5, Charlie-approved 2026-08-29, acid-green accent).
Branch `loud-moments`; commits stay local until Charlie's word (push = prod deploy).
Budget: 6 cycles. Compositions are unchanged — tokens/type/shape/link reskin only.

| ID | Slice | Status |
|---|---|---|
| R1 | Tokens + global styles: `--sp-*` swap (light+dark), Schibsted Grotesk + mono fonts, flat 10/12px buttons/cards, ink+acid-underline links, theme-color/manifest, interim tint/avatar/chip mappings | [x] 00b09ef |
| R2 | Session-flow deltas: voting card (mono tags/count, 40/800), results (mono labels/counts, accent CTA), ink-ground completion payoff, share/lobby/waiting mono voice | [x] 9db92ed |
| R3 | App-side deltas: hub, landing, library, groups, edit, report — mono metas, chip/pill retirement, link treatment sweep | [x] 1377a42 |

## M7 — Design fidelity (Oscar design review 2026-08-29)

Source: `docs/OSCAR-REVIEW-design-2026-08-29.md` vs `Design Handoff/` v4. Run started 2026-08-29 on
branch `quiet-kitchen-fidelity`. **Commits stay local — Charlie pushes (push = prod deploy via CI).**
Budget: 14 cycles. Standing decision: breakfast/lunch/dinner multi-select tracks are plan-approved
(`docs/PLAN-collection-templates.md`) and stay; the handoff is stale there (REQUESTS.md item).

| ID | Slice (review findings) | Status |
|---|---|---|
| S1 | Chrome model: delete mobile topbar nav; per-screen-class chrome (hub = brand+avatar, inner = back+title, session = chromeless); sidebar unchanged on desktop (F1, F11-chrome) | [x] c7c38b5 |
| S2 | Hub/IA: `/collections` becomes the signed-in home (`/` redirects), composed hub per artboard — greeting, group + switch, card meta, last-session footer, ink Host + Join-with-code CTAs; delete invented `/` hero page (F2) | [x] c7c38b5 |
| S3 | Create session: collection radio cards + dashed ad-hoc (collection default), per-track steppers, bottom-pinned Create (F3) | [x] aac5435 |
| S4 | Share screen: `/s/{code}/share` (host-only) — 40px mono code, Copy invite link, native Share, joined count, Go to the lobby; create redirects here (F4) | [x] aac5435 |
| S5 | BUG: session-scoped recipe view for voters (participant/host of that session, item offered in that session); voting card links there (F5) | [x] 6181fff |
| S6 | Voting screen: progress bar, context line (collection · group), centered card + bottom-pinned Yes/No (F6) | [x] 6181fff |
| S7 | Results + complete: outcome color labels (accent/host/faint), persistent kept-by-host group, white majority card w/ violet label, quiet counts, End session early (danger), target-met copy, completion screen per artboard (F7, F11-complete) | [x] d1b1f03 |
| S8 | Join/lobby/waiting compositions: invite landing w/ session+group+chips, voter lobby centered + avatar chips, host lobby "N at the table" + lock caption + code pill, waiting ✓ + progress card (F11, F12-lobby) | [x] c94fbc5 |
| S9 | Library phone: compact rows-in-card, actions off browse (archive stays in edit), one-line Type/Tags/Time filter row, edit-screen tags = applied-only + "+ tag" adder (F8-phone, F9) | [x] 59f047e |
| S10 | Library desktop: sidebar w/ collections + pinned Host, table layout (name/type/tags/kept/last kept) + Sort + Clear (F8-desktop) | [x] db5f799 |
| S11 | Copy sweep to handoff v3 + small fixes: captions, em-dash asides, recipe back-link/source-domain/footer, groups page composition, report "never kept" conditional, phone landing composition, API-panel copy (F10, F12) | [x] b81c441 |

Detailed build plan: `docs/PLAN-v2-samepage.md` (current) · `docs/PLAN-v1-mvp.md` (superseded, kept for
history) · Scope & stop criteria: `CHARTER.md` (identity/D10 sections superseded — see pivot note above)

## Post-MVP (stubs — intent only, see `docs/POST-V1.md`)

- **v1.5 — Planning refinements & richer library**: recency-weighted batches, stale-meal suggestions, per-person constraints, planned-week view, re-run last week, meal photos, **recipe-use experience (cooking view, printing)**, better filtering, looser keep rules if needed.
- **v2 — External intelligence via API & MCP (no in-app AI)**: recipe parsing (photo/link → recipe), discovery, trend analysis, and favorites surfacing all run in Charlie's AI tools through the app's API/MCP (D17) — no LLM keys or AI code in the product.
- **Later / explore**: grocery list generation (explicitly out of MVP), pantry mode, mobile apps, calendar/recurring rhythm, integrations, data export. (Multi-household hosting + real accounts + public deployment are no longer "later" — they landed in M2a/M2b.)

Each gets a full plan doc when its trigger condition fires.

## Change log

- **2026-08-29 (2)** — **Oscar reviews applied + mobile-first locked.** Both 2026-08-29 Oscar reviews
  (plan + shipped code, saved in `docs/`) dispositioned: plan §5 PKs made implementable, vote-data
  lifecycle written as §5.5 (deletion is now a requirement, not a hope), session tenancy invariants and
  §5.6 state machines added, M4/M5/M6 rows sharpened, security follow-ups promoted to M5 blockers.
  New plan §9 locks Charlie's client direction: **mobile-first responsive web app, no SPA**
  (server-rendered + htmx/SSE), PWA at M5, one-option-at-a-time voting on mobile, collection-scoped
  library routing before M3. Design rework (Claude Design) re-briefed mobile-first via
  `docs/DESIGN-BRIEF-mobile.md`; visual/template changes held for that pass. New M2c row tracks the
  pre-M3 correctness/routing slice. Doc sweep fixed CLAUDE.md's stale PIN/`is_admin`/global-API-key
  lines and CHARTER's banner scope.
- **2026-08-28** — **Architecture pivot: Same Page.** Renamed from Dinner Decider; multi-tenant consensus
  platform (`docs/PLAN-v2-samepage.md`) with Meal Planner as the first collection. Real accounts +
  group ownership/admin replace `Person`+PIN entirely (no PINs anywhere); meals generalize to
  `collection`/`item`; voting outcomes are recorded per-item with aggregate yes/no counts and **no
  person-level history**, keeping the privacy invariant even stronger than before. M3+ unapproved until
  this doc is signed off; M1 becomes M2a (identity/tenancy), M2 becomes M2b (generic collections).
  Pre-reveal ad hoc option submission logged as backlog, not blocking.
- **2026-08-26** — **Plan 1 committed.** Charter, v1 MVP build plan (weekly planning sessions, pre-seeded library), and post-MVP stubs; legacy spreadsheet moved to `reference/`; seed data generated (155 meals); architecture: backend, VPS-hosted. Awaiting charter approval.
- **2026-08-26** — **Initial plan review applied** (`docs/INITIAL-PLAN-REVIEW.md`, 12/12 findings accepted): roster-freeze lobby phase, Alembic migrations (M0), WAL-safe backups with restore verification (M5), curated 27-meal `both` seed subset (lunch track populated), admin/PIN-hashing/CSRF security, strengthened vote-privacy invariant, README rewritten (concept moved to `docs/ORIGINAL-CONCEPT.md`), deployment wording fixed, recipe-use experience attached to v2 intake, batch size fixed at 15, idempotent session transitions, deactivate-not-delete. Awaiting charter approval.
- **2026-08-26** — **Majority-vote host acceptance** (Charlie): unanimous auto-kept; majority-yes meals (`yes > no`, ties excluded) shown with aggregate counts; host accepts while slots remain; `kept_by='host'` recorded. Awaiting charter approval.
- **2026-08-26** — **AI lives outside the app** (Charlie): new M6 — token-authenticated JSON API (`/api/v1`, `DD_API_KEY`) + FastMCP server so Charlie's AI tools import meals/recipes and run discovery/trends via MCP. No in-app AI, no LLM keys, ever. Seeded recipe links: Option B (real MCP imports prove the path at M6); Option A available. Awaiting charter approval.
