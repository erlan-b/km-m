from app.models.role import Role
from app.models.user import AccountStatus, User


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


def test_admin_can_crud_localization_entries_and_override_public_page(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "i18n-admin@example.com", [admin_role])
    set_current_user(admin_user)

    create_response = client.post(
        "/api/v1/i18n/admin/entries",
        json={
            "page_key": "dashboard",
            "text_key": "title",
            "language": "ru",
            "text_value": "Кастомная панель",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    entry_payload = create_response.json()
    entry_id = entry_payload["id"]
    assert entry_payload["page_key"] == "dashboard"
    assert entry_payload["text_key"] == "title"
    assert entry_payload["language"] == "ru"

    list_response = client.get(
        "/api/v1/i18n/admin/entries",
        params={"page_key": "dashboard", "language": "ru", "q": "title"},
    )
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total_items"] == 1
    assert list_payload["items"][0]["id"] == entry_id

    page_ru_response = client.get("/api/v1/i18n/pages/dashboard", params={"lang": "ru"})
    assert page_ru_response.status_code == 200
    assert page_ru_response.json()["texts"]["title"] == "Кастомная панель"

    update_response = client.patch(
        f"/api/v1/i18n/admin/entries/{entry_id}",
        json={
            "text_value": "Кастомная панель v2",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["text_value"] == "Кастомная панель v2"

    page_updated_response = client.get("/api/v1/i18n/pages/dashboard", params={"lang": "ru"})
    assert page_updated_response.status_code == 200
    assert page_updated_response.json()["texts"]["title"] == "Кастомная панель v2"

    delete_response = client.delete(f"/api/v1/i18n/admin/entries/{entry_id}")
    assert delete_response.status_code == 204

    page_after_delete_response = client.get("/api/v1/i18n/pages/dashboard", params={"lang": "ru"})
    assert page_after_delete_response.status_code == 200
    assert page_after_delete_response.json()["texts"]["title"] == "Панель управления"


def test_i18n_admin_entries_allow_dynamic_page_registration(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "i18n-admin-pages@example.com", [admin_role])
    set_current_user(admin_user)

    create_response = client.post(
        "/api/v1/i18n/admin/entries",
        json={
            "page_key": "custom_page",
            "text_key": "headline",
            "language": "ru",
            "text_value": "Кастомная страница",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201

    catalog_response = client.get("/api/v1/i18n/pages", params={"lang": "ru"})
    assert catalog_response.status_code == 200
    assert "custom_page" in catalog_response.json()["pages"]

    page_response = client.get("/api/v1/i18n/pages/custom-page", params={"lang": "ru"})
    assert page_response.status_code == 200
    assert page_response.json()["texts"]["headline"] == "Кастомная страница"


def test_i18n_admin_entries_require_admin_or_superadmin(client, db_session, set_current_user):
    support_role = create_role(db_session, "support")
    moderator_role = create_role(db_session, "moderator")
    admin_role = create_role(db_session, "admin")
    superadmin_role = create_role(db_session, "superadmin")

    support_user = create_user(db_session, "i18n-support@example.com", [support_role])
    moderator_user = create_user(db_session, "i18n-moderator@example.com", [moderator_role])
    admin_user = create_user(db_session, "i18n-admin-access@example.com", [admin_role])
    superadmin_user = create_user(db_session, "i18n-superadmin-access@example.com", [superadmin_role])

    set_current_user(support_user)
    support_response = client.get("/api/v1/i18n/admin/entries")
    assert support_response.status_code == 403
    assert support_response.json()["detail"] == "Admin or superadmin role required"

    set_current_user(moderator_user)
    moderator_response = client.post(
        "/api/v1/i18n/admin/entries",
        json={
            "page_key": "guard_page",
            "text_key": "title",
            "language": "ru",
            "text_value": "Moderator should be denied",
        },
    )
    assert moderator_response.status_code == 403
    assert moderator_response.json()["detail"] == "Admin or superadmin role required"

    set_current_user(admin_user)
    admin_response = client.get("/api/v1/i18n/admin/entries")
    assert admin_response.status_code == 200

    set_current_user(superadmin_user)
    superadmin_response = client.post(
        "/api/v1/i18n/admin/entries",
        json={
            "page_key": "guard_page",
            "text_key": "title",
            "language": "ru",
            "text_value": "Superadmin allowed",
        },
    )
    assert superadmin_response.status_code == 201
