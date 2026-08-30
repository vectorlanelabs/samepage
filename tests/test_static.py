def test_app_css_served(client):
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "--sp-accent" in resp.text


def test_base_template_uses_loud_moments_fonts_and_ink_theme(client):
    """M8 R1: base.html pulls Schibsted Grotesk + IBM Plex Mono and sets the
    Loud Moments ink theme color (was Hanken Grotesk + accent blue)."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Schibsted+Grotesk" in resp.text
    assert "IBM+Plex+Mono" in resp.text
    assert 'content="#101114"' in resp.text
    assert "#4468D2" not in resp.text


def test_app_css_has_no_quiet_kitchen_accent_literals():
    """M8 R1: the Quiet Kitchen accent blue is gone from the stylesheet —
    read the file directly so a serving/config regression can't hide it."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text()
    assert "#4468D2" not in css


def test_lib_cell_metadata_color_is_chip_ink_not_link_accent(client):
    """Desktop library metadata cells (type/tags/kept/last) explicitly set
    chip-ink — the row is an <a>, so without an explicit color they'd inherit
    the accent-blue link color."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    block = resp.text[resp.text.index(".lib-cell-type,") :]
    assert "color: var(--sp-chip-ink);" in block


def test_htmx_vendored_and_served(client):
    resp = client.get("/static/htmx.min.js")
    assert resp.status_code == 200
    assert "htmx" in resp.text


def test_favicon_served(client):
    resp = client.get("/static/favicon.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_pwa_manifest_served_and_valid(client):
    import json
    resp = client.get("/static/manifest.webmanifest")
    assert resp.status_code == 200
    manifest = json.loads(resp.text)
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"
    assert any(i["sizes"] == "512x512" for i in manifest["icons"])


def test_service_worker_served_at_root_scope(client):
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    assert "addEventListener" in resp.text  # has a fetch handler → installable


def test_pwa_icons_served(client):
    for icon in ("icon-192.png", "icon-512.png", "icon-maskable-512.png"):
        resp = client.get(f"/static/{icon}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"


def test_app_css_has_no_full_pill_radius():
    """M8 R3: the 999px 'full pill' radius is retired — every chip/badge/brand
    bar now uses a 6px radius (mono) or 50% (true circles only). Read the file
    directly so a serving/config regression can't hide a stray declaration."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text()
    assert "border-radius: 999px" not in css
    assert "border-radius:999px" not in css


def test_guest_topbar_has_visible_display_rule():
    """M8 R4 fix: the base .topbar rule is display: none (signed-in desktop
    uses the sidebar instead). After layout moved into .topbar-inner, the
    .shell--guest .topbar override lost its display declaration and the guest
    header went invisible at every width. The override must declare a
    non-none display. String-level is enough — this class of bug is invisible
    to template tests."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text()
    block = css[css.index(".shell--guest .topbar") :]
    block = block[: block.index("}")]
    assert "display:" in block
    assert "display: none" not in block


def test_sidebar_scroll_region_declares_overflow_y_auto():
    """R5b: the sidebar's nav/collections region is the one scroll area — the
    .sidebar-scroll rule must declare overflow-y: auto on a flex: 1 1 auto
    region so the Host/Join/account/Sign out cluster stays pinned at the
    bottom of the 100vh sidebar when an account has many collections (the old
    .sidebar-spacer let the list overflow and shove the cluster off-screen).
    String-level is enough — this class of layout bug is invisible to
    template tests."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text()
    block = css[css.index(".sidebar-scroll") :]
    block = block[: block.index("}")]
    assert "flex: 1 1 auto;" in block
    assert "min-width: 0;" in block
    assert "overflow-y: auto;" in block


def test_hub_cta_hidden_at_desktop_widths():
    """M8 R5: the hub's bottom CTA stack (Host a session + Join with a code)
    is phone-only — at >=900px the desktop sidebar carries both actions, so
    .hub-cta hides. String-level like the guest-topbar test: verify the rule
    sits inside the min-width: 900px media query (a top-level display:none
    would kill the phone CTAs too)."""
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "app" / "static" / "app.css").read_text()
    start = css.index("@media (min-width: 900px)")
    # Walk to the media query's closing brace, depth-aware — the block
    # contains many nested selector rules.
    depth = 0
    end = len(css)
    for i, ch in enumerate(css[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    media = css[start:end]
    assert ".hub-cta { display: none; }" in media


def test_hub_card_meta_uses_mono_voice(client):
    """M8 R3: the collections-hub card meta line (items count · last session
    date) renders in the mono voice — faint 12px IBM Plex Mono."""
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    block = resp.text[resp.text.index(".hub-card-meta") :]
    assert "font-family: var(--sp-font-mono);" in block
    assert "font-size: 12px;" in block
