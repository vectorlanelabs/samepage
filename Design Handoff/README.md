# Handoff: Dinner Decider — Full App Design

## Overview
A household weekly-meal-planning web app: set dinner/lunch targets, run iterative 15-meal yes/no voting batches until targets are met, keep unanimous (and host-accepted majority) meals, and maintain a meal library with tags, ingredients, and instructions. This bundle covers every screen of the v1 product described in the repo's `CHARTER.md` and `docs/PLAN-v1-mvp.md`, designed as a **desktop-first responsive web app** (not a native mobile app — see the in-app Desktop/Mobile toggle).

## About the Design Files
The file in this bundle (`Dinner Decider.dc.html`) is a **design reference built as a self-contained interactive HTML prototype** — it simulates the full UX with client-side state (no real backend, no persistence, no auth). It is not production code to copy directly. The task is to **recreate this design in the target stack specified in `docs/PLAN-v1-mvp.md`** (FastAPI + SQLAlchemy + SQLite + Jinja2 + HTMX, per decision D1) — server-rendered templates with `hx-post` interactions and polling, not a client-side SPA. Reuse the exact visual language (colors, type, spacing, component shapes) documented below; do not reuse the prototype's client-side state approach.

`support.js` is a runtime shim the prototype needs to render in a browser — it has no bearing on the production implementation and can be ignored by the engineer.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and copy are final. Interaction logic (batch voting, unanimous/majority resolution, track progression) is a faithful simulation of `docs/PLAN-v1-mvp.md` §9 and should be implemented server-side exactly as specified there — the prototype is the UX reference, the plan doc is the behavioral spec of record when the two could be read differently.

## Screens / Views

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

All screens share a persistent left sidebar (desktop) / top bar (mobile) with Home / Meal Library / History / People navigation plus a "Start a session" shortcut, and a fixed top-right Desktop/Mobile view toggle used only for this design review — remove it from production; production should be responsive via real CSS breakpoints instead.

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
