def test_forgot_password_message_localized_to_russian(client):
    response = client.post(
        "/api/v1/auth/forgot-password",
        headers={"X-Language": "ru"},
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Если аккаунт с таким email существует, инструкции по восстановлению были сформированы"


def test_reset_password_http_error_not_localized_by_language_header(client):
    response = client.post(
        "/api/v1/auth/reset-password",
        headers={"X-Language": "ru"},
        json={
            "reset_token": "x" * 30,
            "new_password": "StrongPass123",
            "confirm_password": "StrongPass123",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["message"] == "Invalid or expired reset token"
    assert payload["detail"] == "Invalid or expired reset token"


def test_forgot_password_message_defaults_to_english_without_language_header(client):
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "If an account with that email exists, reset instructions were generated"
