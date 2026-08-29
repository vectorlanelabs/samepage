"""Privacy and terms are public static pages (no auth) — Google's consent
screen links to /privacy, so it must render for signed-out visitors."""


def test_privacy_public(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert "Privacy" in resp.text
    # The privacy claim the product actually makes.
    assert "every individual vote is deleted" in resp.text


def test_terms_public(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    assert "Terms" in resp.text


def test_footer_links_on_a_page(client):
    body = client.get("/login").text
    assert 'href="/privacy"' in body
    assert 'href="/terms"' in body
