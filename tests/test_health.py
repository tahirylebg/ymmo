def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_reaches_database(client):
    response = client.get("/api/health/db")
    assert response.status_code == 200
    assert response.json()["database"] == "reachable"


def test_home_page_is_accessible_html(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'lang="fr"' in html
    assert 'href="#main"' in html  # skip link for keyboard users


def test_openapi_documentation_is_exposed(client):
    assert client.get("/api/openapi.json").status_code == 200
