from datetime import datetime, timedelta, timezone

from app.models.admin_audit_log import AdminAuditLog
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


def create_audit_log(
    db_session,
    *,
    admin_user_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    details: str | None,
    created_at: datetime,
) -> AdminAuditLog:
    item = AdminAuditLog(
        admin_user_id=admin_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        created_at=created_at,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


def test_non_admin_cannot_access_admin_audit_logs(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    user = create_user(db_session, "audit-guard-user@example.com", [user_role])

    set_current_user(user)

    response = client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin or moderator role required"


def test_admin_can_filter_audit_logs_by_action_target_and_admin(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")

    admin_user = create_user(db_session, "audit-admin@example.com", [admin_role])
    second_admin = create_user(db_session, "audit-admin-2@example.com", [admin_role])

    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    matching = create_audit_log(
        db_session,
        admin_user_id=admin_user.id,
        action="user_suspend",
        target_type="user",
        target_id=18,
        details="suspicious activity",
        created_at=now - timedelta(minutes=30),
    )

    create_audit_log(
        db_session,
        admin_user_id=admin_user.id,
        action="user_unsuspend",
        target_type="user",
        target_id=18,
        details="appeal approved",
        created_at=now - timedelta(minutes=20),
    )

    create_audit_log(
        db_session,
        admin_user_id=second_admin.id,
        action="listing_moderation:archive",
        target_type="listing",
        target_id=55,
        details="duplicate content",
        created_at=now - timedelta(minutes=10),
    )

    set_current_user(admin_user)

    response = client.get(
        "/api/v1/admin/audit-logs",
        params={
            "action": "user_suspend",
            "target_type": "user",
            "admin_user_id": admin_user.id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_items"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == matching.id
    assert payload["items"][0]["action"] == "user_suspend"


def test_admin_audit_logs_are_sorted_by_created_at_desc(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "audit-sort-admin@example.com", [admin_role])

    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)

    oldest = create_audit_log(
        db_session,
        admin_user_id=admin_user.id,
        action="action_old",
        target_type="user",
        target_id=1,
        details=None,
        created_at=now - timedelta(minutes=3),
    )
    middle = create_audit_log(
        db_session,
        admin_user_id=admin_user.id,
        action="action_middle",
        target_type="user",
        target_id=2,
        details=None,
        created_at=now - timedelta(minutes=2),
    )
    newest = create_audit_log(
        db_session,
        admin_user_id=admin_user.id,
        action="action_new",
        target_type="user",
        target_id=3,
        details=None,
        created_at=now - timedelta(minutes=1),
    )

    set_current_user(admin_user)

    response = client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 200

    item_ids = [item["id"] for item in response.json()["items"]]
    assert item_ids.index(newest.id) < item_ids.index(middle.id) < item_ids.index(oldest.id)
