"""Thin client for Buffer's GraphQL API (https://api.buffer.com).

The app client's quota is shared by every user (about 250 requests a day), so this
records the rate-limit headers from every response and fails fast instead of retrying.
"""

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.config import BUFFER_API_URL

log = logging.getLogger(__name__)

_POLICY_RE = re.compile(r'"[^"]*"\s*;\s*r=(\d+)\s*;\s*t=(\d+)')


class BufferError(Exception):
    pass


class BufferUnauthorized(BufferError):
    pass


class BufferRateLimited(BufferError):
    def __init__(self, retry_after: int):
        super().__init__(f"Buffer rate limit reached; retry in {retry_after}s")
        self.retry_after = retry_after


@dataclass
class RateLimitState:
    """Remaining requests per window, from the last response's `RateLimit` header."""

    windows: list[tuple[int, int]] = field(default_factory=list)  # (remaining, reset_seconds)

    def update(self, header: str | None) -> None:
        if header:
            self.windows = [(int(r), int(t)) for r, t in _POLICY_RE.findall(header)]

    @property
    def min_remaining(self) -> int | None:
        return min((r for r, _ in self.windows), default=None)


rate_limits = RateLimitState()


def graphql(
    http: httpx.Client, access_token: str, query: str, variables: dict | None = None
) -> dict:
    resp = http.post(
        BUFFER_API_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    rate_limits.update(resp.headers.get("ratelimit"))

    if resp.status_code == 429:
        raise BufferRateLimited(int(resp.headers.get("retry-after", "60")))
    if resp.status_code == 401:
        raise BufferUnauthorized("Buffer rejected the access token")
    resp.raise_for_status()

    body = resp.json()
    errors = body.get("errors") or []
    codes = {(e.get("extensions") or {}).get("code") for e in errors}
    if "UNAUTHORIZED" in codes:
        raise BufferUnauthorized(errors[0].get("message", "unauthorized"))
    if "RATE_LIMIT_EXCEEDED" in codes:
        raise BufferRateLimited(int(resp.headers.get("retry-after", "60")))
    if errors and body.get("data") is None:
        raise BufferError("; ".join(e.get("message", "?") for e in errors))
    if errors:
        log.warning("Buffer returned partial errors: %s", [e.get("message") for e in errors])
    return body["data"]


ACCOUNT_QUERY = """
query Account {
  account { id organizations { id name } }
}
"""

CHANNELS_QUERY = """
query Channels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id name displayName service isDisconnected isLocked
  }
}
"""


def get_account(http: httpx.Client, access_token: str) -> dict:
    return graphql(http, access_token, ACCOUNT_QUERY)["account"]


def get_channels(http: httpx.Client, access_token: str, organization_id: str) -> list[dict]:
    data = graphql(http, access_token, CHANNELS_QUERY, {"organizationId": organization_id})
    return data["channels"]
