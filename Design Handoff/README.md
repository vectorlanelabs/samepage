# Handoff: SamePage — Full App Design (Meal Planner module)

## Overview
**SamePage** is a multi-tenant consensus-voting platform for families and friend groups: groups (one owner, any number of admins) own **collections** — Meal Planner is the first and only buildable one today, with more (things-to-do, games) intended later but explicitly not designed yet. Meal Planner is the household weekly-meal-planning experience: set dinner/lunch targets, run iterative 15-option yes/no voting batches until targets are met, keep unanimous (and host-accepted majority) options, and maintain a meal library with tags, ingredients, and instructions. This bundle covers every screen designed so far, as a **desktop-first responsive web app** (not native mobile — see the in-app Desktop/Mobile toggle).

`docs/PLAN-v2-samepage.md`, referenced as the source of truth for identity/permission rules (owner vs. admin, guest-join rules), does **not exist in the `vectorlanelabs/dinnerdecider` repo** as of this handoff — confirmed via a full-tree search. The account, group, and collection screens below were designed from rules given directly by the product owner in chat, not from that doc. Flag this gap to whoever owns that plan doc before implementation starts.

## New in this pass (SamePage rebrand)
- **Rebrand**: wordmark is now "SamePage" with "Meal Planner" (or the current group name, outside the module) as a secondary sidebar line.
- **Auth**: email + password sign-in/sign-up screens. The old name+PIN login is fully removed — there is no PIN concept.
- **Groups**: create group, switch between groups, manage members (owner starred/non-removable, admins invited by email, admins removable).
- **Collections**: top-level "your collections" grid, scoped to the current group. Meal Planner collections are real/clickable; other types (Things To Do, Game Night) render as disabled "Coming soon" placeholders — intentionally not built out.
- **Session join**: zero-login guest join (name-only) and a logged-in variant (name pre-filled, "join as someone else" escape hatch). A demo toggle switches between the two for review purposes only — remove it in production; the real app determines this from actual auth state.
- **Voting chrome genericized**: the batch screen's meal-count chip now reads "N options" rather than "N meals" — the voting/reveal UI is intended to be reused by future non-meal collection types. Only the Meal Planner module's own screens (Home, Library, Recipe, Done/week-summary) keep meal-specific language, since those are Meal Planner-specific by design.
- **Reporting**: first-pass per-item and per-tag rejection-rate view (static/seeded data, not wired to real vote history).

## About the Design Files
The file in this bundle (`Dinner Decider.dc.html` — filename retained for continuity, content is the full SamePage app) is a **design reference built as a self-contained interactive HTML prototype** — it simulates the full UX with client-side state (no real backend, no persistence, no real auth). It is not production code to copy directly.

## About the Design Files
The file in this bundle (`Dinner Decider.dc.html`) is a **design reference built as a self-contained interactive HTML prototype** — it simulates the full UX with client-side state (no real backend, no persistence, no auth). It is not production code to copy directly. The task is to **recreate this design in the target stack specified in `docs/PLAN-v1-mvp.md`** (FastAPI + SQLAlchemy + SQLite + Jinja2 + HTMX, per decision D1) — server-rendered templates with `hx-post` interactions and polling, not a client-side SPA. Reuse the exact visual language (colors, type, spacing, component shapes) documented below; do not reuse the prototype's client-side state approach.

`support.js` is a runtime shim the prototype needs to render in a browser — it has no bearing on the production implementation and can be ignored by the engineer.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy are final. Interaction logic (batch voting, unanimous/majority resolution, track progression) is a faithful simulation of `docs/PLAN-v1-mvp.md` §9 and should be implemented server-side exactly as specified there — the prototype is the UX reference, the plan doc is the behavioral spec of record when the two could be read differently.

## Screens / Views

