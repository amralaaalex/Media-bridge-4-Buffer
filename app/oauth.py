"""Buffer OAuth: Authorization Code + PKCE (S256), with single-use rotating refresh tokens.

Rotation rule: a refresh token works exactly once, and replaying a spent one revokes the
user's whole grant. So refreshing happens only in `get_access_token`, under a row lock,
the new tokens are committed before they are used, and a failed refresh is never retried.
"""

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BUFFER_AUTH_URL, BUFFER_TOKEN_URL, get_settings
from app.crypto import decrypt, encrypt
from app.db import OAuthToken, User, utcnow

# Refresh this long before Buffer's stated expiry.
EXPIRY_MARGIN = timedelta(minutes=2)


class OAuthError(Exception):
    pass


class ReauthRequired(OAuthError):
    """The user's grant is gone (revoked, or refresh failed); they must log in again."""


def new_pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def authorize_url(state: str, code_challenge: str) -> str:
    s = get_settings()
    params = {
        "client_id": s.buffer_client_id,
        "redirect_uri": s.buffer_redirect_uri,
        "response_type": "code",
        "scope": s.buffer_scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "consent",
    }
    return f"{BUFFER_AUTH_URL}?{urlencode(params)}"


def _token_request(data: dict[str, str], http: httpx.Client) -> dict:
    s = get_settings()
    data = {**data, "client_id": s.buffer_client_id, "client_secret": s.buffer_client_secret}
    resp = http.post(BUFFER_TOKEN_URL, data=data, timeout=20)
    body = (
        resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    )
    if resp.status_code != 200 or "access_token" not in body:
        # Never include the request data here: it contains the secret and tokens.
        raise OAuthError(f"token endpoint {resp.status_code}: {body.get('error', 'unknown_error')}")
    return body


def exchange_code(code: str, code_verifier: str, http: httpx.Client) -> dict:
    return _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_settings().buffer_redirect_uri,
            "code_verifier": code_verifier,
        },
        http,
    )


def store_tokens(db: Session, user: User, token_response: dict) -> OAuthToken:
    expires_at = utcnow() + timedelta(seconds=int(token_response.get("expires_in", 3600)))
    tok = db.get(OAuthToken, user.id)
    if tok is None:
        tok = OAuthToken(user_id=user.id)
        db.add(tok)
    tok.access_token_enc = encrypt(token_response["access_token"])
    if token_response.get("refresh_token"):
        tok.refresh_token_enc = encrypt(token_response["refresh_token"])
    tok.expires_at = expires_at
    return tok


def _as_aware(dt: datetime) -> datetime:
    # SQLite drops tzinfo; values are always written as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def get_access_token(db: Session, user: User, http: httpx.Client) -> str:
    """Return a valid access token, refreshing (and rotating) it if needed. Commits."""
    tok = db.get(OAuthToken, user.id)
    if tok is None or user.disconnected_at is not None:
        raise ReauthRequired("no stored grant")
    if _as_aware(tok.expires_at) - EXPIRY_MARGIN > utcnow():
        return decrypt(tok.access_token_enc)

    # Lock the row, then re-check: another worker may have refreshed while we waited.
    tok = db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user.id).with_for_update()
    ).scalar_one()
    db.refresh(tok)
    if _as_aware(tok.expires_at) - EXPIRY_MARGIN > utcnow():
        db.commit()
        return decrypt(tok.access_token_enc)

    if not tok.refresh_token_enc:
        mark_disconnected(db, user)
        raise ReauthRequired("access token expired and no refresh token was issued")

    try:
        body = _token_request(
            {"grant_type": "refresh_token", "refresh_token": decrypt(tok.refresh_token_enc)}, http
        )
    except (OAuthError, httpx.HTTPError) as exc:
        # The old refresh token may already be spent; retrying it could revoke the grant.
        mark_disconnected(db, user)
        raise ReauthRequired(f"refresh failed: {exc}") from exc

    store_tokens(db, user, body)
    db.commit()
    return body["access_token"]


def mark_disconnected(db: Session, user: User) -> None:
    user.disconnected_at = utcnow()
    db.commit()
