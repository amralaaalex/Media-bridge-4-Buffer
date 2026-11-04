import json
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import buffer_client, cleanup, media, oauth, storage
from app.db import Base, CleanupEvent, FileState, OAuthToken, SessionLocal, User, engine, utcnow
from scripts.smoke_test import dummy_png

CHANNEL = "a" * 24


class FakeBuffer:
    """Buffer GraphQL stand-in: createPost plus aliased post lookups."""

    def __init__(self):
        self.posts: dict[str, dict | None] = {}  # id -> post, None = deleted
        self.create_status = "scheduled"
        self.calls: list[str] = []
        self.rate_limited = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        query, variables = body["query"], body["variables"]
        if self.rate_limited:
            return httpx.Response(429, headers={"retry-after": "120"}, json={"errors": []})
        if "createPost" in query:
            self.calls.append("createPost")
            pid = f"{len(self.posts):024x}"
            inp = variables["input"]
            post = {"id": pid, "status": self.create_status, "dueAt": inp.get("dueAt")}
            self.posts[pid] = post
            return httpx.Response(200, json={"data": {"createPost": {"post": post}}})
        self.calls.append(f"posts:{len(variables)}")
        data, errors = {}, []
        for alias, pid in variables.items():
            post = self.posts.get(pid)
            if post is None:
                errors.append(
                    {"message": "not found", "path": [alias], "extensions": {"code": "NOT_FOUND"}}
                )
            else:
                data[alias] = {**post, "sentAt": None, "error": None}
        # `post` is non-null: any error nulls the whole response, as GraphQL would.
        return httpx.Response(200, json={"data": None if errors else data, "errors": errors})


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    buffer_client.rate_limits.windows = []


@pytest.fixture
def r2(monkeypatch):
    objects: dict[str, bytes] = {}

    def upload(data, content_type):
        key = f"{len(objects)}.{storage.EXTENSIONS[content_type]}"
        objects[key] = data
        return key, f"https://media.test/{key}"

    monkeypatch.setattr(storage, "upload", upload)
    monkeypatch.setattr(storage, "delete", lambda key: objects.pop(key, None))
    return objects


@pytest.fixture
def buffer():
    fake = FakeBuffer()
    with httpx.Client(transport=httpx.MockTransport(fake)) as http:
        fake.http = http
        yield fake


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def user(db):
    u = User(buffer_account_id="acct", buffer_org_id="org")
    db.add(u)
    db.flush()
    oauth.store_tokens(db, u, {"access_token": "at", "refresh_token": "rt", "expires_in": 86400})
    db.commit()
    return u


def posted_file(db, buffer, user, *, mode="schedule", minutes=60):
    f = media.upload_file(db, user, dummy_png(10, 10))
    due = utcnow() + timedelta(minutes=minutes) if mode == "schedule" else None
    return media.post_file(
        db, buffer.http, user, f, channel_id=CHANNEL, text="hi", mode=mode, due_at=due
    )


def events(db, f):
    return [(e.decision, e.reason) for e in db.query(CleanupEvent).filter_by(media_file_id=f.id)]


