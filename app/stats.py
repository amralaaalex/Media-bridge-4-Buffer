"""Aggregate, anonymous numbers about the lifecycle, for the public /stats page.

Everything here is computed across all users and never exposes who uploaded what.
"""

from datetime import datetime, timedelta
from statistics import median

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import CleanupEvent, FileState, MediaFile, utcnow

REMOVED = (FileState.PURGED, FileState.EXPIRED)
# Events that stand for one status lookup of a post on Buffer.
_CHECK_REASONS = or_(
    CleanupEvent.reason.like("status_%"),
    CleanupEvent.reason.in_(("post_sent", "post_deleted")),
)


def compute(db: Session, now: datetime | None = None, days: int = 14) -> dict:
    now = now or utcnow()

    def count(*where) -> int:
        return db.scalar(select(func.count()).select_from(MediaFile).where(*where)) or 0

    uploaded = count()
    posted = count(MediaFile.buffer_post_id.is_not(None))
    held = count(MediaFile.state == FileState.HELD)
    removed = count(MediaFile.state.in_(REMOVED))
    bytes_removed = (
        db.scalar(select(func.sum(MediaFile.size_bytes)).where(MediaFile.state.in_(REMOVED))) or 0
    )
    checks = db.scalar(select(func.count()).select_from(CleanupEvent).where(_CHECK_REASONS)) or 0

    # How soon after its post went out each published file was deleted.
    sent = db.execute(
        select(MediaFile.due_at, MediaFile.purged_at)
        .join(CleanupEvent, CleanupEvent.media_file_id == MediaFile.id)
        .where(CleanupEvent.reason == "post_sent")
    ).all()
    delays = [(p - d).total_seconds() / 60 for d, p in sent if d and p and p >= d]

    start = (now - timedelta(days=days - 1)).date()
    per_day = {start + timedelta(days=i): 0 for i in range(days)}
    for (created,) in db.execute(
        select(MediaFile.created_at).where(
            MediaFile.created_at >= datetime.combine(start, datetime.min.time(), now.tzinfo)
        )
    ):
        per_day[created.date()] = per_day.get(created.date(), 0) + 1

    return {
        "uploaded": uploaded,
        "posted": posted,
        "held_now": held,
        "published_then_deleted": len(sent),
        "removed": removed,
        "bytes_removed": int(bytes_removed),
        "median_minutes_to_delete": round(median(delays), 1) if delays else None,
        "status_checks_per_post": round(checks / posted, 2) if posted else None,
        "daily_uploads": [{"date": d.isoformat(), "count": n} for d, n in per_day.items()],
        "generated_at": now.isoformat(timespec="seconds"),
    }
