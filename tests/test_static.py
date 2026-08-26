def test_app_css_served(client):
    resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "--dd-primary" in resp.text


def test_htmx_vendored_and_served(client):
    resp = client.get("/static/htmx.min.js")
    assert resp.status_code == 200
    assert "htmx" in resp.text
