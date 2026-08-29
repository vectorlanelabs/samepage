# Oscar review — the running app vs. the "Quiet Kitchen" Design Handoff

**Date:** 2026-08-29 · **Target:** the app as built (commit `e0766cd`), driven live at 390×844 (light + dark) and 1280×800, against `Design Handoff/` v4.
**Method:** every screen of the app was rendered through the app's own test client (26 snapshots: signed-out, hub, library, edit, groups, report, and a full host+3-voters session driven end to end), then compared against the 25 artboards on the canvas.
**Excluded by instruction:** the username/password auth screens — the app's Google-OAuth-only sign-in is an accepted product divergence, and nothing below dings it.

## Verdict

**The tokens are right; the screens are wrong.** `app.css` reproduces the Quiet Kitchen token block verbatim, dark mode is genuinely correct, and the component classes (buttons, chips, cards, danger-as-text) are faithful. But the *screens* those components compose are mostly generic scaffold pages wearing Quiet Kitchen paint. The handoff's per-screen compositions — the invented-nowhere-else stuff that IS the design: the hub greeting, the share moment, the radio-card session builder, the chromeless session flow, the outcome color system — are largely not implemented. This reads like the design system was ported in one slice and the screen inventory was never revisited afterward.

One confirmed functional bug fell out of the comparison (finding 5): **every guest voter who taps "See the recipe →" gets a raw 401.**

---

## Findings, worst first

### 1. The mobile chrome is an invented pattern the design deliberately doesn't have

At 390px the signed-in app shows a sticky topbar cramming brand + Home + Collections + Groups + Sign out into one row with `overflow-x: auto` ([app.css:1086](../app/static/app.css)) — the scrollbar is visible and "Groups" is clipped offscreen on first paint. The design has **no top nav menu on any of its 25 artboards**. Its chrome model is per-screen-class:

- **Hub:** brand left, avatar right. Nothing else.
- **Inner screens** (library, edit, groups, reporting): back arrow + screen title.
- **Session screens:** zero app chrome — a context line ("Dinner picks · The Hendersons") and a code pill or progress count.

A horizontally scrolling menu isn't a degraded rendering of the design's nav; there is no nav to degrade. The topbar needs to be deleted, not patched, and each screen given the chrome its artboard shows. (Bonus dead code: `.topbar .nav-account` is set to `display:none` at [app.css:1096](../app/static/app.css) and then given `margin-left:auto` ten lines later.)

### 2. The signed-in IA contradicts the handoff: two home pages, neither of them the designed one

The handoff (README §per-screen notes): *"collections hub is the post-login home."* The hub artboard is a composed screen — "Good evening, Charlie", group name + **switch** link, collection cards with rich meta ("155 meals · last session Aug 24"), "+ New collection", a last-session footer, and two stacked bottom CTAs: **Host a session** (solid ink) and **Join with a code** (secondary).

The app instead has *two* pages: a `/` home ("Decide together" hero card + Collections/Groups stat cards — an invented screen matching no artboard) and a `/collections` page that renders "Collections" as a plain title, **two side-by-side secondary buttons** ("Host a session" styled identically to "+ New collection" — the CSS has `.btn-ink` for exactly this and the template doesn't use it), and bare cards with "6 active items". No greeting, no group switcher, no last-session context, no join-with-code. The screen that anchors the whole signed-in experience is the least designed screen in the app.

### 3. Create session: the least faithful screen in the build

Design: collection **radio cards** (selected card gets the 2px accent border + check), a dashed "Ad hoc — type options on the spot" card, and per-track **steppers** (− 5 +) in a card, "Create session" pinned at the bottom. The app renders: a `Group` `<select>`, a "What are you voting on?" `<select>` **defaulting to "Ad hoc (no collection)"** — the design's default is the collection, ad hoc is the escape hatch — then four bare number inputs: Breakfasts, Lunches, Dinners, Picks. "Breakfasts" appears on no artboard and in no handoff note (the design's tracks are Dinners/Lunches; type is Lunch/Dinner/Both). If breakfast is a real product decision it postdates the handoff and the handoff should say so; if not, it's scope invention. Either way the widgetry (selects + spinners vs. radio cards + steppers) matches nothing in the design.

### 4. The share moment doesn't exist

Design H2 ("Invite the table") is a dedicated screen: the code at **40px IBM Plex Mono** with letterspacing, **Copy invite link** (primary), **Share…** (native share, secondary), a live "3 people have joined" indicator, "Go to the lobby" in ink. The app skips from create straight to the waiting room, where the code appears as a **12px inline pill**. There is no copy-link control anywhere in the app, no share sheet, no join count on a share surface. For an app whose entire growth loop is "host sends a link to the table," this is the most expensive missing screen in the build — and it's fully specified in the handoff.

### 5. CONFIRMED BUG — guest voters get a 401 from the voting card's recipe link

