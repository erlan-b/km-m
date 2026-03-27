from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from db.scripts.seed_basics import seed_categories
from app.db.session import SessionLocal
from app.models.admin_audit_log import AdminAuditLog
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.message import Message, MessageType
from app.models.payment import Payment, PaymentStatus
from app.models.report import Report, ReportStatus, ReportTargetType
from app.models.role import Role
from app.models.user import AccountStatus, User

SEED_NAMESPACE = "admin-panel-v1"


@dataclass
class SeedStats:
    users_created: int = 0
    listings_created: int = 0
    payments_created: int = 0
    reports_created: int = 0
    audit_logs_created: int = 0
    conversations_created: int = 0
    messages_created: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _get_or_create_role(db: Session, role_name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is not None:
        return role

    role = Role(name=role_name)
    db.add(role)
    db.flush()
    return role


def _get_or_create_admin_or_moderator(db: Session, role_name: str, *, email: str, full_name: str, password: str) -> User:
    user = db.scalar(select(User).where(User.roles.any(Role.name == role_name)).order_by(User.id.asc()))
    role = _get_or_create_role(db, role_name)

    if user is not None:
        if role not in user.roles:
            user.roles = [*user.roles, role]
            db.add(user)
        return user

    existing_by_email = db.scalar(select(User).where(User.email == email.lower()))
    if existing_by_email is not None:
        existing_by_email.roles = [*existing_by_email.roles, role]
        existing_by_email.account_status = AccountStatus.ACTIVE
        db.add(existing_by_email)
        return existing_by_email

    user = User(
        full_name=full_name,
        email=email.lower(),
        password_hash=hash_password(password),
        preferred_language="en" if role_name == "admin" else "ru",
        account_status=AccountStatus.ACTIVE,
        roles=[role],
    )
    db.add(user)
    db.flush()
    return user


def _ensure_regular_user(db: Session, user_role: Role, index: int) -> tuple[User, bool]:
    email = f"seed.user{index:02d}@demo.kg"
    user = db.scalar(select(User).where(User.email == email))

    if index % 11 == 0:
        account_status = AccountStatus.BLOCKED
    elif index % 13 == 0:
        account_status = AccountStatus.DEACTIVATED
    elif index % 7 == 0:
        account_status = AccountStatus.PENDING_VERIFICATION
    else:
        account_status = AccountStatus.ACTIVE

    preferred_language = "ru" if index % 2 == 0 else "en"

    created = False
    if user is None:
        user = User(
            full_name=f"Seed User {index:02d}",
            email=email,
            password_hash=hash_password("User12345!"),
            preferred_language=preferred_language,
            account_status=account_status,
            roles=[user_role],
        )
        db.add(user)
        db.flush()
        created = True
    else:
        user.full_name = f"Seed User {index:02d}"
        user.preferred_language = preferred_language
        user.account_status = account_status
        user.roles = [user_role]
        db.add(user)

    return user, created


def _ensure_listing(
    db: Session,
    *,
    owner: User,
    category: Category,
    index: int,
    slot: int,
    status: ListingStatus,
    is_subscription: bool,
    now: datetime,
) -> tuple[Listing, bool]:
    title = f"[SEED:{SEED_NAMESPACE}] Listing U{index:02d}-{slot}"
    listing = db.scalar(
        select(Listing).where(
            Listing.owner_id == owner.id,
            Listing.title == title,
        )
    )

    transaction_type = (TransactionType.SALE, TransactionType.RENT_LONG, TransactionType.RENT_DAILY)[(index + slot) % 3]
    base_price = Decimal("45000.00") + Decimal(index * 1700 + slot * 400)

    created = False
    if listing is None:
        listing = Listing(
            owner_id=owner.id,
            category_id=category.id,
            transaction_type=transaction_type,
            title=title,
            description=f"Seed listing data for admin module checks ({index}-{slot}).",
            price=base_price,
            currency="KGS",
            city=("Bishkek", "Osh", "Karakol", "Jalal-Abad")[(index + slot) % 4],
            address_line=f"Seed street {index}-{slot}",
            latitude=Decimal("42.8700000") + (Decimal(index) / Decimal("10000")) + (Decimal(slot) / Decimal("100000")),
            longitude=Decimal("74.5600000") + (Decimal(index) / Decimal("10000")) + (Decimal(slot) / Decimal("100000")),
            map_address_label=f"Seed point {index}-{slot}",
            dynamic_attributes={"rooms": (index % 5) + 1, "floor": (index % 12) + 1},
            status=status,
            view_count=index * 9 + slot,
            favorite_count=index % 7,
            is_subscription=is_subscription,
            subscription_expires_at=now + timedelta(days=14 + index % 7) if is_subscription else None,
        )
        db.add(listing)
        db.flush()
        created = True
    else:
        listing.category_id = category.id
        listing.transaction_type = transaction_type
        listing.description = f"Seed listing data for admin module checks ({index}-{slot})."
        listing.price = base_price
        listing.currency = "KGS"
        listing.city = ("Bishkek", "Osh", "Karakol", "Jalal-Abad")[(index + slot) % 4]
        listing.address_line = f"Seed street {index}-{slot}"
        listing.map_address_label = f"Seed point {index}-{slot}"
        listing.dynamic_attributes = {"rooms": (index % 5) + 1, "floor": (index % 12) + 1}
        listing.status = status
        listing.view_count = index * 9 + slot
        listing.favorite_count = index % 7
        listing.is_subscription = is_subscription
        listing.subscription_expires_at = now + timedelta(days=14 + index % 7) if is_subscription else None
        db.add(listing)

    return listing, created


def _ensure_payment(
    db: Session,
    *,
    user_id: int,
    listing_id: int,
    key: str,
    status: PaymentStatus,
    payment_provider: str,
    amount: Decimal,
    created_at: datetime,
) -> tuple[Payment, bool]:
    provider_reference = f"seed-{SEED_NAMESPACE}-{key}"
    payment = db.scalar(select(Payment).where(Payment.provider_reference == provider_reference))

    paid_at: datetime | None
    if status in {PaymentStatus.SUCCESSFUL, PaymentStatus.REFUNDED}:
        paid_at = created_at + timedelta(hours=2)
    else:
        paid_at = None

    created = False
    if payment is None:
        payment = Payment(
            user_id=user_id,
            listing_id=listing_id,
            amount=amount,
            currency="KGS",
            status=status,
            payment_provider=payment_provider,
            provider_reference=provider_reference,
            created_at=created_at,
            updated_at=created_at,
            paid_at=paid_at,
        )
        db.add(payment)
        db.flush()
        created = True
    else:
        payment.user_id = user_id
        payment.listing_id = listing_id
        payment.amount = amount
        payment.currency = "KGS"
        payment.status = status
        payment.payment_provider = payment_provider
        payment.created_at = created_at
        payment.updated_at = created_at
        payment.paid_at = paid_at
        db.add(payment)

    return payment, created


def _ensure_report(
    db: Session,
    *,
    key: str,
    reporter_user_id: int,
    target_type: ReportTargetType,
    target_id: int,
    status: ReportStatus,
    reviewed_by_admin_id: int | None,
    created_at: datetime,
) -> tuple[Report, bool]:
    marker = f"[SEED:{SEED_NAMESPACE}] report {key}"
    report = db.scalar(select(Report).where(Report.reason_text == marker))

    reviewed_at = created_at + timedelta(hours=4) if status != ReportStatus.OPEN else None
    resolution_note = "Processed by seed flow" if status != ReportStatus.OPEN else None

    created = False
    if report is None:
        report = Report(
            reporter_user_id=reporter_user_id,
            target_type=target_type,
            target_id=target_id,
            reason_code=("spam", "abuse", "fraud", "duplicate")[int(key) % 4],
            reason_text=marker,
            status=status,
            resolution_note=resolution_note,
            reviewed_by_admin_id=reviewed_by_admin_id,
            created_at=created_at,
            reviewed_at=reviewed_at,
        )
        db.add(report)
        db.flush()
        created = True
    else:
        report.reporter_user_id = reporter_user_id
        report.target_type = target_type
        report.target_id = target_id
        report.reason_code = ("spam", "abuse", "fraud", "duplicate")[int(key) % 4]
        report.reason_text = marker
        report.status = status
        report.resolution_note = resolution_note
        report.reviewed_by_admin_id = reviewed_by_admin_id
        report.created_at = created_at
        report.reviewed_at = reviewed_at
        db.add(report)

    return report, created


def _ensure_audit_log(
    db: Session,
    *,
    key: str,
    admin_user_id: int,
    action: str,
    target_type: str,
    target_id: int,
    created_at: datetime,
) -> tuple[AdminAuditLog, bool]:
    details = f"[SEED:{SEED_NAMESPACE}] audit {key}"
    item = db.scalar(select(AdminAuditLog).where(AdminAuditLog.details == details))

    created = False
    if item is None:
        item = AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            created_at=created_at,
        )
        db.add(item)
        db.flush()
        created = True
    else:
        item.admin_user_id = admin_user_id
        item.action = action
        item.target_type = target_type
        item.target_id = target_id
        item.details = details
        item.created_at = created_at
        db.add(item)

    return item, created