0. **Auth (sign in / sign up)** — standalone, no sidebar. Email + password; sign-up adds a Name field. Toggle link swaps modes. Secondary CTA to the guest session-join screen.
0a. **Session join (guest / logged-in)** — standalone, no sidebar. Shows the session code + name; guest variant has an editable name field with no account requirement, logged-in variant shows the pre-filled name read-only with an "join as someone else" escape hatch. The Guest/Logged-in switch on this screen in the prototype is a review-only demo toggle, not a real app control.
0b. **Collections** — shell screen, grid of the current group's collections (Meal Planner card is clickable → module Home; other types show disabled "Coming soon" cards), "+ New collection" CTA.
0c. **Collection create** — name field + type picker (Meal Planner selectable; other types disabled/dashed).
0d. **Groups** — list of the account's groups with role badge (Owner/Admin), member count, "Manage members" and "Switch"/"Current" actions; "+ Create group" CTA.
0e. **Group create** — name field; creator becomes owner.
0f. **Group members** — owner (starred, not removable) + admins (removable) for the current group; invite-by-email form adds a pending "Invited" row.
0g. **Reporting** — first-pass "By item" and "By tag" rejection-rate lists with a small bar per row.

1. **Home** — dashboard: hero heading + "Start a session" CTA, plus 3 stat cards (Meal Library / History / People) linking out. Grid: `repeat(3,1fr)` desktop, `1fr` mobile.
2. **Session setup** — dinner/lunch target steppers (+/− pill controls), join-code display (`WORD-####` per D3), roster list of people with a per-person "Dinner only / Dinner + Lunch" toggle chip. Two-column grid desktop (targets | roster), stacked on mobile.
3. **Vote** — batch header (track + batch number + meal count), a person-switcher avatar row (simulates handing the device between household members — production replaces this with real per-device sessions), a grid of meal cards with Yes/No pill buttons, and a "Close batch" CTA that activates once every roster member has voted every card.
4. **Batch reveal** — two-stage screen: (1) pending — unanimous keeps shown automatically or, if they exceed remaining slots, as a checkbox picker capped at the remaining count (D13); majority meals (yes > no, ties excluded) shown with aggregate "N/M yes" counts and host Accept/Skip toggles (D5); (2) finalized — confirmed kept list, progress bar, and a "Next batch / Start lunch voting / See the plan" CTA depending on track state.
5. **Done (week summary)** — kept dinners + kept lunches in a two-column grid (desktop) / stacked (mobile), "Save to history & start fresh" CTA.
6. **Meal Library** — search input, type filter chips (All/Dinner/Lunch/Both), tag filter chips (multi-select), active/archived/all status filter, "+ Add a meal" CTA, and a 2-col (desktop) / 1-col (mobile) grid of meal rows (name, type pill, tag chips, "Kept N×" badge, Edit / Recipe → / Archive actions).
7. **Meal edit** — name input, track type cycle button, tag multi-select chips, **Ingredients** textarea (one item per line — stored as a discrete list, intended to drive future ingredient-based meal discovery, not left inside a paragraph), **Instructions** textarea, and an optional "Original source" URL field (secondary — the household's own ingredients/instructions are the primary record, not a link out). Archive/Restore and "View recipe →" actions appear when editing an existing meal.
8. **Recipe view** — meal name, type pill + tag chips, "Kept N× before" note, Ingredients (bulleted list) and Instructions (prose) sections in that order, then the optional original-source link last, and a footer note that a full cooking/print view arrives with recipe intake (v2, per `docs/POST-V1.md`).
9. **History** — 2-col (desktop) / 1-col (mobile) grid of past sessions, each showing its dinner/lunch kept-meal chips.
10. **People** — roster list (avatar, name, track label, PIN placeholder), per-person "Make admin/★ Admin" and "Deactivate/Reactivate" toggles (people are deactivated, never deleted — D16), add-person form.

Meal Planner module screens (1–10) share a persistent left sidebar (desktop) / top bar (mobile) with a top-level nav (Collections / Group / Reporting) plus, only while inside the module, a second "Meal Planner" nav group (Home / Meal Library / History / People) and a "Start a session" shortcut. Auth and session-join (0, 0a) render standalone with no sidebar. A fixed top-right Desktop/Mobile view toggle is used only for this design review — remove it from production; production should be responsive via real CSS breakpoints instead.

## Interactions & Behavior
- **Vote card**: click Yes/No to set this device's current-person vote; selected state fills the button (green Yes / terracotta No).
- **Person switcher**: click an avatar to change whose votes the device is currently entering; a filled/outlined ring shows who has completed the current batch (never their actual answers — vote privacy is a hard invariant per D16, enforced server-side in production: no client response may ever contain another person's vote, during or after a batch).
- **Batch close**: enabled only when every track participant has voted every card in the batch; otherwise shows "Waiting on {names}".
- **Unanimous over-target**: if unanimous-yes count exceeds remaining slots, the host picks up to the remaining count via toggle rows (capped — further clicks past the cap are no-ops).
- **Majority accept**: host can accept majority meals up to whatever slots remain after unanimous resolution; already-capped selections show "Accepted ✓" and disable further accepts.
- **Track progression**: dinner track runs to completion first; if a lunch target is set, lunch voting starts automatically after dinner completes; otherwise the session finishes.
- **Type cycle button** (meal rows/edit): each click cycles Dinner → Lunch → Both → Dinner.
- **Tag filter**: OR semantics — a meal shows if it has *any* selected tag.
- **View toggle** (design-review only): switches the whole shell between desktop (sidebar, multi-column grids) and mobile (top bar, 1–2 column grids, narrower content column) layouts.

## State Management (for the real implementation, per `docs/PLAN-v1-mvp.md` §6, §9)
- `Session` (code, status, dinner/lunch targets, created_by) → `Batch` (per track, sequence, status) → `Vote` (per person/meal, yes/no, never exposed cross-person) → `BatchMeal` (kept flag + kept_by: unanimous|host).
- `Meal` (name, type, tags, ingredients — structured list, instructions, source_url, times_kept, last_kept_at, archived).
- `Person` (name, PIN hash, is_admin, is_active).
- Session/vote transitions must be idempotent (double-submit safe) per §9.9 — the prototype does not model this since it has no network layer.

## Design Tokens
- **Fonts**: `Fredoka` (600/700, headings & buttons), `Nunito Sans` (400/600/700/800, body/UI text) — both via Google Fonts.
- **Background**: `oklch(0.96 0.02 250)` (page), `#fff` (cards/sidebar).
- **Text**: near-black neutral `oklch(0.25 0.02 260)` (primary), `oklch(0.55 0.02 260)` (secondary/muted).
- **Accent hues** (all at chroma ~0.14–0.16, lightness ~0.6–0.72, hue varies): purple/primary `300` (CTAs, active states), terracotta `25` (dinner track, "No" votes), green `140` (lunch track, "Yes"/kept states), plus a per-person avatar palette cycling hues `20, 90, 150, 220, 300, 60, 320, 180`.
- **Radius**: 999px (pills/buttons/avatars), 24px (screen cards), 16–20px (list rows/sub-cards), 12–14px (inputs/small chips).
- **Shadow**: `0 14px 30px rgba(60,50,110,.10)` on primary cards; `0 8px 20px rgba(60,50,110,.08)` on home stat cards.
- **Grids**: desktop 3-col (home stats, vote cards), 2-col (library, history, done summary); mobile collapses to 1-col (2-col for vote cards only).

## Assets
No images/icons — all visual elements are typography, color, and simple CSS shapes (circles, pills). No SVG iconography was hand-drawn; emoji are used sparingly on Home stat-card labels only (📖 🗓 👥) and can be swapped for a real icon set.

## Files
- `Dinner Decider.dc.html` — the full interactive design reference (open directly in a browser).
- `support.js` — runtime shim required only to render the `.dc.html` file in a browser; not relevant to the production build.
