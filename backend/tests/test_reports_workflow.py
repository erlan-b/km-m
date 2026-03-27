from decimal import Decimal

from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.notification import Notification, NotificationType
from app.models.report import Report, ReportStatus
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


def create_category(db_session) -> Category:
    category = Category(name="Reports Category", slug="reports-category", is_active=True, display_order=1)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Reported listing",
        description="Reported listing description long enough",
        price=Decimal("99000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 9",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=ListingStatus.PUBLISHED,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def test_non_admin_cannot_access_report_admin_endpoints(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    reporter = create_user(db_session, "reporter-guard@example.com", [user_role])

    set_current_user(reporter)

    admin_queue_response = client.get("/api/v1/reports/admin")
    assert admin_queue_response.status_code == 403

    resolve_response = client.patch(
        "/api/v1/reports/1/resolve",
        json={"action": "resolve", "resolution_note": "x"},
    )
    assert resolve_response.status_code == 403


def test_admin_resolve_listing_report_with_moderation_updates_entities(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")

    reporter = create_user(db_session, "reporter-listing@example.com", [user_role])
    listing_owner = create_user(db_session, "owner-listing@example.com", [user_role])
    admin_user = create_user(db_session, "admin-listing@example.com", [admin_role])

    category = create_category(db_session)
    listing = create_listing(db_session, listing_owner.id, category.id)

    set_current_user(reporter)
    create_report_response = client.post(
        "/api/v1/reports",
        json={
            "target_type": "listing",
            "target_id": listing.id,
            "reason_code": "spam",
            "reason_text": "Looks suspicious",
        },
    )
    assert create_report_response.status_code == 201
    report_id = create_report_response.json()["id"]

    set_current_user(admin_user)
    queue_response = client.get("/api/v1/reports/admin", params={"status_filter": "open"})
    assert queue_response.status_code == 200
    assert queue_response.json()["total_items"] >= 1

    resolve_response = client.patch(
        f"/api/v1/reports/{report_id}/resolve",
        json={
            "action": "resolve",
            "resolution_note": "Archived after review",
            "moderation_action": "archive",
        },
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == ReportStatus.RESOLVED.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.ARCHIVED

    report = db_session.scalar(select(Report).where(Report.id == report_id))
    assert report is not None
    assert report.status == ReportStatus.RESOLVED
    assert report.reviewed_by_admin_id == admin_user.id

    notification = db_session.scalar(
        select(Notification)
        .where(
            Notification.user_id == reporter.id,
            Notification.notification_type == NotificationType.REPORT_STATUS_CHANGED,
            Notification.related_entity_type == "report",
            Notification.related_entity_id == report_id,
        )
        .order_by(Notification.id.desc())
    )
    assert notification is not None

    audit_actions = db_session.scalars(
        select(AdminAuditLog.action)
        .where(
            AdminAuditLog.target_id.in_([listing.id, report_id]),
            AdminAuditLog.target_type.in_(["listing", "report"]),
        )
        .order_by(AdminAuditLog.id.asc())
    ).all()
    assert "listing_moderation:archive" in audit_actions
    assert "report_resolve" in audit_actions


def test_admin_resolve_user_report_can_block_target_user(client, db_session, set_current_user):
    user_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")

    reporter = create_user(db_session, "reporter-user@example.com", [user_role])
    reported_user = create_user(db_session, "reported-user@example.com", [user_role])
    admin_user = create_user(db_session, "admin-user@example.com", [admin_role])

    set_current_user(reporter)
    create_report_response = client.post(
        "/api/v1/reports",
        json={
            "target_type": "user",
            "target_id": reported_user.id,
            "reason_code": "abuse",
            "reason_text": "Abusive behavior",
        },
    )
    assert create_report_response.status_code == 201
    report_id = create_report_response.json()["id"]

    set_current_user(admin_user)
    resolve_response = client.patch(
        f"/api/v1/reports/{report_id}/resolve",
        json={
            "action": "resolve",
            "resolution_note": "Blocked user",
            "moderation_action": "block",
        },
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == ReportStatus.RESOLVED.value

    db_session.refresh(reported_user)
    assert reported_user.account_status == AccountStatus.BLOCKED

    user_audit = db_session.scalar(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == "user",
            AdminAuditLog.target_id == reported_user.id,
            AdminAuditLog.action == "user_moderation:block",
        )
        .order_by(AdminAuditLog.id.desc())
    )
    assert user_audit is not None
