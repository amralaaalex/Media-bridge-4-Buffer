"""Drive the running media-bridge web app in a real browser (installed Edge via Playwright).

Run from the repo root, with the dev server already up on https://localhost:8000:

    uv run --with playwright python .claude/skills/run-media-bridge/driver.py shots
    uv run --with playwright python .claude/skills/run-media-bridge/driver.py draft-flow

shots       landing, /privacy, app page (empty + filled composer) at desktop 1280 and
            mobile 390 widths, light + dark. Nothing is sent to Buffer.
draft-flow  uploads a generated PNG through the composer as a Buffer *draft* (never
            publishes), then clicks "Delete now". Prints the Buffer post id so the
            leftover draft can be deleted (it spends ~2 app-client API calls).

Logged-in pages use a session cookie signed with SESSION_SECRET for --uid (default 1,
the first user who logged in via /login). Screenshots go to .run/shots/ (gitignored).
"""

import argparse
import base64
import json
import pathlib
import sys

from itsdangerous import TimestampSigner
from playwright.sync_api import sync_playwright

sys.path.insert(0, ".")
from app.config import get_settings
from scripts.smoke_test import dummy_png

OUT = pathlib.Path(".run/shots")


def session_cookie(uid: int) -> str:
    """Starlette SessionMiddleware format: TimestampSigner(secret).sign(b64(json))."""
    payload = base64.b64encode(json.dumps({"uid": uid}).encode())
    return TimestampSigner(get_settings().session_secret).sign(payload).decode()


def new_context(browser, base, uid, *, width=1280, height=900, scheme="light", logged_in=True):
    ctx = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=scheme,
        ignore_https_errors=True,  # self-signed dev cert
    )
    if logged_in:
        ctx.add_cookies([{"name": "session", "value": session_cookie(uid), "url": base}])
    return ctx


def watch_errors(page, errors):
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))


def open_app(page, base):
    page.goto(base + "/")
    page.wait_for_selector(".channel", timeout=20000)  # channels come from /api/channels
    page.wait_for_load_state("networkidle")


def cmd_shots(browser, args, image, errors):
    for scheme in ("light", "dark"):
        for name, w, h in (("desktop", 1280, 900), ("mobile", 390, 844)):
            ctx = new_context(
                browser, args.base, args.uid, width=w, height=h, scheme=scheme, logged_in=False
            )
            page = ctx.new_page()
            watch_errors(page, errors)
            for path, label in (("/", "landing"), ("/privacy", "privacy")):
                page.goto(args.base + path)
                page.screenshot(path=OUT / f"{label}-{name}-{scheme}.png", full_page=True)
            ctx.add_cookies(
                [{"name": "session", "value": session_cookie(args.uid), "url": args.base}]
            )
            open_app(page, args.base)
            page.screenshot(path=OUT / f"app-{name}-{scheme}.png", full_page=True)
            page.set_input_files("#file-input", str(image))
            page.fill("#text", "Screenshot run: filled composer")
            page.fill("#alt", "A plain blue test image")
            page.click("#modes >> text=Schedule")
            page.screenshot(path=OUT / f"app-filled-{name}-{scheme}.png", full_page=True)
            ctx.close()


def cmd_draft_flow(browser, args, image, errors):
    ctx = new_context(browser, args.base, args.uid)
    page = ctx.new_page()
    watch_errors(page, errors)
    open_app(page, args.base)
    page.set_input_files("#file-input", str(image))
    page.fill("#text", "media-bridge driver test: draft (will not publish)")
    page.fill("#alt", "Plain test image from the run-media-bridge driver")
    page.click("#modes >> text=Draft")
    page.click("#submit")
    page.wait_for_selector("#toast:not([hidden])", timeout=30000)
    print("toast:", page.inner_text("#toast"))
    newest = page.evaluate("fetch('/api/files').then(r => r.json()).then(f => f[0])")
    print("file:", newest["id"], newest["state"], "post:", newest["buffer_post_id"])
    page.screenshot(path=OUT / "draft-flow-posted.png", full_page=True)

    page.on("dialog", lambda d: (print("confirm:", d.message), d.accept()))
    page.wait_for_selector(".file-delete")
    page.locator(".file-delete").first.click()
    page.wait_for_function("document.querySelector('#toast').innerText.includes('deleted')")
    print("toast:", page.inner_text("#toast"))
    page.screenshot(path=OUT / "draft-flow-deleted.png", full_page=True)
    print(f"leftover Buffer draft to delete: {newest['buffer_post_id']}")
    ctx.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["shots", "draft-flow"])
    parser.add_argument("--base", default="https://localhost:8000")
    parser.add_argument("--uid", type=int, default=1)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    image = OUT / "test-image.png"
    image.write_bytes(dummy_png(1200, 627))
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")  # installed Edge: no browser download
        {"shots": cmd_shots, "draft-flow": cmd_draft_flow}[args.command](
            browser, args, image, errors
        )
        browser.close()
    print("screenshots:", ", ".join(sorted(x.name for x in OUT.glob("*.png"))))
    print("console errors:", errors or "none")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