def _ensure_conversation_and_messages(
    db: Session,
    *,
    listing: Listing,
    participant_user_id: int,
    key: str,
    now: datetime,
) -> tuple[bool, int]:
    participant_a_id, participant_b_id = sorted((listing.owner_id, participant_user_id))

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.listing_id == listing.id,
            Conversation.participant_a_id == participant_a_id,
            Conversation.participant_b_id == participant_b_id,
        )
    )

    conversation_created = False
    if conversation is None:
        conversation = Conversation(
            listing_id=listing.id,
            created_by_user_id=participant_user_id,
            participant_a_id=participant_a_id,
            participant_b_id=participant_b_id,
            created_at=now - timedelta(days=int(key) % 10),
        )
        db.add(conversation)
        db.flush()
        conversation_created = True

    message_created_count = 0
    for offset in (0, 1):
        marker = f"[SEED:{SEED_NAMESPACE}] convo {key} msg {offset + 1}"
        existing = db.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.text_body == marker,
            )
        )
        if existing is None:
            sender_id = participant_user_id if offset == 0 else listing.owner_id
            sent_at = now - timedelta(days=int(key) % 10, minutes=offset * 5)
            db.add(
                Message(
                    conversation_id=conversation.id,
                    sender_id=sender_id,
                    message_type=MessageType.TEXT,
                    text_body=marker,
                    is_read=offset == 1,
                    sent_at=sent_at,
                )
            )
            conversation.last_message_at = sent_at
            db.add(conversation)
            message_created_count += 1

    return conversation_created, message_created_count


