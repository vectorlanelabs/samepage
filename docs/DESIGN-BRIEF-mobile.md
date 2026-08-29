# Design Brief — SamePage mobile-first rework

> For the Claude Design pass now in flight. Written 2026-08-29 by the project lead. This brief
> **supersedes the layout direction of the existing `Design Handoff/` bundle**, which describes itself as
> "desktop-first responsive" — that premise is now wrong. Its screen *inventory* and permission rules
> remain a useful reference; its layouts and visual language do not (Charlie has rejected the current
> visual design outright — do not iterate from it, start fresh).

## Corrections to the previous handoff's assumptions

1. **`docs/PLAN-v2-samepage.md` exists now** (the old handoff README says it doesn't). It is the binding
   spec for identity, permissions, session/batch state machines (§5.6), vote-data lifecycle (§5.5), and
   client-platform decisions (§9). Design from it, not from chat memory.
2. **Desktop-first is inverted.** Voters — and usually the host starting a session — are on phones.
   Every session-flow screen is designed at phone width first; desktop is the adaptation. Library and
   collection management may be desktop-comfortable but must remain fully usable on a phone.
3. **The app is server-rendered, not an SPA** (plan §9). Design page-per-screen with light dynamic
   updates (htmx/SSE): a lobby roster that fills in, a results reveal, a vote tally. Avoid interactions
   that only make sense with heavy client-side state (drag-and-drop ordering, optimistic multi-step
   wizards, cross-screen persistent panels).

## The one big presentation change: voting is one option at a time

On mobile, a batch is **not a 15-row grid**. It is a sequence: one full-screen card per option — name,
tags/type, optional recipe peek — with large yes/no targets and a progress indicator ("4 of 15"). After
the last card: a waiting state ("waiting for 2 more voters") until the batch closes, then the results
screen (aggregate counts only — never who voted which way; this is the product's hard privacy
invariant). Desktop may show a denser list, but mobile's card flow is the primary design.

## Screens, in priority order

1. **Voter flow (phone)** — join by link/code (guest name entry; logged-in pre-fill), lobby, one-at-a-time
   voting cards, waiting state, batch results reveal (kept-unanimous, host-accepted, not kept),
   session-complete summary. This flow must work beautifully for someone who has never seen the app and
   will never log in.
2. **Host flow (phone)** — create session (pick collection or ad hoc, set targets), share code/link,
   lobby with roster (including **remove participant** — plan §5.6), start voting, batch results with
   majority-accept decisions (host-only), end session. The host is on their phone on the couch.
3. **Sign in / sign up** (phone-first, trivial screens).
4. **Collections & library** — collections index as the post-login hub (URLs are
   `/collections/{id}`, plan §9), library browse/search/filter, item detail/edit, recipe view. May be
   desktop-comfortable; must work on phone.
5. **Groups** — create/switch group, manage members (owner starred, admins removable, invite by email).
6. **Reporting** — later milestone (M4); a placeholder direction is enough for now.

## Constraints that are product law (not design preferences)

- Aggregate vote counts only, everywhere, always. No screen may imply per-person votes are knowable.
- No dice/randomizer imagery or mechanics anywhere — permanently retired.
- Joining a session requires no account. Login only pre-fills a display name.
- 404-style dead ends for other groups' resources (never "you don't have permission" — don't design
  screens that reveal a resource exists).
- PWA at M5: design an app icon and assume installed-to-home-screen usage (no browser chrome).

## Visual language

Free rein. Charlie dislikes the current design; nothing about its colors, type, or component shapes needs
to survive. Keep it self-contained (system/Google fonts, no external assets at runtime) and workable in
light and dark.

## Deliverable

Same bundle shape as before (self-contained interactive HTML prototype + README documenting tokens and
per-screen notes) into `Design Handoff/`, replacing the current bundle. The engineering side will
recreate it as Jinja templates + CSS in one reskin slice — flag anything you design that you suspect
can't be server-rendered simply, rather than assuming it can.
