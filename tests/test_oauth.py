import base64
import hashlib
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app import oauth
from app.crypto import decrypt
from app.db import OAuthToken, SessionLocal, User, init_db, utcnow


@pytest.fixture
def db():
    init_db()
    with SessionLocal() as session:
        yield session


def make_user(db, *, expires_in: timedelta, refresh: str | None = "rt-1") -> User:
    user = User(buffer_account_id=f"acct-{utcnow().timestamp()}")
    db.add(user)
    db.flush()
    oauth.store_tokens(db, user, {"access_token": "at-1", "refresh_token": refresh})
    db.get(OAuthToken, user.id).expires_at = utcnow() + expires_in
    db.commit()
    return user


def token_server(responses: list[httpx.Response], seen: list[dict]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({k: v[0] for k, v in parse_qs(request.content.decode()).items()})
        return responses.pop(0)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_pkce_challenge_is_s256_of_verifier():
    verifier, challenge = oauth.new_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=")
    assert challenge == expected.decode()
    assert "=" not in verifier and len(verifier) >= 43


def test_authorize_url_has_pkce_and_offline_access():
    q = parse_qs(urlparse(oauth.authorize_url("st", "ch")).query)
    assert q["code_challenge_method"] == ["S256"]
    assert q["code_challenge"] == ["ch"] and q["state"] == ["st"]
    assert "offline_access" in q["scope"][0].split()


def test_valid_token_is_returned_without_refresh(db):
    user = make_user(db, expires_in=timedelta(minutes=30))
    seen: list[dict] = []
    with token_server([], seen) as http:
        assert oauth.get_access_token(db, user, http) == "at-1"
    assert seen == []


def test_expired_token_rotates_and_persists_new_refresh_token(db):
    user = make_user(db, expires_in=timedelta(seconds=-1))
    seen: list[dict] = []
    ok = httpx.Response(
        200, json={"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600}
    )
    with token_server([ok], seen) as http:
        assert oauth.get_access_token(db, user, http) == "at-2"
    assert seen[0]["grant_type"] == "refresh_token" and seen[0]["refresh_token"] == "rt-1"
    tok = db.get(OAuthToken, user.id)
    assert decrypt(tok.refresh_token_enc) == "rt-2"


def test_failed_refresh_disconnects_and_is_not_retried(db):
    user = make_user(db, expires_in=timedelta(seconds=-1))
    seen: list[dict] = []
    bad = httpx.Response(400, json={"error": "invalid_grant"})
    with token_server([bad], seen) as http:
        with pytest.raises(oauth.ReauthRequired):
            oauth.get_access_token(db, user, http)
        with pytest.raises(oauth.ReauthRequired):
            oauth.get_access_token(db, user, http)
    assert len(seen) == 1
    assert user.disconnected_at is not None
