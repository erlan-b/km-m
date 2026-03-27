from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.listing import Listing
from app.models.promotion import Promotion, PromotionStatus


def expire_premium_promotions(db: Session, now: datetime | None = None) -> dict[str, int]:
    run_at = now or datetime.now(timezone.utc).replace(tzinfo=None)

    checked = db.scalar(
        select(func.count())
        .select_from(Promotion)
        .where(Promotion.status == PromotionStatus.ACTIVE)
    ) or 0

    to_expire = db.scalars(
        select(Promotion).where(
            Promotion.status == PromotionStatus.ACTIVE,
            Promotion.ends_at <= run_at,
        )
    ).all()

    listing_ids = set[int]()
    for promotion in to_expire:
        promotion.status = PromotionStatus.EXPIRED
        listing_ids.add(promotion.listing_id)
        db.add(promotion)

    updated_listings = 0
    for listing_id in listing_ids:
        active_count = db.scalar(
            select(func.count())
            .select_from(Promotion)
            .where(
                Promotion.listing_id == listing_id,
                Promotion.status == PromotionStatus.ACTIVE,
                Promotion.ends_at > run_at,
            )
        ) or 0

        if active_count == 0:
            listing = db.scalar(select(Listing).where(Listing.id == listing_id))
            if listing is not None:
                if listing.is_premium:
                    updated_listings += 1
                listing.is_premium = False
                if listing.premium_expires_at is not None and listing.premium_expires_at <= run_at:
                    listing.premium_expires_at = None
                db.add(listing)

    db.commit()

    return {
        "checked_promotions": checked,
        "expired_promotions": len(to_expire),
        "updated_listings": updated_listings,
    }