The voting card's "See the recipe →" points at `/collections/{cid}/items/{iid}` ([sessions.py:521](../app/routes/sessions.py)), which is guarded by `require_account` **plus** owned-collection checks ([library.py:557](../app/routes/library.py)). Verified live: a guest participant mid-vote who taps the link receives a bare `401 Sign in required`; a signed-in voter who isn't a group admin would get 404. The only person who can read a recipe during voting is the host. The design puts the recipe peek in the **voter** flow (V3 → C4). Either the recipe view needs a session-scoped public variant (participant-of-active-session may view items in that session), or the link must go. Shipping a dead-end 401 in the core flow is neither.

### 6. The voting screen — the product's one essential screen — is 70% there, and the missing 30% is the designed part

Right: Yes above No, stacked, full-width, correct hierarchy (accent primary / secondary), correct dark mode (light-blue accent with dark ink text). Wrong or missing:

- **No progress bar.** The design's 4px accent bar under "4 of 15" is the voter's only sense of pace. App shows text only: "Session opal-7110 · Option 1 of 5".
- **Header shows the raw session code**, not the session/group context line ("Dinner picks · The Hendersons"). Codes are for joining, not for staring at while you vote.
- Card sits at the top with buttons directly beneath, vs. the design's centered card + buttons pinned to the bottom (thumb reach — this is the screen's ergonomics, not decoration).
- Guests vote under a topbar that says **"Sign in"** — chrome the design's session screens don't have, and an off-message prompt mid-vote.
- Design's option card puts chips above a 34px/600 name, left-aligned, with a one-line description; app centers a 28px name with chips below and drops the description.

### 7. Batch results: the outcome color system was dropped, and the host-kept row vanishes

The handoff's README makes outcome grouping a **color rule**: accent label = kept-unanimous, host-violet label = kept-by-host, faint = not kept. The app's section headers are plain ink ("Kept — everyone agreed", "Not kept"), and after the host taps Keep, the kept item **disappears from the results screen entirely** — there is no "Kept by the host" group (it resurfaces only in the final plan). The majority card washes the whole card in violet tint (design: white card, violet *label*, faintly-violet border) — violet is supposed to mark host-only *affordances*, not flood a surface. Counts render as chunky chips ("Yes 4 / No 0") vs. the design's quiet "6 yes" meta text. "End session early" (danger text, always available on host results in the design) doesn't exist — the host can only finish once targets are met. And the progress line renders "**Dinners: 3 of 2**", which is the kind of string that makes users file bug reports; the design's framing is "3 of 5 dinners picked so far."

### 8. Library: phone density is half the design's, and the desktop layout was specified and not built

**Phone:** the design lists meals as compact rows inside one card — name, "kept 12×" right-aligned, one meta line, hairline dividers; ~7 rows per screen. The app renders each meal as a fat standalone card (type pill, tag chips, kept count, and an Edit / Recipe / Archive action row) — ~3 per screen, with a destructive Archive exposed at browse level (the design keeps archive inside edit, as danger text). The filter row wraps to **three rows** plus a visible "Search" button; v4 of the handoff exists specifically to prevent this ("fixed-width row, never a wrapping chip list"). The dropdown set is also wrong: design Type / Tags / **Time**; app Type / Tags / **Active-Archived** (invented), Time missing, and Type contains "Breakfast" (see finding 3).

**Desktop:** the README is explicit — "library gets a real desktop layout (250px sidebar nav + dropdown filter row with Sort and Clear + **table**: name / type / tags / kept / last kept)." The app at 1280px shows the same phone cards in a single column. No table, no Sort, no last-kept column. The sidebar exists but is the generic Home/Collections/Groups list — the design's sidebar names each collection, includes Reporting, and pins a "Host a session" button at the bottom.

### 9. Edit/add meal: the tag control has wrong semantics and won't scale

