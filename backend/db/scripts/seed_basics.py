import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.role import Role
from app.models.user import AccountStatus, User

DEFAULT_CATEGORIES = [
    {"name": "Apartments", "slug": "apartments", "display_order": 10},
    {"name": "Houses", "slug": "houses", "display_order": 20},
    {"name": "Commercial", "slug": "commercial", "display_order": 30},
    {"name": "Land", "slug": "land", "display_order": 40},
    {"name": "Rooms", "slug": "rooms", "display_order": 50},
]


@dataclass(frozen=True)
class DemoUserSpec:
    full_name: str
    email: str
    password: str
    preferred_language: str
    roles: tuple[str, ...]


DEMO_USERS: tuple[DemoUserSpec, ...] = (
    DemoUserSpec(
        full_name="Demo Superadmin",
        email="superadmin@demo.kg",
        password="Superadmin12345!",
        preferred_language="en",
        roles=("superadmin",),
    ),
    DemoUserSpec(
        full_name="Demo Admin",
        email="admin@demo.kg",
        password="Admin12345!",
        preferred_language="en",
        roles=("admin",),
    ),
    DemoUserSpec(
        full_name="Demo Support",
        email="support@demo.kg",
        password="Support12345!",
        preferred_language="ru",
        roles=("support",),
    ),
    DemoUserSpec(
        full_name="Demo Moderator",
        email="moderator@demo.kg",
        password="Moderator12345!",
        preferred_language="ru",
        roles=("moderator",),
    ),
    DemoUserSpec(
        full_name="Demo User",
        email="user@demo.kg",
        password="User12345!",
        preferred_language="ru",
        roles=("user",),
    ),
)


def seed_categories() -> None:
    with SessionLocal() as db:
        for item in DEFAULT_CATEGORIES:
            existing = db.scalar(select(Category).where(Category.slug == item["slug"]))
            if existing is None:
                db.add(Category(**item, is_active=True))
                continue

            existing.name = item["name"]
            existing.display_order = item["display_order"]
            existing.is_active = True
            db.add(existing)

        db.commit()


def get_or_create_role(db, role_name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == role_name))
    if role is not None:
        return role

    role = Role(name=role_name)
    db.add(role)
    db.flush()
    return role


def seed_demo_users() -> None:
    with SessionLocal() as db:
        for spec in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == spec.email.lower()))
            role_objects = [get_or_create_role(db, role_name) for role_name in spec.roles]

            if user is None:
                user = User(
                    full_name=spec.full_name,
                    email=spec.email.lower(),
                    password_hash=hash_password(spec.password),
                    preferred_language=spec.preferred_language,
                    account_status=AccountStatus.ACTIVE,
                    roles=role_objects,
                )
                db.add(user)
            else:
                user.full_name = spec.full_name
                user.password_hash = hash_password(spec.password)
                user.preferred_language = spec.preferred_language
                user.account_status = AccountStatus.ACTIVE
                user.roles = role_objects
                db.add(user)

        db.commit()

    print("Demo users seed complete")


def seed_all() -> None:
    seed_categories()
    print("Category seed complete")
    seed_demo_users()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed baseline demo data")
    parser.add_argument(
        "--scope",
        choices=("categories", "users", "all"),
        default="all",
        help="Select what to seed",
    )
    args = parser.parse_args()

    if args.scope == "categories":
        seed_categories()
        print("Category seed complete")
        return

    if args.scope == "users":
        seed_demo_users()
        return

    seed_all()


if __name__ == "__main__":
    main()