def seed_admin_panel_demo(*, regular_user_count: int = 30) -> SeedStats:
    if regular_user_count < 1:
        raise ValueError("regular_user_count must be >= 1")

    seed_categories()

    stats = SeedStats()
    now = _utc_now()

    with SessionLocal() as db:
        admin_role = _get_or_create_role(db, "admin")
        moderator_role = _get_or_create_role(db, "moderator")
        user_role = _get_or_create_role(db, "user")

        admin_user = _get_or_create_admin_or_moderator(
            db,
            "admin",
            email="admin@demo.kg",
            full_name="Demo Admin",
            password="Admin12345!",
        )
        moderator_user = _get_or_create_admin_or_moderator(
            db,
            "moderator",
            email="moderator@demo.kg",
            full_name="Demo Moderator",
            password="Moderator12345!",
        )

        if admin_role not in admin_user.roles:
            admin_user.roles = [*admin_user.roles, admin_role]
        if moderator_role not in moderator_user.roles:
            moderator_user.roles = [*moderator_user.roles, moderator_role]
        db.add(admin_user)
        db.add(moderator_user)

        categories = db.scalars(select(Category).order_by(Category.id.asc())).all()
        if not categories:
            raise RuntimeError("No categories found after seeding")

        regular_users: list[User] = []
        listings: list[Listing] = []
        published_listings: list[Listing] = []

        statuses_cycle = [
            ListingStatus.PUBLISHED,
            ListingStatus.PENDING_REVIEW,
            ListingStatus.REJECTED,
            ListingStatus.ARCHIVED,
            ListingStatus.INACTIVE,
            ListingStatus.SOLD,
            ListingStatus.DRAFT,
        ]

        for index in range(1, regular_user_count + 1):
            user, created = _ensure_regular_user(db, user_role, index)
            regular_users.append(user)
            if created:
                stats.users_created += 1

            for slot in (1, 2):
                status = statuses_cycle[(index + slot) % len(statuses_cycle)]
                is_subscription = slot == 1 and index % 3 == 0
                if is_subscription:
                    status = ListingStatus.PUBLISHED

                listing, listing_created = _ensure_listing(
                    db,
                    owner=user,
                    category=categories[(index + slot) % len(categories)],
                    index=index,
                    slot=slot,
                    status=status,
                    is_subscription=is_subscription,
                    now=now,
                )
                listings.append(listing)
                if listing.status == ListingStatus.PUBLISHED:
                    published_listings.append(listing)
                if listing_created:
                    stats.listings_created += 1

        payment_statuses = [
            PaymentStatus.SUCCESSFUL,
            PaymentStatus.PENDING,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
            PaymentStatus.REFUNDED,
        ]
        providers = ["mock", "stripe", "elsom", "mbank"]

        for index, user in enumerate(regular_users, start=1):
            owner_listings = [item for item in listings if item.owner_id == user.id]
            if not owner_listings:
                continue

            primary_listing = owner_listings[0]
            status = payment_statuses[index % len(payment_statuses)]
            provider = providers[index % len(providers)]
            amount = Decimal("350.00") + Decimal(index * 15)
            created_at = now - timedelta(days=index % 20, hours=index % 5)

            _, created = _ensure_payment(
                db,
                user_id=user.id,
                listing_id=primary_listing.id,
                key=f"u{index:02d}-1",
                status=status,
                payment_provider=provider,
                amount=amount,
                created_at=created_at,
            )
            if created:
                stats.payments_created += 1

        for index in range(1, min(regular_user_count, 24) + 1):
            reporter = regular_users[(index - 1) % len(regular_users)]
            if index % 2 == 0:
                target_type = ReportTargetType.LISTING
                target_id = listings[(index * 3) % len(listings)].id
            else:
                target_type = ReportTargetType.USER
                target_id = regular_users[(index * 2) % len(regular_users)].id

            status = (ReportStatus.OPEN, ReportStatus.RESOLVED, ReportStatus.DISMISSED)[index % 3]
            reviewed_by_admin_id = None
            if status != ReportStatus.OPEN:
                reviewed_by_admin_id = admin_user.id if index % 2 == 0 else moderator_user.id

            _, created = _ensure_report(
                db,
                key=str(index),
                reporter_user_id=reporter.id,
                target_type=target_type,
                target_id=target_id,
                status=status,
                reviewed_by_admin_id=reviewed_by_admin_id,
                created_at=now - timedelta(days=index % 15, hours=index % 6),
            )
            if created:
                stats.reports_created += 1

        action_targets: list[tuple[str, str]] = [
            ("user_suspend", "user"),
            ("user_unsuspend", "user"),
            ("listing_moderation:reject", "listing"),
            ("listing_moderation:archive", "listing"),
            ("report_resolve", "report"),
            ("report_dismiss", "report"),
            ("category_update", "category"),
            ("payment_review", "payment"),
        ]

        for index in range(1, 41):
            action, target_type = action_targets[index % len(action_targets)]
            if target_type == "user":
                target_id = regular_users[index % len(regular_users)].id
            elif target_type == "listing":
                target_id = listings[index % len(listings)].id
            elif target_type == "report":
                target_id = index
            elif target_type == "category":
                target_id = categories[index % len(categories)].id
            else:
                target_id = index

            _, created = _ensure_audit_log(
                db,
                key=str(index),
                admin_user_id=admin_user.id if index % 2 == 0 else moderator_user.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                created_at=now - timedelta(days=index % 12, minutes=index * 3),
            )
            if created:
                stats.audit_logs_created += 1

        conversation_candidates = published_listings[: min(len(published_listings), 14)]
        for index, listing in enumerate(conversation_candidates, start=1):
            participant = regular_users[(index * 3) % len(regular_users)]
            if participant.id == listing.owner_id:
                participant = regular_users[(index * 3 + 1) % len(regular_users)]

            conversation_created, message_created = _ensure_conversation_and_messages(
                db,
                listing=listing,
                participant_user_id=participant.id,
                key=str(index),
                now=now,
            )
            if conversation_created:
                stats.conversations_created += 1
            stats.messages_created += message_created

        db.commit()

    print("Admin panel demo seed complete")
    print(f"Regular users requested: {regular_user_count}")
    print(
        "Created -> "
        f"users: {stats.users_created}, "
        f"listings: {stats.listings_created}, "
        f"payments: {stats.payments_created}, "
        f"reports: {stats.reports_created}, "
        f"audit_logs: {stats.audit_logs_created}, "
        f"conversations: {stats.conversations_created}, "
        f"messages: {stats.messages_created}"
    )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo data for all admin modules")
    parser.add_argument("--users", type=int, default=30, help="Regular users count to seed")
    args = parser.parse_args()

    seed_admin_panel_demo(regular_user_count=args.users)


if __name__ == "__main__":
    main()
