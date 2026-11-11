import json

import httpx
import pytest

from app import buffer_client


def client(response: httpx.Response) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _: response))


def org_buffer(orgs: list[dict], channels: dict[str, list[dict]], error_code: str | None = None):
    """Fake Buffer for the account + per-organization channels queries.

    An organization missing from `channels` answers with `error_code` and null data.
    """
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "account" in body["query"]:
            calls.append("account")
            account = {"id": "acct", "organizations": orgs}
            return httpx.Response(200, json={"data": {"account": account}})
        org = body["variables"]["organizationId"]
        calls.append(org)
        if org not in channels:
            error = {"message": "nope", "extensions": {"code": error_code}}
            return httpx.Response(200, json={"data": None, "errors": [error]})
        return httpx.Response(200, json={"data": {"channels": channels[org]}})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_channels_come_from_every_organization():
    orgs = [
        {"id": "o1", "name": "Personal"},
        {"id": "o2", "name": "Locked"},
        {"id": "o3", "name": "Team"},
    ]
    channels = {"o1": [{"id": "c1", "service": "x"}], "o3": [{"id": "c3", "service": "bluesky"}]}
    http, calls = org_buffer(orgs, channels, error_code="FORBIDDEN")
    with http:
        result = buffer_client.get_all_channels(http, "t")
    assert calls == ["account", "o1", "o2", "o3"]
    # The failing organization is skipped; the others still show, tagged with their org.
    assert [(c["id"], c["organizationId"], c["organizationName"]) for c in result] == [
        ("c1", "o1", "Personal"),
        ("c3", "o3", "Team"),
    ]


def test_channels_auth_failure_is_not_skipped():
    http, _ = org_buffer([{"id": "o1", "name": "A"}], {}, error_code="UNAUTHORIZED")
    with http, pytest.raises(buffer_client.BufferUnauthorized):
        buffer_client.get_all_channels(http, "t")


def test_rate_limit_header_parsed_from_combined_header():
    state = buffer_client.RateLimitState()
    state.update('"100-in-15min"; r=98; t=897, "250-in-24h";r=12;t=4000')
    assert state.windows == [(98, 897), (12, 4000)]
    assert state.min_remaining == 12


def test_429_raises_with_retry_after():
    resp = httpx.Response(429, headers={"retry-after": "753"}, json={"errors": []})
    with client(resp) as http, pytest.raises(buffer_client.BufferRateLimited) as exc:
        buffer_client.graphql(http, "t", "query { x }")
    assert exc.value.retry_after == 753


def test_unauthorized_error_code_raises():
    body = {"data": None, "errors": [{"message": "no", "extensions": {"code": "UNAUTHORIZED"}}]}
    resp = httpx.Response(200, json=body)
    with client(resp) as http, pytest.raises(buffer_client.BufferUnauthorized):
        buffer_client.graphql(http, "t", "query { x }")
