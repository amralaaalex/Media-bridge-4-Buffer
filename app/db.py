from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    buffer_account_id: Mapped[str] = mapped_column(String(64), unique=True)
    buffer_org_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # Set when Buffer rejects our refresh token or returns 401; cleared on re-login.
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    # SQLite (local dev only) needs this to be used from FastAPI's threadpool.
    connect_args={"check_same_thread": False}
    if _settings.database_url.startswith("sqlite")
    else {},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
