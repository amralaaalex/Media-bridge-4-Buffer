import enum
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    TypeDecorator,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo on read)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    buffer_account_id: Mapped[str] = mapped_column(String(64), unique=True)
    buffer_org_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Set when Buffer rejects our refresh token or returns 401; cleared on re-login.
    disconnected_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class FileState(enum.StrEnum):
    UPLOADED = "UPLOADED"  # stored, not attached to a Buffer post yet
    HELD = "HELD"  # attached to a post that hasn't been sent
    PURGED = "PURGED"  # deleted: post sent, post deleted in Buffer, or user's "delete now"
    EXPIRED = "EXPIRED"  # deleted because ttl_expires_at passed


class MediaFile(Base):
    __tablename__ = "media_files"
    __table_args__ = (Index("ix_media_files_state_next_check", "state", "next_check_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(64))
    public_url: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(32))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[FileState] = mapped_column(
        Enum(FileState, native_enum=False, length=16), default=FileState.UPLOADED
    )
    buffer_post_id: Mapped[str | None] = mapped_column(String(64))
    channel_id: Mapped[str | None] = mapped_column(String(64))
    due_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_post_status: Mapped[str | None] = mapped_column(String(32))
    # When the cleanup job should next look at this file. Null once it's gone.
    next_check_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ttl_expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    purged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class CleanupEvent(Base):
    """Audit trail of every lifecycle decision; also feeds the stats page."""

    __tablename__ = "cleanup_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_file_id: Mapped[str] = mapped_column(ForeignKey("media_files.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))  # keep | purge | expire | fail
    reason: Mapped[str] = mapped_column(String(64))
    post_status: Mapped[str | None] = mapped_column(String(32))
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


_settings = get_settings()
_is_sqlite = _settings.database_url.startswith("sqlite")
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    # SQLite (local dev only) needs this to be used from FastAPI's threadpool.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    # Neon's free plan has 100 CU-hours/month and suspends after 5 idle minutes. Holding
    # idle pooled connections may keep it awake, so open one per unit of work instead.
    **({} if _is_sqlite else {"poolclass": NullPool}),
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
