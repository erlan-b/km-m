from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.category import Category

DEFAULT_CATEGORIES = [
    {"name": "Apartments", "slug": "apartments"},
    {"name": "Houses", "slug": "houses"},
    {"name": "Commercial", "slug": "commercial"},
    {"name": "Land", "slug": "land"},
    {"name": "Rooms", "slug": "rooms"},
]


def seed_categories() -> None:
    with SessionLocal() as db:
        for item in DEFAULT_CATEGORIES:
            existing = db.scalar(select(Category).where(Category.slug == item["slug"]))
            if existing is None:
                db.add(Category(**item, is_active=True))

        db.commit()


if __name__ == "__main__":
    seed_categories()
    print("Category seed complete")
