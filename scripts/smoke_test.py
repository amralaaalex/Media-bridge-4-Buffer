"""End-to-end smoke test: dummy image -> R2 -> Buffer draft post.

Uses the grant of the first user in the local DB (log in via the web app first).
Creates a *draft* (saveToDraft), so nothing is published.

    uv run python -m scripts.smoke_test

Spends 3-4 requests of the app client's shared Buffer quota.
"""

import struct
import sys
import zlib

import httpx
from sqlalchemy import select

from app import buffer_client, oauth, storage
from app.db import SessionLocal, User, init_db


def dummy_png(width: int = 1200, height: int = 627) -> bytes:
    """A solid-colour PNG at LinkedIn's recommended link-image size, no Pillow needed."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    row = b"\x00" + bytes((44, 110, 212)) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(row * height, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    init_db()
    with SessionLocal() as db, httpx.Client() as http:
        user = db.execute(select(User).order_by(User.id)).scalars().first()
        if user is None:
            sys.exit("No user in the DB: log in through the web app first.")

        key, url = storage.upload(dummy_png(), "image/png")
        print(f"uploaded   {key}\npublic url {url}")
        check = http.get(url, timeout=20)
        print(f"public GET {check.status_code} {check.headers.get('content-type')}")
        if check.status_code != 200:
            sys.exit("The public URL is not reachable; Buffer would fail to fetch it.")

        token = oauth.get_access_token(db, user, http)
        channels = buffer_client.get_channels(http, token, user.buffer_org_id)
        channel = next(c for c in channels if not c.get("isDisconnected"))
        print(f"channel    {channel['service']} / {channel.get('displayName') or channel['name']}")

        try:
            post = buffer_client.create_post(
                http,
                token,
                channel_id=channel["id"],
                text="media-bridge smoke test (draft, will not publish)",
                image_url=url,
                alt_text="A plain blue test image",
                draft=True,
            )
        except buffer_client.BufferError as exc:
            storage.delete(key)
            sys.exit(f"createPost failed: {exc}")
        print(f"post       {post}")
        print(f"fetched    {buffer_client.get_post(http, token, post['id'])}")
        print(f"rate limit {buffer_client.rate_limits.windows}")

        print("The R2 object is kept so the draft keeps its image; delete the draft in Buffer.")


if __name__ == "__main__":
    main()