def test_sniff_content_type():
    assert media.sniff_content_type(dummy_png(1, 1)) == "image/png"
    assert media.sniff_content_type(b"\xff\xd8\xff\xe0rest") == "image/jpeg"
    assert media.sniff_content_type(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert media.sniff_content_type(b"%PDF-1.7") is None


def test_upload_rejects_non_images_and_oversize(db, user, r2, monkeypatch):
    with pytest.raises(media.UploadRejected):
        media.upload_file(db, user, b"%PDF-1.7 not an image")
    monkeypatch.setattr(media.get_settings(), "max_upload_mb", 0)
    with pytest.raises(media.UploadRejected):
        media.upload_file(db, user, dummy_png(10, 10))
    assert r2 == {}


def test_scheduled_post_is_held_until_due_without_api_calls(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    assert f.state == FileState.HELD and f.due_at is not None
    assert f.next_check_at == f.due_at + timedelta(minutes=2)
    assert f.ttl_expires_at > utcnow() + timedelta(days=59)

    next_at = cleanup.run_pass(db, buffer.http)
    assert buffer.calls == ["createPost"]  # nothing due: Buffer isn't asked
    assert next_at == f.next_check_at


def test_sent_post_purges_file(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    buffer.posts[f.buffer_post_id]["status"] = "sent"
    cleanup.run_pass(db, buffer.http, now=f.next_check_at)
    db.refresh(f)
    assert f.state == FileState.PURGED and f.object_key not in r2
    assert ("purge", "post_sent") in events(db, f)


def test_post_deleted_in_buffer_purges_file(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    buffer.posts[f.buffer_post_id] = None
    cleanup.run_pass(db, buffer.http, now=f.next_check_at)
    db.refresh(f)
    assert f.state == FileState.PURGED
    assert ("purge", "post_deleted") in events(db, f)


def test_batch_with_one_deleted_post_keeps_the_others(db, buffer, user, r2):
    a = posted_file(db, buffer, user, minutes=60)
    b = posted_file(db, buffer, user, minutes=60)
    buffer.posts[a.buffer_post_id] = None
    now = max(a.next_check_at, b.next_check_at)
    cleanup.run_pass(db, buffer.http, now=now)
    db.refresh(a)
    db.refresh(b)
    assert buffer.calls[-1] == "posts:2"  # one batched request
    assert a.state == FileState.PURGED
    assert b.state == FileState.HELD and b.next_check_at > now  # re-checked later


def test_still_scheduled_post_is_rechecked_later(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    now = f.next_check_at
    cleanup.run_pass(db, buffer.http, now=now)
    db.refresh(f)
    assert f.state == FileState.HELD
    assert f.next_check_at == now + timedelta(minutes=10)  # due but not sent: publishing


def test_unposted_upload_expires_without_api_calls(db, buffer, user, r2):
    f = media.upload_file(db, user, dummy_png(10, 10))
    cleanup.run_pass(db, buffer.http, now=f.ttl_expires_at)
    db.refresh(f)
    assert f.state == FileState.EXPIRED and r2 == {}
    assert buffer.calls == []
    assert events(db, f) == [("expire", "never_posted")]


def test_rate_limit_backs_off_instead_of_spinning(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    buffer.rate_limited = True
    now = f.next_check_at
    assert cleanup.run_pass(db, buffer.http, now=now) == now + timedelta(seconds=120)
    db.refresh(f)
    assert f.state == FileState.HELD


def test_disconnected_user_is_skipped_for_a_day(db, buffer, user, r2):
    f = posted_file(db, buffer, user, minutes=60)
    db.get(OAuthToken, user.id).expires_at = utcnow() - timedelta(minutes=1)
    user.disconnected_at = utcnow()
    db.commit()
    now = f.next_check_at
    cleanup.run_pass(db, buffer.http, now=now)
    db.refresh(f)
    assert f.next_check_at == now + timedelta(hours=24)


def test_api_upload_post_and_delete_now(db, buffer, user, r2):
    from app.main import app, get_http, require_user

    app.dependency_overrides[require_user] = lambda: db.get(User, user.id)
    app.dependency_overrides[get_http] = lambda: buffer.http
    try:
        with TestClient(app, base_url="https://testserver") as client:
            up = client.post("/api/files", files={"file": ("x.png", dummy_png(10, 10))})
            assert up.status_code == 201, up.text
            fid = up.json()["id"]
            due = (utcnow() + timedelta(hours=1)).isoformat()
            body = {"channel_id": CHANNEL, "text": "hi", "mode": "schedule", "due_at": due}
            posted = client.post(f"/api/files/{fid}/post", json=body)
            assert posted.status_code == 200, posted.text
            assert posted.json()["state"] == "HELD"
            deleted = client.post(f"/api/files/{fid}/delete").json()
            assert deleted["state"] == "PURGED" and deleted["warning"]
            bad = client.post("/api/files", files={"file": ("x.pdf", b"%PDF")})
            assert bad.status_code == 400
    finally:
        app.dependency_overrides.clear()
