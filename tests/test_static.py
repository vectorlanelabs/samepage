def test_app_css_served(client):
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "--sp-accent" in resp.text


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
