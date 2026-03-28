from datetime import datetime, timezone


def utc_now() -> datetime:
    """Timezone-naive UTC timestamp for MySQL storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
