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


CREATE_POST_MUTATION = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess { post { id status dueAt } }
    ... on MutationError { message }
  }
}
"""

POST_QUERY = """
query Post($id: PostId!) {
  post(input: { id: $id }) { id status dueAt sentAt externalLink error { message } }
}
"""


class BufferPostRejected(BufferError):
    """createPost returned a typed MutationError (bad channel, limit reached, bad media...)."""


def create_post(
    http: httpx.Client,
    access_token: str,
    *,
    channel_id: str,
    text: str,
    image_url: str,
    alt_text: str | None = None,
    due_at: str | None = None,
    draft: bool = False,
) -> dict:
    """Create an image post. `due_at` (ISO 8601) schedules it; otherwise it joins the queue.

    Not retried on failure: createPost has no idempotency key, so a retry after a timeout
    could publish twice.
    """
    image: dict = {"url": image_url}
    if alt_text:
        image["metadata"] = {"altText": alt_text}
    post_input = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": "customScheduled" if due_at else "addToQueue",
        "assets": [{"image": image}],
        "saveToDraft": draft,
    }
    if due_at:
        post_input["dueAt"] = due_at
    result = graphql(http, access_token, CREATE_POST_MUTATION, {"input": post_input})["createPost"]
    if "post" not in result:
        raise BufferPostRejected(result.get("message", "Buffer rejected the post"))
    return result["post"]


def get_post(http: httpx.Client, access_token: str, post_id: str) -> dict:
    return graphql(http, access_token, POST_QUERY, {"id": post_id})["post"]
