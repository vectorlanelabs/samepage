# Same Page — "Quiet Kitchen" Design Handoff

Redesign round 2, 2026-08-29. This replaces the previous Dinner Decider bundle in full.
Open `Same Page — Quiet Kitchen.dc.html` in a browser (keep `support.js` next to it) — every
screen of the app is on one pan/zoom canvas: phone-first at 390px, plus desktop previews and a
dark-mode pair.

**Direction in one line:** calm, soft-modern, lived-in — warm-gray surfaces, one humanist sans
(Hanken Grotesk), muted blue for actions, violet reserved for host-only moments. Hierarchy comes
from weight and spacing, not boxes or color.

**Logo:** the old PNG logo assets are retired from the UI. The wordmark is re-set in Hanken
Grotesk 700 next to a simple CSS "page" glyph (bordered rounded rect, three bars: accent / host /
border colors). `assets/samepage-favicon.png` is kept as the favicon / PWA home-screen icon
until a refreshed mark is cut; the old wordmark PNGs are removed.

## Tokens (as CSS custom properties)

```css
:root {
  --sp-bg:        #F6F4F0;  /* app background        */
  --sp-card:      #FFFFFF;  /* raised surfaces        */
  --sp-field:     #FDFCFA;  /* inputs                 */
  --sp-ink:       #2B2E3E;  /* primary text           */
  --sp-sub:       #83817A;  /* secondary text         */
  --sp-faint:     #A3A099;  /* tertiary / disabled    */
  --sp-chip-bg:   #F0EDE7;  /* tag chips, code pills  */
  --sp-chip-ink:  #6A675E;
  --sp-border:    #E7E3DC;  /* card borders           */
  --sp-hairline:  #F0EDE7;  /* in-card row dividers   */
  --sp-border-strong: #C9C4B9;  /* inputs, secondary buttons */
  --sp-accent:    #4468D2;  /* the one action color   */
  --sp-accent-tint: #EAEFFB;
  --sp-host:      #8177C9;  /* host-only affordances  */
  --sp-host-tint: #F0EDF9;
  --sp-danger:    #B65C4E;  /* remove / archive / end */
  --sp-avatar:    #E9E5DD;
  --sp-shadow:    0 1px 2px rgba(43, 46, 62, 0.04), 0 12px 32px rgba(43, 46, 62, 0.07);
  --sp-btn-shadow: 0 1px 2px rgba(43, 46, 62, 0.18), 0 4px 14px rgba(68, 104, 210, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.14); /* primary buttons; ink buttons swap the blue glow for rgba(43,46,62,0.2) */
}
@media (prefers-color-scheme: dark) {
  :root {
    --sp-bg: #191A21;      --sp-card: #23242E;   --sp-field: #23242E;
    --sp-ink: #EDECE7;     --sp-sub: #9B99A6;    --sp-faint: #6E6D78;
    --sp-chip-bg: #2E2F3A; --sp-chip-ink: #B8B6C2;
    --sp-border: #33343F;  --sp-hairline: #2E2F3A; --sp-border-strong: #454652;
    --sp-accent: #7E9AEC;  --sp-accent-tint: #262C3E;  /* dark: accent buttons use dark ink text #14151B */
    --sp-host: #A69DE0;    --sp-host-tint: #2E2A40;
    --sp-danger: #D48575;  --sp-avatar: #2E2F3A;
    --sp-shadow: none;     /* dark relies on borders, not shadows */
  }
}
```

## Type

- One family: **Hanken Grotesk** (Google Fonts; self-hostable). Weights 400 / 500 / 600 / 700.
- Mono accent: **IBM Plex Mono** 500, used ONLY for join codes (e.g. `PLUM-42`).
- Scale (phone): screen titles 22–30/700 with `letter-spacing: -0.018em`; option name on the
  voting card 34/600; body 14–15/400; labels + meta 12.5–13/500 in `--sp-sub`; never below 12px.
