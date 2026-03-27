from dataclasses import dataclass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.role import Role
from app.models.user import AccountStatus, User


@dataclass(frozen=True)
class DemoUserSpec:
    full_name: str
    email: str
    password: str
    preferred_language: str
    roles: tuple[str, ...]


DEMO_USERS: tuple[DemoUserSpec, ...] = (
    DemoUserSpec(
        full_name="Demo Admin",
        email="admin@demo.kg",
        password="Admin12345!",
        preferred_language="en",
        roles=("admin",),
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


if __name__ == "__main__":
    seed_demo_users()
