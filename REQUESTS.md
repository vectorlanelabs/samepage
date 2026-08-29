# Requests (non-blocking channel)

The build is complete and deployment-ready. The items below are the only things that want your
attention — split into what needs a decision from you vs. what's just parked.

## Needs your decision

- [ ] **Before go-live: Google OAuth client + domain + CI go-word.**
  1. **Google OAuth client.** In Google Cloud Console: create/reuse a project → "APIs & Services" →
     "OAuth consent screen" (External; app name "Same Page"; your email; default scopes; publish) →
     "Credentials" → "Create credentials → OAuth client ID → Web application". Add the authorized
     redirect URIs `https://<your-domain>/auth/google/callback` and (for local testing)
     `http://localhost:8000/auth/google/callback`. Hand me the client id + secret — they go in `.env`
     as `SP_GOOGLE_CLIENT_ID` / `SP_GOOGLE_CLIENT_SECRET`, never committed.
  2. **Production domain** — needed for the OAuth redirect URI, the Caddyfile, and the deploy pipeline.
  3. **Go-word for the GitHub Actions deploy pipeline** — the no-CI rule (CLAUDE.md #10) holds until you
     give it. Until then, `docs/DEPLOY.md` is the hand-deploy path.

- [ ] **M6b — MCP server: skip it, or build it?** The JSON API (M6a) already lets external AI tools
  read/write a group's library and read its reports over per-group Bearer auth, so "AI lives outside the
  app" is met. An MCP server would wrap the same operations for MCP-native clients, but it adds a
  heavyweight new runtime dependency (fastmcp + mcp, none installed) and a new protocol, is hard to
  verify with the current test discipline, and is the kind of stack-novelty you asked to be consulted on.
  **Options:** (1) skip it — the JSON API is enough; (2) say go and I'll add FastMCP and verify it against
  a real MCP client; (3) a lighter approach you prefer.

- [ ] **Scrub the seed data from git history too?** The seed pipeline, the `D20 Dinner Decider.xlsx`, and
  the dice provenance are deleted from the current tree (production launches from a blank DB), but they
  still exist in git history. Removing them from history is a destructive rewrite (breaks existing
  clones), so I did not do it unasked. Say the word if you want it.

## Parked (decided — no action needed unless you disagree)

- [ ] **Over-target trim (D13 strict).** M3e uses "host decides when to stop": targets are guidance, the
  host runs more batches while they want and clicks Finish when satisfied; unanimous keeps always stand
  (a batch can tip the count one past target). Strict D13 "host picks which to drop" is not built — it
  needs its own trim UI and the host-stops model already gives the host full control. Stands unless you
  want strict trimming.

- [ ] **Phantom account indicator on a stale session.** `app/templating.py` trusts the session's
  `account_name` without a DB check (deliberate — no DB hit per render; display names aren't editable).
  If an account-deletion/deactivation path is ever added, a surviving cookie would show a live-looking
  indicator while every real route still 401s. Revisit the context processor in that future slice.
  (Oscar M2c review — minor.)

- [ ] **Library export (low priority).** A user-facing JSON export of items + recipes. M5's DB-level
  backups already cover disaster recovery; this would be portability on top. Build if a real need shows up.

## Resolved

- ~~M5 pre-deployment security blockers~~ — **done.** Google SSO (M5a) removed the password surface and
  its login-rate-limiting / timing-side-channel / signup-email-oracle blockers; join-by-code rate
  limiting shipped in M5b. The security list for go-live is clear.
- ~~Drop `Category.legacy_sheet_index`~~ — **done** in M2e (migration 0008), alongside deleting the whole
  seed pipeline and the XLSX.
- ~~reference/D20 Dinner Decider.xlsx~~ — deleted from the tree (M2e). History scrub is the open item above.
- ~~Bare 401s instead of a login redirect~~ — fixed (`main.py` 401 handler redirects browser navigations
  to `/login?next=...`).
- ~~Library CRUD gating is interim~~ — closed by the tenancy fixes + collection-scoped routing (M2c).
- ~~Single-collection routing~~ — shipped as M2c (`/collections/{id}`).
- ~~Batch size default~~ — fixed at 15; revisit after real sessions.
- ~~Adversarial plan review~~ — `docs/INITIAL-PLAN-REVIEW.md`, all 12 findings accepted; plus the two
  2026-08-29 Oscar reviews (`docs/OSCAR-REVIEW-*.md`).
- ~~Hosting~~ — VPS (Hostinger).
- ~~Track order~~ — dinner first, then lunch.
- ~~Majority rule~~ — strict `yes > no`, ties excluded, host accepts, unanimous kept first, aggregate
  counts only. Built and verified in M3d.
- ~~Recipe display~~ — built (M2b), shown on the recipe view.
- ~~Raw votes via API~~ — aggregates only, and now structurally true: per-person votes are deleted at
  batch close (M3d) and never exposed over the API (M6a).
- ~~API auth shape~~ — per-group Bearer tokens, not one shared key. Built in M6a.
- ~~Site access gate vs. open signup~~ — accounts are the boundary; no site-wide gate.
- ~~Dice ritual~~ — removed permanently, in all forms, across the live docs.
- ~~Lunch starter set / `both` subset~~, ~~admin bootstrap~~, ~~multi-worker bootstrap guard~~,
  ~~CLAUDE.md refresh~~, ~~CI disabled~~, ~~seeded recipe links Option A/B~~ — all obsolete or settled;
  see `docs/DEVLOG.md` for the history.
