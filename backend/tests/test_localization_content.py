from app.models.admin_audit_log import AdminAuditLog
from app.models.localization_entry import LocalizationEntry
from app.models.role import Role
from app.models.user import AccountStatus, User
from sqlalchemy import select


def create_role(db_session, name: str) -> Role:
    role = Role(name=name)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


def create_user(db_session, email: str, roles: list[Role]) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        password_hash="test-hash",
        preferred_language="ru",
        account_status=AccountStatus.ACTIVE,
        roles=roles,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_public_localization_content_returns_requested_language_and_fallback(client, db_session):
    db_session.add_all(
        [
            LocalizationEntry(
                key="auth.login.title",
                translations={"en": "Login", "ru": "Vhod"},
                is_active=True,
            ),
            LocalizationEntry(
                key="auth.login.subtitle",
                translations={"en": "Welcome back"},
                is_active=True,
            ),
            LocalizationEntry(
                key="hidden.key",
                translations={"en": "Hidden"},
                is_active=False,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/localization/content", params={"language": "ru", "key_prefix": "auth."})
    assert response.status_code == 200

    payload = response.json()
    assert payload["language"] == "ru"
    assert payload["items"]["auth.login.title"] == "Vhod"
    assert payload["items"]["auth.login.subtitle"] == "Welcome back"
    assert "hidden.key" not in payload["items"]


def test_non_admin_cannot_manage_localization_entries(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    user = create_user(db_session, "user-localization@example.com", [user_role])
    set_current_user(user)

    response = client.post(
        "/api/v1/localization/admin/entries",
        json={
            "key": "app.greeting",
            "translations": {"en": "Hello", "ru": "Privet"},
            "is_active": True,
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin or moderator role required"


def test_admin_can_manage_localization_entries_and_audit_is_written(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "admin-localization@example.com", [admin_role])
    set_current_user(admin_user)

    create_response = client.post(
        "/api/v1/localization/admin/entries",
        json={
            "key": "profile.save",
            "description": "Save button label",
            "translations": {"en": "Save", "ru": "Sokhranit"},
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    entry = create_response.json()
    entry_id = entry["id"]

    list_response = client.get("/api/v1/localization/admin/entries", params={"q": "profile"})
    assert list_response.status_code == 200
    assert list_response.json()["total_items"] >= 1

    update_response = client.patch(
        f"/api/v1/localization/admin/entries/{entry_id}",
        json={
            "translations": {"en": "Save", "ru": "Sokhranit izmeneniya", "ky": "Saktap Kaluu"},
            "description": "Updated label",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["translations"]["ky"] == "Saktap Kaluu"

    deactivate_response = client.post(f"/api/v1/localization/admin/entries/{entry_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    activate_response = client.post(f"/api/v1/localization/admin/entries/{entry_id}/activate")
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True

    actions = db_session.scalars(
        select(AdminAuditLog.action)
        .where(
            AdminAuditLog.target_type == "localization_entry",
            AdminAuditLog.target_id == entry_id,
        )
        .order_by(AdminAuditLog.id.asc())
    ).all()

    assert actions == [
        "localization_entry_create",
        "localization_entry_update",
        "localization_entry_deactivate",
        "localization_entry_activate",
    ]
