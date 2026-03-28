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


def test_support_has_read_only_admin_panel_access(client, db_session, set_current_user):
    support_role = create_role(db_session, "support")
    support_user = create_user(db_session, "matrix-support@example.com", [support_role])
    set_current_user(support_user)

    assert client.get("/api/v1/admin/dashboard").status_code == 200
    assert client.get("/api/v1/listings/admin/moderation").status_code == 200
    assert client.get("/api/v1/reports/admin").status_code == 200
    assert client.get("/api/v1/categories/admin").status_code == 200
    assert client.get("/api/v1/payments/admin").status_code == 200
    assert client.get("/api/v1/promotions/admin").status_code == 200
    assert client.get("/api/v1/promotions/packages/admin").status_code == 200
    assert client.get("/api/v1/admin/users").status_code == 200
    assert client.get("/api/v1/admin/messages/conversations", params={"user_id": 1}).status_code == 200

    moderate_listing = client.patch(
        "/api/v1/listings/1/moderation",
        json={"action": "approve", "note": "x"},
    )
    assert moderate_listing.status_code == 403
    assert moderate_listing.json()["detail"] == "Moderator, admin or superadmin role required"

    resolve_report = client.patch(
        "/api/v1/reports/1/resolve",
        json={"action": "resolve", "resolution_note": "x"},
    )
    assert resolve_report.status_code == 403
    assert resolve_report.json()["detail"] == "Moderator, admin or superadmin role required"

    create_category = client.post(
        "/api/v1/categories",
        json={
            "name": "Matrix category",
            "slug": "matrix-category",
            "display_order": 1,
            "is_active": True,
            "attributes_schema": [],
        },
    )
    assert create_category.status_code == 403
    assert create_category.json()["detail"] == "Moderator, admin or superadmin role required"

    suspend_user = client.post(
        "/api/v1/admin/users/1/suspend",
        json={"reason": "x"},
    )
    assert suspend_user.status_code == 403
    assert suspend_user.json()["detail"] == "Admin or superadmin role required"

    verify_user = client.post(
        "/api/v1/admin/users/1/verification",
        json={"verification_status": "verified", "reason": "x"},
    )
    assert verify_user.status_code == 403
    assert verify_user.json()["detail"] == "Admin or superadmin role required"

    create_package = client.post(
        "/api/v1/promotions/packages/admin",
        json={
            "title": "Matrix package",
            "description": "x",
            "duration_days": 7,
            "price": "100.00",
            "currency": "KGS",
        },
    )
    assert create_package.status_code == 403
    assert create_package.json()["detail"] == "Admin or superadmin role required"

    deactivate_promotion = client.patch(
        "/api/v1/promotions/admin/1/deactivate",
        json={"reason": "x"},
    )
    assert deactivate_promotion.status_code == 403
    assert deactivate_promotion.json()["detail"] == "Admin or superadmin role required"

    audit_logs = client.get("/api/v1/admin/audit-logs")
    assert audit_logs.status_code == 403
    assert audit_logs.json()["detail"] == "Admin or superadmin role required"


def test_moderator_can_moderate_but_cannot_perform_admin_management(client, db_session, set_current_user):
    moderator_role = create_role(db_session, "moderator")
    moderator_user = create_user(db_session, "matrix-moderator@example.com", [moderator_role])
    set_current_user(moderator_user)

    create_category = client.post(
        "/api/v1/categories",
        json={
            "name": "Moderator category",
            "slug": "moderator-category",
            "display_order": 2,
            "is_active": True,
            "attributes_schema": [],
        },
    )
    assert create_category.status_code == 201

    moderate_listing = client.patch(
        "/api/v1/listings/99999/moderation",
        json={"action": "approve", "note": "x"},
    )
    assert moderate_listing.status_code == 404

    resolve_report = client.patch(
        "/api/v1/reports/99999/resolve",
        json={"action": "resolve", "resolution_note": "x"},
    )
    assert resolve_report.status_code == 404

    suspend_user = client.post(
        "/api/v1/admin/users/1/suspend",
        json={"reason": "x"},
    )
    assert suspend_user.status_code == 403
    assert suspend_user.json()["detail"] == "Admin or superadmin role required"

    audit_logs = client.get("/api/v1/admin/audit-logs")
    assert audit_logs.status_code == 403
    assert audit_logs.json()["detail"] == "Admin or superadmin role required"


def test_admin_and_superadmin_have_admin_management_access(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    superadmin_role = create_role(db_session, "superadmin")
    user_role = create_role(db_session, "user")

    admin_user = create_user(db_session, "matrix-admin@example.com", [admin_role])
    superadmin_user = create_user(db_session, "matrix-superadmin@example.com", [superadmin_role])
    target_user = create_user(db_session, "matrix-target@example.com", [user_role])

    set_current_user(admin_user)
    assert client.get("/api/v1/admin/audit-logs").status_code == 200

    i18n_create_by_admin = client.post(
        "/api/v1/i18n/admin/entries",
        json={
            "page_key": "matrix_page",
            "text_key": "title",
            "language": "ru",
            "text_value": "Матрица",
        },
    )
    assert i18n_create_by_admin.status_code == 201

    set_current_user(superadmin_user)
    suspend_response = client.post(
        f"/api/v1/admin/users/{target_user.id}/suspend",
        json={"reason": "policy"},
    )
    assert suspend_response.status_code == 200
    assert suspend_response.json()["account_status"] == "blocked"