- No small caps, no letterspaced uppercase, no italics.
- Microcopy is lean: no reassurance footnotes or caption sub-cues. Account and privacy rules
  live in the flows themselves, not in captions under buttons.

## Shape & depth

- Radius: cards 14–18px, buttons/inputs 12px, chips/pills 999px.
- Borders: 1px `--sp-border` on cards; 1.5px `--sp-border-strong` on inputs and secondary buttons.
- Shadow: `--sp-shadow` (layered: crisp 1px contact + soft ambient) on cards; `--sp-btn-shadow`
  on primary buttons only — secondary/danger stay flat. Dark mode drops card shadows (borders
  carry the layering) and keeps a faint glow on the accent button.
- Buttons: 56–60px tall on phone (44px min hit target everywhere). Primary = solid accent;
  secondary = white + strong border; the hub's "Host a session" uses solid ink for contrast with
  the accent CTAs around it. Danger actions are text-only in `--sp-danger` — never filled red.

## Color rules

- **Blue `--sp-accent` is the only interactive color** for participants: primary buttons, links,
  progress fills, "everyone said yes" labels.
- **Violet `--sp-host` marks host-only things**: host badge in rosters (★), "kept by the host"
  outcome group, majority accept/pass controls. A voter should never see violet on something
  they can tap.
- **Danger `--sp-danger`** for remove participant / archive / end session, text-style only.
- Outcome grouping on results: accent label = kept-unanimous, host label = kept-by-host,
  `--sp-faint` = not kept (grayed row, no strikethrough).

## Per-screen notes (canvas order)

**1 · Voter flow** — join (guest name entry; logged-in users get the name pre-filled, field
stays editable), lobby (roster fills live via SSE; code pill top-right), voting card (one option
per page; Yes above No, stacked full-width; progress bar + "4 of 15"; recipe peek is a plain
link to the recipe page), waiting ("voters finished 4 of 6" — count only, never names of who's
missing), batch results (grouped by outcome, aggregate counts only), session complete (final
kept list with outcome pills).

**2 · Host flow** — create session (collection radio cards + ad hoc option; per-track steppers
write `session_target` rows), share (code + copy link + native share), host lobby (roster rows
with text-danger Remove per plan §5.6; starting locks the roster), host results (majority
section on top with Keep/Pass per item — violet; unanimous below for reference; Start next
batch primary; End session early as danger text).

**3 · Auth** — sign in / sign up.

**4 · Collections & library** — collections hub is the post-login home (`/collections/{id}`);
library is browse/search/filter with chip filters and kept-count meta; item edit (segmented
type control, removable tag chips, archive as danger text); recipe view (ingredients + method
cards + source link + offered/kept footer).

**5 · Groups** — group list with current marked, members with ★ owner, removable admins,
invite-by-email row.

**6 · Reporting** — M4 placeholder: striped placeholder blocks with mono captions; charts
read from batch outcomes and totals only.

**Landing (signed-out)** — desktop and phone. No app-shell sidebar when signed out; value-prop
headline left, join-by-code card as the co-star; sign in / create account quiet in the top-right.
Join code entry posts to the same join flow as an invite link.

**Desktop** — library gets a real desktop layout (250px sidebar nav + table: name / type / tags /
kept / last kept). Session screens stay a centered 720px single column reusing the phone
components unchanged — voting stays one-option-at-a-time on desktop too.

## Engineering notes

- Every screen is a plain server-rendered page. Only two places need light dynamic updates,
  both SSE/htmx-friendly: lobby rosters filling in, and the waiting-state → results reveal.
  Steppers, segmented controls, chips, Keep/Pass are ordinary forms/links.
- Hard privacy invariant preserved everywhere: aggregate counts only; the waiting state shows a
  count of finished voters, never who.
- Fonts via Google Fonts (or self-host the two families); no other runtime assets. The logo
  glyph is pure CSS/HTML — no image request.
- Not-found semantics, PWA installed-mode chrome, and the reporting build-out are unchanged
  from `docs/PLAN-v2-samepage.md`.
