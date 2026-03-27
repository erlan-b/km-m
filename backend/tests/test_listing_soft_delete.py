from decimal import Decimal

from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
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
    category = Category(name="Apartments", slug="apartments", is_active=True, display_order=1)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(db_session, owner_id: int, category_id: int, status: ListingStatus) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title="Test listing",
        description="Test listing description long enough",
        price=Decimal("100000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 1",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=status,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def test_owner_archive_and_restore_happy_path(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    archive_response = client.delete(f"/api/v1/listings/{listing.id}")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == ListingStatus.ARCHIVED.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.ARCHIVED

    restore_response = client.post(f"/api/v1/listings/{listing.id}/restore")
    assert restore_response.status_code == 200
    assert restore_response.json()["status"] == ListingStatus.PENDING_REVIEW.value

    db_session.refresh(listing)
    assert listing.status == ListingStatus.PENDING_REVIEW


def test_archive_listing_denies_non_owner_non_admin(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner2@example.com", [owner_role])
    stranger = create_user(db_session, "stranger@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(stranger)

    response = client.delete(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 403
    assert response.json()["detail"] == "Not enough permissions"


def test_archive_listing_allows_admin_for_foreign_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    admin_role = create_role(db_session, "admin")
    owner = create_user(db_session, "owner3@example.com", [owner_role])
    admin = create_user(db_session, "admin@example.com", [admin_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(admin)

    response = client.delete(f"/api/v1/listings/{listing.id}")
    assert response.status_code == 200
    assert response.json()["status"] == ListingStatus.ARCHIVED.value


def test_restore_fails_for_non_archived_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner4@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    response = client.post(f"/api/v1/listings/{listing.id}/restore")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only archived listings can be restored"


def test_status_action_invalid_transition_returns_400(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner5@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.ARCHIVED)

    set_current_user(owner)

    response = client.patch(f"/api/v1/listings/{listing.id}/status", json={"action": "activate"})
    assert response.status_code == 400
    assert "is not allowed" in response.json()["detail"]


def test_hard_delete_fails_for_non_archived_listing(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner6@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.PUBLISHED)

    set_current_user(owner)

    response = client.delete(f"/api/v1/listings/{listing.id}/hard")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only archived listings can be permanently deleted"


def test_hard_delete_archived_listing_removes_row(client, db_session, set_current_user):
    owner_role = create_role(db_session, "user")
    owner = create_user(db_session, "owner7@example.com", [owner_role])
    category = create_category(db_session)
    listing = create_listing(db_session, owner.id, category.id, ListingStatus.ARCHIVED)

    set_current_user(owner)

    response = client.delete(f"/api/v1/listings/{listing.id}/hard")
    assert response.status_code == 204

    deleted_listing = db_session.scalar(select(Listing).where(Listing.id == listing.id))
    assert deleted_listing is None
