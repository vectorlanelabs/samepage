# Same Page — "Loud Moments" Design Handoff

Redesign round 3, 2026-08-29. This replaces the Quiet Kitchen bundle in full (v1–v4 live in
git history). Open `screens.html` in a browser for the six reference screens; the editable
canvas lives at the Claude artifact "Loud Moments".

**Direction in one line:** quiet chrome, loud moments — cool near-white ground, hard ink,
crisp 1px borders, and a single acid-green accent spent only where something happens.
Chosen by Charlie over a Klein-blue variant; acid green carries **ink text, always** (it is
a surface color, never a text color).

**What carries over from Quiet Kitchen/M7 unchanged:** every screen composition (chrome
model, hub, create/share/voting/results/complete flows, library, lean copy), the violet
host-only semantics, the outcome grouping system, and the vote-privacy display rules. This
is a token/type/contrast reskin — the M7 templates keep their structure.

## Tokens (as CSS custom properties)

```css
:root {
  --sp-bg:            #FCFCFD;  /* app background                      */
  --sp-card:          #FFFFFF;  /* raised surfaces                     */
  --sp-field:         #FFFFFF;  /* inputs                              */
  --sp-ink:           #101114;  /* primary text; solid-ink buttons     */
  --sp-sub:           #5E626E;  /* secondary text (6.1:1)              */
  --sp-faint:         #6E7280;  /* tertiary/meta text (5:1 — AA floor) */
  --sp-border:        #E4E5E9;  /* hairline structure                  */
  --sp-border-strong: #D6D8DE;  /* cards, inputs, secondary buttons    */
  --sp-hairline:      #EEEFF2;  /* in-card row dividers                */
  --sp-accent:        #CCF53F;  /* THE accent — surfaces only          */
  --sp-accent-ink:    #101114;  /* text on accent surfaces             */
  --sp-accent-deep:   #4E6200;  /* accent's text-safe form (labels)    */
  --sp-host:          #6C5CE8;  /* host-only affordances               */
  --sp-host-tint:     #F0EEFC;
  --sp-danger:        #C74E39;  /* text-only, as before                */
  --sp-shadow:        0 1px 2px rgba(16, 17, 20, 0.05);  /* cards only; buttons flat */
}
@media (prefers-color-scheme: dark) {
  :root {
    --sp-bg: #101114;      --sp-card: #1A1B21;   --sp-field: #1A1B21;
    --sp-ink: #FFFFFF;     --sp-sub: #ABAEB9;    --sp-faint: #8A8DA0;
    --sp-border: #22242B;  --sp-border-strong: #3A3C46; --sp-hairline: #2A2C34;
    --sp-accent: #CCF53F;  --sp-accent-ink: #101114;    --sp-accent-deep: #B8E018;
    --sp-host: #8B7CF0;    --sp-host-tint: #262143;
    --sp-danger: #E06A55;  --sp-shadow: none;
  }
}
```

Note the accent does not change in dark mode — acid on ink is the direction's signature
(the light-mode completion screen already previews it).

## Type

- Display + UI: **Schibsted Grotesk** (Google Fonts), weights 400 / 500 / 700 / 800.
- **IBM Plex Mono** 400/500 is promoted from "join codes only" to the brand voice: codes,
  counts ("4 / 15", "6 yes"), tags ("dinner · fish · 35 min"), dates ("aug 24"), outcome
  section labels, and outcome pills. Mono content is lowercase.
- Scale (phone): payoff display 46/800, screen titles 26–30/800, option name on the voting
  card 40/800, body 15/400–500, mono meta 12–13/400–500. Never below 12px.
- Letter-spacing on display sizes scales with size: −0.022em at 27–40px, −0.024em at 42px,
  −0.026em at 46px. Body untracked.
- Still no letterspaced uppercase, no small caps, no italics. Lean copy rules unchanged.

## Shape & depth

- Radii: cards 12px, buttons + inputs 10px, mono pills 6px. No 999px pills anywhere —
  the pill-everything look is retired with Quiet Kitchen.
- Borders: 1px `--sp-border-strong` on cards; 1.5px on inputs and secondary buttons.
- Shadows: `--sp-shadow` on cards only. Buttons are flat — no glows, no insets.
- Buttons: vote Yes/No 60px; all other full-width CTAs 56px; weight 700, 16–17px.
  Primary = accent surface + ink text. Structural lead among accent CTAs = solid ink
  (hub's "Host a session", landing's in-card "Join session"). Secondary = card bg +
  1.5px strong border. Danger stays text-only.
- Links: ink, weight 700, with a **2px accent underline** (`text-underline-offset: 3px`);
  hover flips the underline to ink. This replaces accent-colored link text everywhere.

## Color rules

- **Acid `--sp-accent` is a surface, not a text color.** It appears as: primary buttons,
  progress fills, link underlines, the "everyone" outcome pill, and the top bar of the
  brand glyph. Text on it is always `--sp-accent-ink`.
- Where the accent must be *text* at small sizes (the "everyone said yes" section label),
  use `--sp-accent-deep`.
- **Violet `--sp-host`** keeps exactly its M7 role: host-only labels, Keep buttons, the
  "host's call" pill, host avatar in rosters. A voter never taps violet.
- Outcome system unchanged in structure: accent = kept-unanimous, host = kept-by-host,
  faint = not kept.
- **The completion screen flips to ink ground** (`#101114`) with reversed type in both
  themes — it is the product's payoff moment and the one full-bleed accent-on-ink surface.

## Per-screen deltas from the M7 implementation

Compositions unchanged; apply the token/type swaps above plus:

1. **Voting card** — tags become one mono line (no chip backgrounds); option name 40/800;
   count in the header is mono "4 / 15"; buttons per the shape rules. Dark variant on the
   canvas is normative for dark mode.
2. **Batch results** — section labels in mono (accent-deep / host / faint); row counts in
   mono; the primary CTA becomes accent+ink.
3. **Session complete** — ink ground, 46/800 "Dinner's sorted.", mono meta line, kept rows
   as hairline list with mono outcome pills (accent+ink "everyone", host+white "host's
   call"), ghost "Done" (1.5px `#3A3C46` border) pinned bottom.
4. **Hub** — avatar becomes ink circle + white initial; collection meta in mono; "Manage"
   and "+ New collection" use the link treatment; CTAs unchanged in structure.
5. **Landing** — headline 42/800 all-ink; join-card code field in mono; "Join session"
   solid ink; bottom "Host a session" accent+ink.
6. Everything else (share, lobbies, waiting, library, groups, create-session, report)
   reskins by tokens with no compositional change; the mono voice applies to codes,
   counts, joined labels, and kept/last-kept metas throughout.

## Engineering notes

- Same constraints as before: server-rendered Jinja + htmx, no build step; fonts via
  Google Fonts (Schibsted Grotesk replaces Hanken Grotesk; IBM Plex Mono stays).
- The reskin is a `--sp-*` token swap plus the type/shape/link rules — template churn is
  limited to the per-screen deltas above (mono tag lines, mono counts, the completion
  screen's ink ground, chip retirement).
- Contrast: `--sp-faint` is at the AA floor by design — never lighten it; accent-on-ink
  and ink-on-accent both exceed 7:1; host-on-ink white text passes AA (~4.8:1).
- `assets/samepage-favicon.png` remains the favicon/PWA icon until a refreshed mark is
  cut; the CSS brand glyph's bars become accent / host / border-strong.
