from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from sqlalchemy import select

from app.models.category import Category
from app.models.listing import Listing, ListingStatus, TransactionType
from app.models.listing_media import ListingMedia
from app.models.role import Role
from app.models.user import AccountStatus, SellerType, User
from app.services.listing_media_image_service import get_thumbnail_path


def create_role(db_session, name: str) -> Role:
    role = Role(name=name)
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)
    return role


def create_user(
    db_session,
    *,
    email: str,
    roles: list[Role],
    seller_type: SellerType = SellerType.OWNER,
) -> User:
    user = User(
        full_name=email.split("@")[0],
        email=email,
        password_hash="test-hash",
        preferred_language="ru",
        account_status=AccountStatus.ACTIVE,
        roles=roles,
        seller_type=seller_type,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_category(db_session) -> Category:
    category = Category(name="Recommended Features", slug="recommended-features", is_active=True)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def create_listing(
    db_session,
    *,
    owner_id: int,
    category_id: int,
    title: str,
    view_count: int,
    is_subscription: bool,
    status: ListingStatus = ListingStatus.PUBLISHED,
) -> Listing:
    listing = Listing(
        owner_id=owner_id,
        category_id=category_id,
        transaction_type=TransactionType.SALE,
        title=title,
        description=f"{title} description with enough length",
        price=Decimal("123000.00"),
        currency="KGS",
        city="Bishkek",
        address_line="Street 1",
        latitude=Decimal("42.8746"),
        longitude=Decimal("74.5698"),
        map_address_label="Bishkek",
        status=status,
        view_count=view_count,
        is_subscription=is_subscription,
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


def make_jpeg_bytes(width: int = 2600, height: int = 1600) -> bytes:
    image = Image.new("RGB", (width, height), color=(120, 40, 30))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=98)
    return buffer.getvalue()


def test_public_listings_support_most_viewed_promoted_and_seller_type_filters(client, db_session):
    user_role = create_role(db_session, "user")
    owner_user = create_user(db_session, email="owner-filter@example.com", roles=[user_role], seller_type=SellerType.OWNER)
    company_user = create_user(db_session, email="company-filter@example.com", roles=[user_role], seller_type=SellerType.COMPANY)

    category = create_category(db_session)

    least_viewed = create_listing(
        db_session,
        owner_id=owner_user.id,
        category_id=category.id,
        title="Least Viewed",
        view_count=3,
        is_subscription=False,
    )
    middle_viewed = create_listing(
        db_session,
        owner_id=owner_user.id,
        category_id=category.id,
        title="Middle Viewed",
        view_count=15,
        is_subscription=False,
    )
    most_viewed = create_listing(
        db_session,
        owner_id=company_user.id,
        category_id=category.id,
        title="Most Viewed",
        view_count=99,
        is_subscription=True,
    )

    sort_response = client.get("/api/v1/listings", params={"sort_by": "most_viewed"})
    assert sort_response.status_code == 200
    sorted_ids = [item["id"] for item in sort_response.json()["items"]]
    assert sorted_ids[:3] == [most_viewed.id, middle_viewed.id, least_viewed.id]

    promoted_response = client.get("/api/v1/listings", params={"promoted_only": "true"})
    assert promoted_response.status_code == 200
    promoted_ids = [item["id"] for item in promoted_response.json()["items"]]
    assert promoted_ids == [most_viewed.id]

    company_response = client.get("/api/v1/listings", params={"seller_type": "company"})
    assert company_response.status_code == 200
    company_ids = [item["id"] for item in company_response.json()["items"]]
    assert company_ids == [most_viewed.id]


def test_listing_media_upload_creates_optimized_image_and_thumbnail(
    client,
    db_session,
    set_current_user,
    monkeypatch,
    tmp_path,
):
    user_role = create_role(db_session, "user")
    owner = create_user(db_session, email="owner-media@example.com", roles=[user_role])
    category = create_category(db_session)

    listing = create_listing(
        db_session,
        owner_id=owner.id,
        category_id=category.id,
        title="Media Listing",
        view_count=0,
        is_subscription=False,
        status=ListingStatus.PUBLISHED,
    )

    media_settings = SimpleNamespace(
        media_root=str(tmp_path),
        listing_media_max_files_per_listing=20,
        listing_media_subdir="listing_media",
        listing_media_max_size_mb=10,
        listing_media_allowed_mime_types=["image/jpeg", "image/png", "image/webp"],
    )
    monkeypatch.setattr("app.api.v1.endpoints.listing_media.get_settings", lambda: media_settings)

    set_current_user(owner)

    upload_response = client.post(
        f"/api/v1/listing-media/listings/{listing.id}/upload",
        files=[("files", ("photo.jpg", make_jpeg_bytes(), "image/jpeg"))],
    )
    assert upload_response.status_code == 201

    payload = upload_response.json()
    assert len(payload["items"]) == 1
    media_item = payload["items"][0]
    assert media_item["thumbnail_url"] is not None

    media = db_session.scalar(select(ListingMedia).where(ListingMedia.id == media_item["id"]))
    assert media is not None

    absolute_media_path = (Path(tmp_path) / media.file_path).resolve()
    thumbnail_path = get_thumbnail_path(absolute_media_path)

    assert absolute_media_path.exists()
    assert thumbnail_path.exists()

    with Image.open(absolute_media_path) as optimized:
        assert optimized.width <= 1920
        assert optimized.height <= 1920

    with Image.open(thumbnail_path) as thumb:
        assert thumb.width <= 480
        assert thumb.height <= 480

    thumbnail_response = client.get(f"/api/v1/listing-media/{media.id}/thumbnail/my")
    assert thumbnail_response.status_code == 200
    assert thumbnail_response.headers["content-type"].startswith("image/webp")

    delete_response = client.delete(f"/api/v1/listing-media/{media.id}")
    assert delete_response.status_code == 204
    assert not absolute_media_path.exists()
    assert not thumbnail_path.exists()
