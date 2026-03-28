from types import SimpleNamespace

from app.models.user import User
from sqlalchemy import select


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def register_user(client, *, email: str, password: str, preferred_language: str = "en") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": email,
            "password": password,
            "confirm_password": password,
            "preferred_language": preferred_language,
        },
    )
    assert response.status_code == 201


def login_user(client, *, email: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_auth_register_login_refresh_logout_and_profile_language_flow(client):
    email = "auth-flow@example.com"
    password = "StrongPass123"

    register_user(client, email=email, password=password)

    login_payload = login_user(client, email=email, password=password)
    access_token = login_payload["access_token"]
    refresh_token = login_payload["refresh_token"]

    me_response = client.get("/api/v1/auth/me", headers=auth_headers(access_token))
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["email"] == email
    assert me_payload["seller_type"] == "owner"
    assert me_payload["verification_status"] == "unverified"
    assert me_payload["verified_badge"] is False
    assert "created_at" in me_payload
    assert "updated_at" in me_payload
    assert "response_rate" in me_payload

    languages_response = client.get("/api/v1/auth/languages")
    assert languages_response.status_code == 200
    assert "en" in languages_response.json()["languages"]

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 200
    refreshed_payload = refresh_response.json()
    refreshed_access_token = refreshed_payload["access_token"]
    refreshed_refresh_token = refreshed_payload["refresh_token"]
    assert refreshed_refresh_token != refresh_token

    old_refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert old_refresh_response.status_code == 401

    update_language_response = client.patch(
        "/api/v1/auth/me/language",
        headers=auth_headers(refreshed_access_token),
        json={"preferred_language": "ru"},
    )
    assert update_language_response.status_code == 200
    assert update_language_response.json()["preferred_language"] == "ru"

    logout_response = client.post("/api/v1/auth/logout", json={"refresh_token": refreshed_refresh_token})
    assert logout_response.status_code == 200

    revoked_refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refreshed_refresh_token})
    assert revoked_refresh_response.status_code == 401


def test_auth_forgot_reset_and_change_password_revokes_tokens(client, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.get_settings",
        lambda: SimpleNamespace(expose_password_reset_token=True, supported_languages=["en", "ru", "ky"]),
    )

    email = "auth-reset@example.com"
    first_password = "InitialPass123"
    second_password = "AfterReset123"
    third_password = "AfterChange123"

    register_user(client, email=email, password=first_password)

    forgot_response = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot_response.status_code == 200
    reset_token = forgot_response.json()["reset_token"]
    assert reset_token is not None

    reset_response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "reset_token": reset_token,
            "new_password": second_password,
            "confirm_password": second_password,
        },
    )
    assert reset_response.status_code == 200

    old_login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": first_password},
    )
    assert old_login_response.status_code == 401

    second_login_payload = login_user(client, email=email, password=second_password)
    second_access_token = second_login_payload["access_token"]
    second_refresh_token = second_login_payload["refresh_token"]

    change_response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(second_access_token),
        json={
            "current_password": second_password,
            "new_password": third_password,
            "confirm_password": third_password,
        },
    )
    assert change_response.status_code == 200

    revoked_refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh_token})
    assert revoked_refresh_response.status_code == 401

    second_login_again_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": second_password},
    )
    assert second_login_again_response.status_code == 401

    third_login_payload = login_user(client, email=email, password=third_password)
    assert third_login_payload["access_token"]

    persisted_user = db_session.scalar(select(User).where(User.email == email))
    assert persisted_user is not None
