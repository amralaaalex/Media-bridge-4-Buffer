"""Drive the file lifecycle from the terminal, as the first logged-in user in the DB.

    uv run python -m scripts.cli post IMAGE --text "..." --mode draft|queue|schedule|now
                                            [--in MINUTES] [--alt "..."] [--channel ID]
    uv run python -m scripts.cli files
    uv run python -m scripts.cli check [--force]     # run one cleanup pass now
    uv run python -m scripts.cli delete FILE_ID      # "delete now"

Uses the same code paths as the web API, so it spends the app client's Buffer quota.
"""

import argparse
import pathlib
import sys
from datetime import timedelta

import httpx
from sqlalchemy import select

from app import buffer_client, cleanup, media, oauth
from app.db import FileState, MediaFile, SessionLocal, User, init_db, utcnow


def first_user(db) -> User:
    user = db.execute(select(User).order_by(User.id)).scalars().first()
    if user is None:
        sys.exit("No user in the DB: log in through the web app first.")
    return user


def show(f: MediaFile) -> None:
    def t(dt):
        return f"{dt:%m-%d %H:%M}Z" if dt else "-"

    print(
        f"{f.id}  {f.state.value:<8} post={f.buffer_post_id or '-'} "
        f"status={f.last_post_status or '-'} due={t(f.due_at)} next_check={t(f.next_check_at)}"
    )


def cmd_post(args, db, http, user) -> None:
    data = pathlib.Path(args.image).read_bytes()
    try:
        f = media.upload_file(db, user, data)
    except media.UploadRejected as exc:
        sys.exit(f"upload rejected: {exc}")
    print(f"uploaded {f.public_url}")
    channel = args.channel
    if channel is None:
        token = oauth.get_access_token(db, user, http)
        channel = buffer_client.get_channels(http, token, user.buffer_org_id)[0]["id"]
    due = utcnow() + timedelta(minutes=args.in_minutes) if args.mode == "schedule" else None
    try:
        f = media.post_file(
            db,
            http,
            user,
            f,
            channel_id=channel,
            text=args.text,
            mode=args.mode,
            alt_text=args.alt,
            due_at=due,
        )
    except media.PostFailed as exc:
        sys.exit(f"post failed (file stays UPLOADED and expires on its own): {exc}")
    show(f)


def cmd_files(args, db, http, user) -> None:
    for f in db.execute(
        select(MediaFile).where(MediaFile.user_id == user.id).order_by(MediaFile.created_at)
    ).scalars():
        show(f)


def cmd_check(args, db, http, user) -> None:
    if args.force:
        for f in db.execute(select(MediaFile).where(MediaFile.state == FileState.HELD)).scalars():
            f.next_check_at = utcnow()
        db.commit()
    print(f"next pass needed at: {cleanup.run_pass(db, http)}")
    print(f"rate limit windows (remaining, reset s): {buffer_client.rate_limits.windows}")
    cmd_files(args, db, http, user)


def cmd_delete(args, db, http, user) -> None:
    f = db.get(MediaFile, args.file_id)
    if f is None or f.user_id != user.id:
        sys.exit("no such file")
    if f.state not in (FileState.UPLOADED, FileState.HELD):
        sys.exit(f"already {f.state.value}")
    if media.post_still_needs_file(f):
        print("warning: the Buffer post still needs this image; delete or edit it in Buffer")
    media.remove_file(
        db,
        f,
        state=FileState.PURGED,
        decision="purge",
        reason="user_deleted",
        post_status=f.last_post_status,
    )
    show(f)


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("post")
    p.add_argument("image")
    p.add_argument("--text", required=True)
    p.add_argument("--mode", choices=["draft", "queue", "schedule", "now"], required=True)
    p.add_argument("--in", dest="in_minutes", type=int, default=10)
    p.add_argument("--alt")
    p.add_argument("--channel")
    sub.add_parser("files")
    c = sub.add_parser("check")
    c.add_argument("--force", action="store_true", help="treat every HELD file as due")
    d = sub.add_parser("delete")
    d.add_argument("file_id")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db, httpx.Client() as http:
        user = first_user(db)
        {"post": cmd_post, "files": cmd_files, "check": cmd_check, "delete": cmd_delete}[args.cmd](
            args, db, http, user
        )


if __name__ == "__main__":
    main()
