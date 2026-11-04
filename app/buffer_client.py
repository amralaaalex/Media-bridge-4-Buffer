"""Thin client for Buffer's GraphQL API (https://api.buffer.com).

The app client's quota is shared by every user (about 525 requests a day measured), so this
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
    data, errors = graphql_raw(http, access_token, query, variables)
    if errors and data is None:
        raise BufferError("; ".join(e.get("message", "?") for e in errors))
    if errors:
        log.warning("Buffer returned partial errors: %s", [e.get("message") for e in errors])
    return data


def graphql_raw(
    http: httpx.Client, access_token: str, query: str, variables: dict | None = None
) -> tuple[dict | None, list[dict]]:
    """Like `graphql`, but returns (data, errors) so callers can handle partial failures.

    Auth and rate-limit failures still raise.
    """
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
    return body.get("data"), errors


ACCOUNT_QUERY = """
query Account {
  account { id organizations { id name } }
}
"""

CHANNELS_QUERY = """
query Channels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id name displayName service avatar isDisconnected isLocked
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


# Our posting modes -> Buffer's ShareMode. "draft" is any mode plus saveToDraft.
SHARE_MODES = {
    "queue": "addToQueue",
    "schedule": "customScheduled",
    "now": "shareNow",
    "draft": "addToQueue",
}


def create_post(
    http: httpx.Client,
    access_token: str,
    *,
    channel_id: str,
    text: str,
    image_url: str,
    mode: str,
    alt_text: str | None = None,
    due_at: str | None = None,
) -> dict:
    """Create an image post. `due_at` (ISO 8601 UTC) is required for mode "schedule".

    Not retried on failure: createPost has no idempotency key, so a retry after a timeout
    could publish twice.
    """
    if mode not in SHARE_MODES:
        raise ValueError(f"unknown mode: {mode}")
    if (mode == "schedule") != (due_at is not None):
        raise ValueError("due_at is required for, and only allowed with, mode 'schedule'")
    image: dict = {"url": image_url}
    if alt_text:
        image["metadata"] = {"altText": alt_text}
    post_input = {
        "channelId": channel_id,
        "text": text,
        "schedulingType": "automatic",
        "mode": SHARE_MODES[mode],
        "assets": [{"image": image}],
        "saveToDraft": mode == "draft",
    }
    if due_at:
        post_input["dueAt"] = due_at
    result = graphql(http, access_token, CREATE_POST_MUTATION, {"input": post_input})["createPost"]
    if "post" not in result:
        raise BufferPostRejected(result.get("message", "Buffer rejected the post"))
    return result["post"]


def get_post(http: httpx.Client, access_token: str, post_id: str) -> dict:
    return graphql(http, access_token, POST_QUERY, {"id": post_id})["post"]


# Buffer caps aliases per query at 30.
MAX_POSTS_PER_QUERY = 30
_POST_FIELDS = "id status dueAt sentAt externalLink error { message }"


def _is_not_found(error: dict) -> bool:
    return (error.get("extensions") or {}).get("code") == "NOT_FOUND"


def get_posts(http: httpx.Client, access_token: str, post_ids: list[str]) -> dict[str, dict | None]:
    """Look up many posts in one request (aliased `post` fields; `posts` can't filter by id).

    Returns {post_id: post}, with None for posts Buffer reports as NOT_FOUND (deleted).
    Posts whose lookup failed for another reason are left out, so callers re-check later.
    """
    if len(post_ids) > MAX_POSTS_PER_QUERY:
        raise ValueError(f"at most {MAX_POSTS_PER_QUERY} posts per query")
    if not post_ids:
        return {}
    aliases = {f"p{i}": pid for i, pid in enumerate(post_ids)}
    params = ", ".join(f"${a}: PostId!" for a in aliases)
    fields = " ".join(f"{a}: post(input: {{ id: ${a} }}) {{ {_POST_FIELDS} }}" for a in aliases)
    data, errors = graphql_raw(http, access_token, f"query Posts({params}) {{ {fields} }}", aliases)

    failed = {e["path"][0]: e for e in errors if e.get("path")}
    only_not_found = all(e.get("path") and _is_not_found(e) for e in errors)
    if data is None and errors and not only_not_found:
        # `post` is non-null, so one failing alias can null the whole response. Fall back
        # to one request per post, but only when it isn't just deleted posts.
        if len(post_ids) == 1:
            raise BufferError("; ".join(e.get("message", "?") for e in errors))
        result: dict[str, dict | None] = {}
        for pid in post_ids:
            try:
                result.update(get_posts(http, access_token, [pid]))
            except (BufferUnauthorized, BufferRateLimited):
                raise
            except BufferError as exc:
                log.warning("post %s lookup failed: %s", pid, exc)
        return result

    result = {}
    for alias, pid in aliases.items():
        if alias in failed:
            if _is_not_found(failed[alias]):
                result[pid] = None
        elif data and data.get(alias) is not None:
            result[pid] = data[alias]
        # else: the response was nulled by a deleted sibling; status unknown, re-check later.
    return result
