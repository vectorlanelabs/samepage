# Same Page — Redesign Kickoff (for Claude Design)

> Project kickoff, 2026-08-29. The previous design project is **scrapped** — this is a brand-new,
> ground-up redesign of the entire app, not an iteration. Nothing from the old prototype's layouts,
> colors, type, or component shapes carries over. Two things survive from the old bundle: the **logo
> assets** in `Design Handoff/assets/` (mandatory, see Brand below) and, if useful, its screen
> inventory as a checklist of what exists. Everything else: clean slate.

## Round 1 — the ask: three distinct design directions

Deliver **three genuinely different visual directions** for the app — not one direction in three
accent colors. Different personalities: e.g. one warm/editorial, one crisp/utilitarian, one playful —
your call, as long as the three would photograph as three different products. Each direction must:

- Use the existing logo assets as-is (below). The direction's palette must sit comfortably with the
  logo's colors; the logo is the fixed point the rest of the system is derived around.
- Be shown as **2–3 signature screens at phone width**, self-contained HTML: the **voting card**
  (one option at a time — the app's single most important screen), the **collections/home hub**, and
  one more of your choice (session lobby or batch results are good candidates).
- Come with a one-paragraph rationale and its core tokens (palette with light + dark values, type
  choices, radius/spacing feel).

Charlie picks one (or asks for a blend). **Round 2** then builds the chosen direction out to the full
app — every screen in the inventory below — as a self-contained interactive HTML prototype + README
documenting tokens and per-screen notes, delivered into `Design Handoff/` replacing the old bundle.

## Brand (fixed)

- Product name: **Same Page** — two words, always. The module inside it: **Meal Planner**.
- Logo assets in `Design Handoff/assets/` (use as-is; do not redraw or restyle):
  - `samepage-wordmark-full-logo.png` — stacked-pages mark + "Same Page" wordmark
  - `samepage-wordmark-only.png` — wordmark alone
  - `samepage-favicon.png` — the stacked-pages mark alone (also the PWA/home-screen icon basis)
- The logo's own palette — ink navy, bright blue, violet accent, cream page-white — is the anchor
  every direction must harmonize with (harmonize ≠ copy; a direction may go dark, muted, or warm, but
  the logo can't look pasted-on).

## What the product is

Same Page is a multi-tenant consensus-voting platform for families and friend groups. Groups own
**collections** (Meal Planner — a meal library with recipes — is the first kind) and host **voting
sessions**: a batch of options, private yes/no votes, unanimous keeps auto-accepted, majority keeps
offered to the host. Anyone with a session link/code can join and vote — no account needed; accounts
exist for group owners/admins who manage collections and host sessions.

Binding spec: `docs/PLAN-v2-samepage.md` — identity/permissions (§4), session/batch state machines
(§5.6), client-platform decisions (§9). Design from it, not from memory of the old project.

## Platform constraints (product law, not preferences)

- **Mobile-first.** Voters — and usually the host — are on phones. Every session-flow screen is
  designed at phone width first; desktop is the adaptation. Library/collection management may be
  desktop-comfortable but must work on a phone.
- **Server-rendered, no SPA** (plan §9): page-per-screen with light dynamic updates (htmx/SSE — a
  lobby roster filling in, a results reveal). Avoid designs that need heavy client-side state
  (drag-and-drop ordering, optimistic multi-step wizards, cross-screen persistent panels).
- **Voting is one option at a time on mobile**: full-screen card per option — name, tags/type,
  optional recipe peek — big yes/no targets, "4 of 15" progress; then a waiting state, then results.
  Not a 15-row grid. Desktop may show a denser list.
- **Aggregate vote counts only, everywhere, always.** No screen may imply per-person votes are
  knowable. This is the product's hard privacy invariant.
- Joining a session requires no account; login only pre-fills a display name.
- No dice/randomizer imagery or mechanics — permanently retired.
- Dead ends for other groups' resources read as not-found, never "no permission" (don't design
  screens that reveal a resource exists).
- **PWA**: assume installed-to-home-screen usage (no browser chrome); light and dark both required.
- Self-contained: system/Google fonts only, no external runtime assets.

## Screen inventory (round 2 scope, priority order)

1. **Voter flow (phone)** — join by link/code (guest name entry; logged-in pre-fill), lobby,
   one-at-a-time voting cards, waiting state, batch results reveal (kept-unanimous, host-accepted,
   not kept), session-complete summary. Must work beautifully for someone who's never seen the app.
2. **Host flow (phone)** — create session (pick collection or ad hoc, set targets), share code/link,
   lobby with roster incl. **remove participant** (plan §5.6), start voting, batch results with
   host-only majority-accept, end session.
3. **Sign in / sign up.**
4. **Collections & library** — collections index as the post-login hub (`/collections/{id}` URLs),
   library browse/search/filter, item detail/edit, recipe view.
5. **Groups** — create/switch, manage members (owner starred, admins removable, invite by email).
6. **Reporting** — M4, placeholder direction only.

## Working notes

- Flag anything you design that you suspect can't be server-rendered simply — don't assume it can.
- Engineering will recreate the chosen direction as Jinja templates + CSS in one reskin slice;
  tokens documented as CSS custom properties make that hand-off cheap.