Every group tag renders as a chip **with an ✕** — including tags not on the meal (an ✕ on something not applied is a lie; toggling "20 min ✕" *adds* it). The design shows only the meal's own tags as removable chips plus a dashed "+ tag" adder. At the real library's scale (155 meals, dozens of time/cuisine tags) the app's approach becomes a wall of chips on every edit screen. Also: the segmented control is Breakfast/Lunch/Dinner multi-select vs. the design's Lunch/Dinner/Both single-choice — same breakfast question as finding 3 — and the title is "Edit Miso Salmon Rice Bowls" where the design says "Edit meal" (the name is already in the form's first field).

### 10. The v3 "lean copy" pass was un-done by the implementation

Handoff v3 deleted twelve reassurance captions by name. The app has re-grown several of them, nearly verbatim:

- "…no account needed to join." — share/waiting room, join page, landing join card (v3 removed "No account needed…" in all variants)
- "Keep or pass each one — aggregate counts only, individual votes stay private." — host results (v3: "Accept each or let it go.")
- "Admins manage collections and host sessions. Voting never requires membership." — group page (removed by name in v3)
- Em-dash asides throughout: "Waiting for others — 1/4 finished.", "All targets met — finish when ready.", "Share this code with your group — no account…" (v3 trimmed exactly this construction)

The handoff's position is that the privacy invariant is enforced by what screens *show*, not restated under buttons. The copy source of truth is the artboards; the templates read like they were written before v3 landed and never swept.

### 11. Session-flow screens keep app chrome and lose their compositions

All session screens render inside the standard shell (topbar or sidebar + Privacy/Terms footer). The design's session screens are chromeless. Beyond that, per screen:

- **Join (invite landing):** design is the emotional beat — centered brand, "You're invited to vote", session + group name in 26px, "15 options / ~5 minutes" chips, full-width "Join the session", "Have an account? Sign in." (pre-fills the name). App: "Join session / Code: opal-7110" + a bare name field + a **small non-block "Join"** button. The invitee learns neither what they're voting on nor with whom.
- **Voter lobby:** design centers "Waiting for the host to start" with a pulse dot and a "Here so far / 6 people" card of avatar chips. App: a "Waiting room" card that says "Waiting room" twice, plain text rows, no avatars.
- **Host lobby:** title should be "6 at the table" with the code pill top-right and the caption "Starting locks the roster. Batch 1 has 15 options." App titles it with the collection name, drops the caption entirely (the roster-locking rule is now invisible), and renders Charlie's host marker as two gray chips ("you" "host") instead of the violet ★ treatment. Remove-as-danger-text is correct.
- **Waiting state:** design has the ✓-in-circle, "That's all fifteen", and a "Voters finished 4 of 6" card **with a progress bar**. App: left-aligned "All your votes are in." and a one-line card, no check, no bar.
- **Session complete:** design "Dinner's sorted." + meta "5 dinners in 3 batches · 27 options seen" + colored outcome pills (accent "everyone" / violet "host's call") + quiet "Done". App: "Your plan", session-code meta, **gray** pills for both outcomes (the color system again, finding 7), and a full-accent "Join another session" primary — a strange lead action for a host looking at their own finished plan.

### 12. Smaller, still real

- **Groups:** design is one screen (group cards with "Owner · 3 collections" meta, current marked with accent border, dashed "+ New group", members below, invite row). App splits it into a thin list page ("The Hendersons / Owner") and a detail page; no collection counts, no current-group concept, no dashed add.
- **Group detail's "API & MCP access" panel** matches no artboard (M6 shipped past the handoff). Fine to exist; needs a design pass — right now it's the only screen with a marketing paragraph ("ChatGPT, Claude, and the like") in a settings card.
- **Recipe view:** back link says "← Back to library" (design: "← Meal Planner" — the collection name); source link hides the domain ("Originally sourced from this recipe ↗" vs. "Full recipe at cooking.example.com ↗" — the domain is the information); "Kept 7× before" floats under the chips while the design keeps kept-stats in the footer with last-kept date.
- **Landing (phone):** close on desktop, but the phone artboard's composition (headline → join card → Host pinned bottom; sub "Build a library, vote in private, keep what everyone loves.") was swapped for the desktop copy plus an invented 1-2-3 "how it works" band, and the join card's "Join session" is secondary where the design uses solid ink.
- **Report:** exceeds the M4 placeholder (real by-meal/by-tag data — legitimately ahead of the design), but "Kept 4 of 10 offered · **never kept**" renders both halves of a contradiction in one row when `last_kept_at` is empty; the never-kept clause should be conditional on `times_kept == 0`, whatever the timestamp says.

---

## What's actually good (credit where due)

- **Token fidelity is excellent.** The `:root` block is the handoff's, verbatim, both palettes; the layered card shadow and button glow made it in; fields read as wells.
- **Dark mode is right,** not approximately right: accent buttons flip to dark ink text, card shadows drop in favor of borders, chips and hairlines all track. This is the hardest part of a token system to get right and it works.
- **Danger-as-text is respected everywhere** — no filled red anywhere in the app.
- **The vote privacy invariant held** on every screen I drove: counts only, never names, waiting state shows "1/4 finished" with no who.
- **Yes/No hierarchy** on the voting card is correct, and the floating "+ Add a meal" pill matches the artboard.
- **Desktop signed-out landing** is genuinely close to its artboard — evidence the team can hit a composition when it's treated as the spec.

## The pattern to fix, not just the findings

Almost every finding reduces to one habit: **the artboards were treated as a mood board, and the design system as the deliverable.** The reverse is true. The tokens were the easy 20%; the compositions — chrome per screen class, the hub, the share screen, the session builder, the outcome colors, the lean copy — are the design. Recommended order of attack: chrome model (1), session flow screens (4, 5, 6, 7, 11), hub/IA (2, 3), library (8, 9), copy sweep against v3 (10).

*— Oscar. I'll happily re-review; bring screenshots.*
