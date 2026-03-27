from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.category import Category

DEFAULT_CATEGORIES = [
    {"name": "Apartments", "slug": "apartments", "display_order": 10},
    {"name": "Houses", "slug": "houses", "display_order": 20},
    {"name": "Commercial", "slug": "commercial", "display_order": 30},
    {"name": "Land", "slug": "land", "display_order": 40},
    {"name": "Rooms", "slug": "rooms", "display_order": 50},
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
