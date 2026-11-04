"""File lifecycle operations shared by the web routes, the cleanup job and scripts.

UPLOADED --post_file--> HELD --(cleanup: sent / deleted in Buffer)--> PURGED
    |                     |---(ttl passed)--> EXPIRED
    |                     '---(user: delete now)--> PURGED
    '---(never posted within unattached_ttl_hours)--> EXPIRED
"""

import logging
from datetime import datetime, timedelta

import httpx
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app import buffer_client, oauth, storage
from app.config import get_settings
from app.db import CleanupEvent, FileState, MediaFile, User, utcnow

log = logging.getLogger(__name__)

# Statuses after which Buffer no longer needs the file.
DONE_STATUSES = {"sent"}


class UploadRejected(ValueError):
    pass


class PostFailed(Exception):
    """Buffer didn't create the post; the message is safe to show the user."""


def sniff_content_type(data: bytes) -> str | None:
    """Identify the image type from its bytes; the client's Content-Type isn't trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def upload_file(db: Session, user: User, data: bytes) -> MediaFile:
    s = get_settings()
    if not data:
        raise UploadRejected("The file is empty.")
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise UploadRejected(f"The file is larger than {s.max_upload_mb} MB.")
    content_type = sniff_content_type(data)
    if content_type is None:
        raise UploadRejected("Only JPEG, PNG, GIF and WebP images are supported.")

    key, url = storage.upload(data, content_type)
    expires = utcnow() + timedelta(hours=s.unattached_ttl_hours)
    media = MediaFile(
        user_id=user.id,
        object_key=key,
        public_url=url,
        content_type=content_type,
        size_bytes=len(data),
        state=FileState.UPLOADED,
        ttl_expires_at=expires,
        next_check_at=expires,
    )
    db.add(media)
    db.commit()
    return media


def next_check_for(status: str | None, due_at: datetime | None, now: datetime) -> datetime:
    """When to ask Buffer about a HELD file's post again. Never earlier than needed."""
    if status == "scheduled" and due_at and due_at > now:
        return due_at + timedelta(minutes=2)
    if status in ("scheduled", "sending"):  # due but not sent yet: publishing is underway
        return now + timedelta(minutes=10)
    if status == "error":  # the user may fix the channel and retry from Buffer
        return now + timedelta(hours=6)
    # draft / needs_approval / unknown: nothing will happen until a person acts
    return now + timedelta(hours=24)


def parse_buffer_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def post_file(
    db: Session,
    http: httpx.Client,
    user: User,
    media: MediaFile,
    *,
    channel_id: str,
    text: str,
    mode: str,
    alt_text: str | None = None,
    due_at: datetime | None = None,
) -> MediaFile:
    """Create the Buffer post for an UPLOADED file and start holding the file for it."""
    if media.state != FileState.UPLOADED:
        raise PostFailed("This file is already attached to a post or was deleted.")
    now = utcnow()
    if mode == "schedule" and (due_at is None or due_at <= now):
        raise PostFailed("Pick a time in the future.")

    token = oauth.get_access_token(db, user, http)
    try:
        post = buffer_client.create_post(
            http,
            token,
            channel_id=channel_id,
            text=text,
            image_url=media.public_url,
            mode=mode,
            alt_text=alt_text,
            due_at=due_at.isoformat().replace("+00:00", "Z") if due_at else None,
        )
    except buffer_client.BufferPostRejected as exc:
        raise PostFailed(str(exc)) from exc
    except buffer_client.BufferUnauthorized as exc:
        oauth.mark_disconnected(db, user)
        raise oauth.ReauthRequired(str(exc)) from exc
    except httpx.TimeoutException as exc:
        # The post may exist anyway (no idempotency key), so keep the file long enough
        # not to break it, and don't retry.
        media.ttl_expires_at = media.next_check_at = now + timedelta(
            days=get_settings().media_ttl_days
        )
        db.commit()
        raise PostFailed(
            "Buffer didn't answer in time. Check your Buffer queue before trying again."
        ) from exc

    status = post.get("status")
    post_due = parse_buffer_time(post.get("dueAt"))
    ttl = now + timedelta(days=get_settings().media_ttl_days)
    if post_due and post_due + timedelta(days=7) > ttl:
        ttl = post_due + timedelta(days=7)  # scheduled far out: hold past the publish date

    media.state = FileState.HELD
    media.buffer_post_id = post["id"]
    media.channel_id = channel_id
    media.due_at = post_due
    media.last_post_status = status
    media.ttl_expires_at = ttl
    media.next_check_at = now if status in DONE_STATUSES else next_check_for(status, post_due, now)
    db.add(
        CleanupEvent(
            media_file_id=media.id, decision="keep", reason="post_created", post_status=status
        )
    )
    db.commit()
    return media


def remove_file(
    db: Session,
    media: MediaFile,
    *,
    state: FileState,
    decision: str,
    reason: str,
    post_status: str | None = None,
) -> None:
    """Delete the object from R2 and record why. Commits."""
    try:
        storage.delete(media.object_key)
    except (BotoCoreError, ClientError) as exc:
        # Leave the row as is so the next pass retries the delete.
        log.warning("R2 delete failed for %s: %s", media.object_key, exc)
        raise
    media.state = state
    media.purged_at = utcnow()
    media.next_check_at = None
    if post_status:
        media.last_post_status = post_status
    db.add(
        CleanupEvent(
            media_file_id=media.id, decision=decision, reason=reason, post_status=post_status
        )
    )
    db.commit()


def post_still_needs_file(media: MediaFile) -> bool:
    return media.state == FileState.HELD and media.last_post_status not in DONE_STATUSES
