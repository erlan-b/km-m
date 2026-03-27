def test_i18n_pages_catalog_uses_request_language(client):
    response = client.get("/api/v1/i18n/pages", headers={"X-Language": "ru"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "ru"
    assert "dashboard" in payload["pages"]


def test_i18n_dashboard_page_translations_in_russian(client):
    response = client.get("/api/v1/i18n/pages/dashboard", headers={"X-Language": "ru"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"] == "dashboard"
    assert payload["language"] == "ru"
    assert payload["texts"]["title"] == "Панель управления"
    assert payload["texts"]["refresh"] == "Обновить"


def test_i18n_pages_unknown_page_returns_404(client):
    response = client.get("/api/v1/i18n/pages/missing-page", headers={"X-Language": "ru"})

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["message"] == "Translation page not found"
    assert payload["detail"] == "Translation page not found"