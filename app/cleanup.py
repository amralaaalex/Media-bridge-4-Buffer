"""Cleanup job: delete each file as soon as its post no longer needs it.

There is no fixed polling interval. Every file carries `next_check_at` (the post's due
time, or a re-check time), and the worker sleeps until the earliest one. That keeps
Buffer API calls to roughly one per post, and leaves the database idle (so Neon can
scale to zero) when nothing is due.
"""

import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import buffer_client, media, oauth
from app.db import CleanupEvent, FileState, MediaFile, SessionLocal, User, utcnow

log = logging.getLogger(__name__)

ACTIVE = (FileState.UPLOADED, FileState.HELD)
# Leave this many requests in the app client's smallest window for interactive use.
RATE_LIMIT_RESERVE = 10
# Wake at least this often even when nothing is scheduled (safety net, ~4 DB hits/day).
MAX_SLEEP = timedelta(hours=6)


def run_pass(db: Session, http: httpx.Client, now: datetime | None = None) -> datetime | None:
    """Process every file that is due. Returns when the next pass is needed (None: nothing)."""
    now = now or utcnow()
    _expire(db, now)
    backoff_until = _check_held_posts(db, http, now)
    if backoff_until is not None:
        # Due files are still due; waking at their (past) time would spin. Wait it out.
        return backoff_until
    return db.execute(
        select(func.min(MediaFile.next_check_at)).where(MediaFile.state.in_(ACTIVE))
    ).scalar()


def _expire(db: Session, now: datetime) -> None:
    expired = (
        db.execute(
            select(MediaFile).where(MediaFile.state.in_(ACTIVE), MediaFile.ttl_expires_at <= now)
        )
        .scalars()
        .all()
    )
    for f in expired:
        reason = "never_posted" if f.state == FileState.UPLOADED else "ttl"
        try:
            media.remove_file(db, f, state=FileState.EXPIRED, decision="expire", reason=reason)
        except (BotoCoreError, ClientError):
            db.rollback()
            f.next_check_at = now + timedelta(minutes=15)
            db.commit()


def _check_held_posts(db: Session, http: httpx.Client, now: datetime) -> datetime | None:
    """Ask Buffer about due HELD files. Returns a wake time if we had to back off."""
    due = (
        db.execute(
            select(MediaFile)
            .where(MediaFile.state == FileState.HELD, MediaFile.next_check_at <= now)
            .order_by(MediaFile.next_check_at)
        )
        .scalars()
        .all()
    )
    if not due:
        return None

    remaining = buffer_client.rate_limits.min_remaining
    if remaining is not None and remaining <= RATE_LIMIT_RESERVE:
        log.info("Rate limit low (%s left); deferring %d checks", remaining, len(due))
        return now + timedelta(minutes=15)

    by_user: dict[int, list[MediaFile]] = defaultdict(list)
    for f in due:
        by_user[f.user_id].append(f)

    for user_id, files in by_user.items():
        user = db.get(User, user_id)
        try:
            token = oauth.get_access_token(db, user, http)
        except oauth.ReauthRequired:
            # Can't see this user's posts until they log in again; the TTL still applies.
            for f in files:
                f.next_check_at = now + timedelta(hours=24)
            db.commit()
            continue

        for start in range(0, len(files), buffer_client.MAX_POSTS_PER_QUERY):
            batch = files[start : start + buffer_client.MAX_POSTS_PER_QUERY]
            try:
                posts = buffer_client.get_posts(http, token, [f.buffer_post_id for f in batch])
            except buffer_client.BufferRateLimited as exc:
                return now + timedelta(seconds=exc.retry_after)
            except buffer_client.BufferUnauthorized:
                oauth.mark_disconnected(db, user)
                break
            except (buffer_client.BufferError, httpx.HTTPError) as exc:
                log.warning("Post status check failed for user %s: %s", user_id, exc)
                for f in batch:
                    f.next_check_at = now + timedelta(minutes=15)
                db.commit()
                continue
            for f in batch:
                _apply(db, f, posts, now)
    return None


_UNKNOWN = object()


def _apply(db: Session, f: MediaFile, posts: dict, now: datetime) -> None:
    post = posts.get(f.buffer_post_id, _UNKNOWN)
    f.last_checked_at = now
    try:
        if post is None:
            media.remove_file(
                db, f, state=FileState.PURGED, decision="purge", reason="post_deleted"
            )
            return
        if post is _UNKNOWN:
            f.next_check_at = now + timedelta(minutes=15)
        elif post["status"] in media.DONE_STATUSES:
            media.remove_file(
                db,
                f,
                state=FileState.PURGED,
                decision="purge",
                reason="post_sent",
                post_status=post["status"],
            )
            return
        else:
            f.last_post_status = post["status"]
            f.due_at = media.parse_buffer_time(post.get("dueAt"))
            f.next_check_at = media.next_check_for(f.last_post_status, f.due_at, now)
            db.add(
                CleanupEvent(
                    media_file_id=f.id,
                    decision="keep",
                    reason=f"status_{f.last_post_status}",
                    post_status=f.last_post_status,
                )
            )
    except Exception:
        log.exception("Cleanup failed for file %s", f.id)
        db.rollback()
        f.next_check_at = now + timedelta(minutes=15)
    db.commit()


class CleanupWorker:
    """Background thread that sleeps until the next file is due. `poke()` wakes it early."""

    def __init__(self, http: httpx.Client):
        self._http = http
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="cleanup", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=10)

    def poke(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            try:
                with SessionLocal() as db:
                    next_at = run_pass(db, self._http)
            except Exception:
                log.exception("Cleanup pass failed")
                next_at = utcnow() + timedelta(minutes=5)
            now = utcnow()
            sleep_until = min(next_at, now + MAX_SLEEP) if next_at else now + MAX_SLEEP
            self._wake.wait(max(1.0, (sleep_until - now).total_seconds()))
