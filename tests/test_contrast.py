"""WCAG AA contrast audit for the Loud Moments token pairs (Slice R1 fix).

Parses the two token blocks out of app/static/app.css — the :root block
(light theme) and the prefers-color-scheme: dark :root block — and asserts
the text/surface pairs the design actually renders meet the WCAG AA floor
(>= 4.5:1), with ink on the app background at AAA (>= 7:1). Dependency-free:
the WCAG 2.x relative-luminance and contrast formulas are implemented here.

One pairing needs a scope note: the accent surface never carries the dark
theme's white --sp-ink — text on accent is always --sp-accent-ink (#101114,
the light ink) in BOTH themes ("acid green carries ink text, always" —
Design Handoff/README.md). So "ink on accent" audits #101114 on the accent
in both themes, not the dark theme's --sp-ink token.

A second scope note (M8 R2): the completion screen's host pill is theme-
invariant — body.complete-ground pins --sp-host to #6C5CE8 (the LIGHT value)
in both themes, so its white label is audited once against that fixed hex,
independent of the dark theme's #8B7CF0 token (test_complete_ground_host_pill_white_aa).
"""

from __future__ import annotations

import re
from pathlib import Path

APP_CSS = Path(__file__).resolve().parents[1] / "app" / "static" / "app.css"

# The ink that accent surfaces carry (== --sp-accent-ink in both themes; the
# dark theme's white --sp-ink is never painted on accent).
ACCENT_INK = "#101114"


