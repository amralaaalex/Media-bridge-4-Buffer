"""Per-user API keys for agents. The key is shown once; only its SHA-256 is stored."""

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import AgentKey, User, utcnow

PREFIX = "mb_"


def _hash(key: str) -> str:
    # Keys are 256-bit random, so a plain (unsalted) hash is enough to make a DB leak useless.
    return hashlib.sha256(key.encode()).hexdigest()


def create(db: Session, user: User) -> tuple[AgentKey, str]:
    key = PREFIX + secrets.token_urlsafe(32)
    row = AgentKey(user_id=user.id, key_hash=_hash(key), prefix=key[: len(PREFIX) + 6])
    db.add(row)
    db.commit()
    return row, key


def authenticate(db: Session, key: str) -> User | None:
    """The key's user, or None if the key is unknown or revoked. Records last use."""
    if not key.startswith(PREFIX):
        return None
    row = db.execute(select(AgentKey).where(AgentKey.key_hash == _hash(key))).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    row.last_used_at = utcnow()
    db.commit()
    return db.get(User, row.user_id)


def list_for(db: Session, user: User) -> list[AgentKey]:
    return list(
        db.execute(
            select(AgentKey)
            .where(AgentKey.user_id == user.id, AgentKey.revoked_at.is_(None))
            .order_by(AgentKey.created_at.desc())
        ).scalars()
    )


def revoke(db: Session, user: User, key_id: int) -> bool:
    row = db.get(AgentKey, key_id)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return False
    row.revoked_at = utcnow()
    db.commit()
    return True
