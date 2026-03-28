from datetime import datetime

from app.models.category import Category
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


def create_category(
    db_session,
    *,
    name: str,
    slug: str,
    display_order: int,
    created_at: datetime,
    is_active: bool = True,
) -> Category:
    category = Category(
        name=name,
        slug=slug,
        is_active=is_active,
        display_order=display_order,
        created_at=created_at,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def test_public_categories_sorted_by_display_order_then_created_at(client, db_session):
    highest_priority = create_category(
        db_session,
        name="Priority One",
        slug="priority-one",
        display_order=10,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )
    second_same_priority = create_category(
        db_session,
        name="Priority Two",
        slug="priority-two",
        display_order=10,
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    lower_priority = create_category(
        db_session,
        name="Priority Three",
        slug="priority-three",
        display_order=20,
        created_at=datetime(2026, 1, 1, 8, 0, 0),
    )

    response = client.get("/api/v1/categories")
    assert response.status_code == 200

    ordered_ids = [item["id"] for item in response.json()["items"]]
    assert ordered_ids == [highest_priority.id, second_same_priority.id, lower_priority.id]


def test_admin_can_create_and_update_display_order(client, db_session, set_current_user):
    admin_role = create_role(db_session, "admin")
    admin_user = create_user(db_session, "admin-categories@example.com", [admin_role])
    set_current_user(admin_user)

    first_create_response = client.post(
        "/api/v1/categories",
        json={
            "name": "Laptops",
            "slug": "laptops",
            "is_active": True,
            "display_order": 20,
            "attributes_schema": [],
        },
    )
    assert first_create_response.status_code == 201
    first_payload = first_create_response.json()
    assert first_payload["display_order"] == 20

    second_create_response = client.post(
        "/api/v1/categories",
        json={
            "name": "Phones",
            "slug": "phones",
            "is_active": True,
            "display_order": 10,
            "attributes_schema": [],
        },
    )
    assert second_create_response.status_code == 201

    update_response = client.patch(
        f"/api/v1/categories/{first_payload['id']}",
        json={"display_order": 5},
    )
    assert update_response.status_code == 200
    assert update_response.json()["display_order"] == 5

    list_response = client.get("/api/v1/categories/admin")
    assert list_response.status_code == 200

    ordered_ids = [item["id"] for item in list_response.json()["items"]]
    assert ordered_ids[:2] == [first_payload["id"], second_create_response.json()["id"]]


def test_category_display_order_rejects_negative_value(client, db_session, set_current_user):
    moderator_role = create_role(db_session, "moderator")
    moderator_user = create_user(db_session, "moderator-categories@example.com", [moderator_role])
    set_current_user(moderator_user)

    create_response = client.post(
        "/api/v1/categories",
        json={
            "name": "Invalid Order",
            "slug": "invalid-order",
            "is_active": True,
            "display_order": -1,
            "attributes_schema": [],
        },
    )
    assert create_response.status_code == 422