def _linearize(channel: float) -> float:
    """WCAG 2.x linearization of one sRGB channel (0..1)."""
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of an #RRGGBB color."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (_linearize(c / 255) for c in (r, g, b))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    """WCAG 2.x contrast ratio (1..21)."""
    fg, bg = luminance(foreground), luminance(background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _token_blocks() -> tuple[str, str]:
    """(light, dark) token block BODIES from app.css — regex'd out of the
    file so the audit always runs against the real shipped tokens."""
    text = APP_CSS.read_text()
    light = re.search(r":root\s*\{([^}]*)\}", text)
    dark = re.search(
        r"@media \(prefers-color-scheme: dark\)\s*\{[^}]*:root\s*\{([^}]*)\}",
        text,
        re.DOTALL,
    )
    assert light is not None, ":root token block not found in app.css"
    assert dark is not None, "dark token block not found in app.css"
    return light.group(1), dark.group(1)


def _tokens(block: str) -> dict[str, str]:
    """name -> '#RRGGBB' for every color token in a token block."""
    return {
        name: f"#{value}"
        for name, value in re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b", block)
    }


_LIGHT_BLOCK, _DARK_BLOCK = _token_blocks()
LIGHT = _tokens(_LIGHT_BLOCK)
DARK = _tokens(_DARK_BLOCK)


def _assert_ratio(fg: str, bg: str, label: str, minimum: float = 4.5) -> None:
    ratio = contrast(fg, bg)
    assert ratio >= minimum, (
        f"{label}: {fg} on {bg} = {ratio:.2f}:1, below the {minimum}:1 floor"
    )


def test_sub_on_bg_aa_both_themes():
    _assert_ratio(LIGHT["sp-sub"], LIGHT["sp-bg"], "light --sp-sub on --sp-bg")
    _assert_ratio(DARK["sp-sub"], DARK["sp-bg"], "dark --sp-sub on --sp-bg")


def test_faint_on_bg_aa_both_themes():
    _assert_ratio(LIGHT["sp-faint"], LIGHT["sp-bg"], "light --sp-faint on --sp-bg")
    _assert_ratio(DARK["sp-faint"], DARK["sp-bg"], "dark --sp-faint on --sp-bg")


def test_danger_on_bg_aa_both_themes():
    _assert_ratio(LIGHT["sp-danger"], LIGHT["sp-bg"], "light --sp-danger on --sp-bg")
    _assert_ratio(DARK["sp-danger"], DARK["sp-bg"], "dark --sp-danger on --sp-bg")


def test_accent_ink_on_accent_aa_both_themes():
    _assert_ratio(
        LIGHT["sp-accent-ink"], LIGHT["sp-accent"], "light --sp-accent-ink on --sp-accent"
    )
    _assert_ratio(DARK["sp-accent-ink"], DARK["sp-accent"], "dark --sp-accent-ink on --sp-accent")


def test_ink_on_accent_aa_both_themes():
    # Accent surfaces always carry --sp-accent-ink (the light ink #101114)
    # in BOTH themes — the dark theme's white --sp-ink never sits on accent.
    _assert_ratio(ACCENT_INK, LIGHT["sp-accent"], "ink on accent (light accent)")
    _assert_ratio(ACCENT_INK, DARK["sp-accent"], "ink on accent (dark accent)")


def test_white_on_host_aa_light_theme():
    _assert_ratio("#FFFFFF", LIGHT["sp-host"], "white on light --sp-host")


def test_ink_on_host_aa_dark_theme():
    _assert_ratio(ACCENT_INK, DARK["sp-host"], "#101114 on dark --sp-host")


def test_host_on_bg_aa_both_themes():
    # --sp-host also renders as TEXT on the plain app background (host-only
    # labels like .results-group-label--host, host pills on bg surfaces), so
    # the violet itself must clear AA on --sp-bg in both themes — separate
    # from the white/#101114-on-host pairings audited above.
    _assert_ratio(LIGHT["sp-host"], LIGHT["sp-bg"], "light --sp-host on --sp-bg")
    _assert_ratio(DARK["sp-host"], DARK["sp-bg"], "dark --sp-host on --sp-bg")


def test_chip_ink_on_bg_and_card_aa_both_themes():
    # --sp-chip-ink paints table cells, chips, and meta text on BOTH the app
    # background and the card surface; every pair must clear AA in both themes.
    _assert_ratio(LIGHT["sp-chip-ink"], LIGHT["sp-bg"], "light --sp-chip-ink on --sp-bg")
    _assert_ratio(LIGHT["sp-chip-ink"], LIGHT["sp-card"], "light --sp-chip-ink on --sp-card")
    _assert_ratio(DARK["sp-chip-ink"], DARK["sp-bg"], "dark --sp-chip-ink on --sp-bg")
    _assert_ratio(DARK["sp-chip-ink"], DARK["sp-card"], "dark --sp-chip-ink on --sp-card")


def test_accent_deep_on_bg_aa_both_themes():
    _assert_ratio(LIGHT["sp-accent-deep"], LIGHT["sp-bg"], "light --sp-accent-deep on --sp-bg")
    _assert_ratio(DARK["sp-accent-deep"], DARK["sp-bg"], "dark --sp-accent-deep on --sp-bg")


def test_ink_on_bg_aaa_both_themes():
    _assert_ratio(LIGHT["sp-ink"], LIGHT["sp-bg"], "light --sp-ink on --sp-bg", minimum=7)
    _assert_ratio(DARK["sp-ink"], DARK["sp-bg"], "dark --sp-ink on --sp-bg", minimum=7)


def test_ink_ground_reversed_type_aa():
    """M8 R2: the completion screen flips to the ink ground (#101114) in BOTH
    themes with reversed type — white titles/names and the faint/sub meta
    values (#8A8DA0 / #ABAEB9) all clear AA on it. The ground is theme-
    invariant, so the pairs are audited once against the fixed hex values."""
    _assert_ratio("#FFFFFF", "#101114", "white on ink ground")
    _assert_ratio("#ABAEB9", "#101114", "sub on ink ground")
    _assert_ratio("#8A8DA0", "#101114", "faint on ink ground")


def test_complete_ground_host_pill_white_aa():
    """M8 R2: the completion screen is theme-invariant INCLUDING the host
    color — body.complete-ground pins --sp-host to the light-theme violet
    #6C5CE8 in both themes, so the "host's call" pill keeps white text on the
    ink ground (white on #6C5CE8 ≈ 4.85:1, AA). The dark theme's #8B7CF0
    would fail at ~3.4:1, which is why the R1 dark-mode ink override must not
    reach the pill. The structural asserts protect the pin + override removal
    so the numeric pair below is what actually renders."""
    text = APP_CSS.read_text()
    complete = re.search(r"body\.complete-ground\s*\{([^}]*)\}", text)
    assert complete is not None, "body.complete-ground block not found in app.css"
    pinned = re.search(r"--sp-host:\s*(#[0-9a-fA-F]{6})", complete.group(1))
    assert pinned is not None, "--sp-host is not pinned in body.complete-ground"
    assert pinned.group(1).upper() == "#6C5CE8", (
        f"ink-ground --sp-host is {pinned.group(1)}, expected #6C5CE8"
    )
    assert not re.search(r"\.complete-pill--host\s*\{[^}]*color:\s*#101114\b", text), (
        "dark-mode ink override still reaches .complete-pill--host"
    )
    _assert_ratio("#FFFFFF", "#6C5CE8", "white on pinned ink-ground --sp-host")
