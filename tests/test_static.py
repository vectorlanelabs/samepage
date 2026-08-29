def test_app_css_served(client):
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "--sp-accent" in resp.text


def test_htmx_vendored_and_served(client):
    resp = client.get("/static/htmx.min.js")
    assert resp.status_code == 200
    assert "htmx" in resp.text


def test_favicon_served(client):
    resp = client.get("/static/favicon.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"
