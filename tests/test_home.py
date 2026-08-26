def test_home_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "What's for dinner?" in resp.text
    assert "Meal Library" in resp.text
    assert "History" in resp.text
    assert "People" in resp.text


def test_home_shows_zero_counts_on_empty_db(client):
    resp = client.get("/")
    assert "0 meals" in resp.text
    assert "0 weeks planned" in resp.text
    assert "0 active" in resp.text
