# Changelog — Quiet Kitchen handoff

## v4 — filter controls (2026-08-29)
- Replaced pill/chip filter rows in the library (phone + desktop) with compact dropdown
  triggers (Type / Tags / Time, plus Sort and Clear on desktop). Dropdowns scale to any
  number of tags without wrapping; each renders as a plain <select> or a small options
  page server-side. Tag chips on the item-edit screen are unchanged (those are values,
  not filters).

## v3 — lean copy (2026-08-29)
- Removed 12 caption sub-cues across all screens: the privacy/no-account reassurance
  footnotes under buttons and at screen bottoms ("Votes are private — the group only ever
  sees totals", "No account needed. Votes stay private", "Hosting needs an account — voting
  never does", "Who's still voting isn't shown — only the count", "Keep this page open…",
  "Admins manage collections… Voting never requires membership", "You only need an account
  to host sessions…", and the landing variants).
- Trimmed em-dash asides in microcopy: "Two dinners to go — batch 3 is on its way" → "Two
  dinners to go"; "Sit tight — results appear…" → "Results appear the moment everyone's
  done"; "Saved to Meal Planner — the host has the full list" → "Saved to Meal Planner";
  "Starting locks the roster — batch 1 has 15 dinner options" → "Starting locks the roster.
  Batch 1 has 15 options"; "Majority-yes options — accept them or let them go" → "Accept
  each or let it go"; reporting subhead → "Coming with M4."
- Join screen footnote reduced to "Have an account? Sign in." (link kept — it pre-fills the
  display name).
- Sign-up subhead reworded to the imperative: "Host sessions and manage your group's
  collections."
- README: added the lean-microcopy rule (account/privacy rules live in the flows, not in
  captions); auth and reporting notes updated to match.
- The aggregate-votes-only privacy invariant is unchanged — it's enforced by what screens
  display (counts only), no longer restated in captions.

## v2 — polish pass (2026-08-29)
- Card shadows: single flat blur → layered `0 1px 2px rgba(43,46,62,0.04),
  0 12px 32px rgba(43,46,62,0.07)` (crisp contact + soft ambient). 22 instances.
- Primary buttons (accent + ink): added depth — contact shadow, faint color glow, hairline
  inset top highlight (`--sp-btn-shadow`). Secondary and danger buttons stay flat. Dark-mode
  accent buttons keep only a faint glow.
- Inputs: faint inset shade (`inset 0 1px 2px rgba(43,46,62,0.04)`) so fields read as wells.
- Display type: heading tracking tightened (-0.01em → -0.018em; hero sizes -0.02em).
- README tokens updated: `--sp-shadow` revised, `--sp-btn-shadow` added.

## v2 — landing screens (2026-08-29)
- Added the missing signed-out landing, desktop + phone (the live build had improvised one).
  Rules encoded: no app-shell sidebar when signed out; join-by-code card is the co-star;
  value-prop headline; sign in / create account quiet in the top-right.

## v1 — initial handoff (2026-08-29)
- Full "Quiet Kitchen" (direction 2c) screen set: voter flow (join, lobby, voting card,
  waiting, batch results, session complete), host flow (create, share, lobby with remove,
  majority-accept results), auth, collections hub, library, item edit, recipe, groups &
  members, reporting placeholder, desktop previews (library, host results), dark-mode pair.
- Tokens documented as CSS custom properties, light + dark.
- Old wordmark PNGs retired (wordmark re-set in Hanken Grotesk + CSS page glyph);
  `assets/samepage-favicon.png` kept as the PWA icon.
