import httpx
import pytest

from app import buffer_client


def client(response: httpx.Response) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _: response))


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
