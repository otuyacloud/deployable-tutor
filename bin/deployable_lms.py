#!/usr/bin/env python3
"""Live, content-free connector for the OpsAndPlatforms Deployable LMS."""

import argparse
import base64
import getpass
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode, urlparse

COURSE = "devops-bootcamp-deployable"
SERVICE = "opsandplatforms-deployable-lms-session"
LOCAL_CLOUDFLARED = Path.home() / ".local" / "share" / "deployable-tutor" / "bin" / "cloudflared"
LMS_HOST = "lms.opsandplatforms.com"


def is_macos() -> bool:
    return sys.platform == "darwin"


def state_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "deployable-tutor" / "frappe.cookies"


def save_session(cookies: Path) -> None:
    payload = base64.b64encode(cookies.read_bytes()).decode("ascii")
    if is_macos():
        subprocess.run(["security", "add-generic-password", "-U", "-s", SERVICE, "-a", "active", "-w", payload], check=True)
        return
    destination = state_path()
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination.write_text(payload)
    destination.chmod(0o600)


def load_session(cookies: Path) -> bool:
    try:
        if is_macos():
            payload = subprocess.run(["security", "find-generic-password", "-s", SERVICE, "-a", "active", "-w"], check=True, text=True, capture_output=True).stdout.strip()
        else:
            payload = state_path().read_text().strip()
        cookies.write_bytes(base64.b64decode(payload, validate=True))
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
        return False


def cloudflared_command() -> str:
    """Prefer the user-local binary installed by install.sh, then PATH."""
    if LOCAL_CLOUDFLARED.exists() and os.access(LOCAL_CLOUDFLARED, os.X_OK):
        return str(LOCAL_CLOUDFLARED)
    return "cloudflared"


def validate_base_url(base_url: str) -> str:
    """Prevent a learner session cookie from being sent to an arbitrary host."""
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.hostname != LMS_HOST or parsed.path not in ("", "/"):
        raise ValueError(f"The Deployable connector only supports https://{LMS_HOST}.")
    return f"https://{LMS_HOST}"


def request(base_url: str, path: str, cookies: Path, data: dict | None = None) -> dict:
    command = [cloudflared_command(), "access", "curl", f"{base_url.rstrip('/')}{path}", "--silent", "--show-error", "--cookie", str(cookies), "--cookie-jar", str(cookies)]
    if data is not None:
        command.extend(["--request", "POST", "--data", urlencode(data)])
    result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def course_outline(base_url: str, cookies: Path) -> list[dict]:
    path = "/api/method/lms.lms.utils.get_course_outline?" + urlencode({"course": COURSE, "progress": 1})
    outline = request(base_url, path, cookies).get("message")
    if not outline:
        raise RuntimeError("The LMS session did not return this course outline.")
    return outline


def next_position(base_url: str, cookies: Path) -> tuple[int, int] | None:
    outline = course_outline(base_url, cookies)
    for chapter in outline:
        for lesson in chapter.get("lessons", []):
            if not lesson.get("is_complete"):
                week, number = lesson["number"].split("-", maxsplit=1)
                return int(week), int(number)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Deployable LMS lesson connector.")
    parser.add_argument("week", type=int, nargs="?", choices=range(0, 15))
    parser.add_argument("--lesson", type=int, default=1)
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--overview", action="store_true", help="Open a week's first overview lesson; requires a week.")
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--login", action="store_true")
    parser.add_argument("--base-url", default="https://lms.opsandplatforms.com")
    args = parser.parse_args()
    try:
        args.base_url = validate_base_url(args.base_url)
    except ValueError as error:
        parser.error(str(error))
    if args.login and (args.week is not None or args.next or args.overview or args.complete):
        parser.error("--login cannot be combined with lesson actions")
    if args.next and (args.week is not None or args.overview or args.complete):
        parser.error("--next cannot be combined with a week, --overview, or --complete")
    if args.overview and (args.week is None or args.complete):
        parser.error("--overview requires a week and cannot be combined with --complete")
    if not args.login and not args.next and args.week is None:
        parser.error("provide a week, --next, --overview, or --login")

    descriptor, temp_path = tempfile.mkstemp(prefix="deployable-lms-", suffix=".cookies")
    os.close(descriptor)
    cookies = Path(temp_path)
    try:
        if args.login:
            subprocess.run([cloudflared_command(), "access", "login", args.base_url], check=True)
            email = input("LMS email: ").strip()
            password = getpass.getpass("LMS password: ")
            login = request(args.base_url, "/api/method/login", cookies, {"usr": email, "pwd": password})
            # Website Users may authenticate successfully with Frappe's "No App"
            # response because they have no Desk app. They can still use LMS portal APIs.
            if login.get("message") not in ("Logged In", "No App"):
                print("LMS login was not accepted.", file=sys.stderr)
                return 3
            save_session(cookies)
            print("This machine is connected to the Deployable LMS.")
            return 0
        if not load_session(cookies):
            print("No LMS session exists on this machine. Run the connector with --login.", file=sys.stderr)
            return 7
        if args.next:
            position = next_position(args.base_url, cookies)
            if position is None:
                print("All course lessons are complete.")
                return 0
            args.week, args.lesson = position
        if args.overview:
            args.lesson = 1
        if args.complete:
            request(args.base_url, "/api/method/lms.lms.api.mark_lesson_progress", cookies, {"course": COURSE, "chapter_number": args.week, "lesson_number": args.lesson})
            save_session(cookies)
            print(f"Marked Week {args.week}, Lesson {args.lesson} complete in the LMS.")
            return 0
        path = "/api/method/lms.lms.utils.get_lesson?" + urlencode({"course": COURSE, "chapter": args.week, "lesson": args.lesson})
        lesson = request(args.base_url, path, cookies).get("message") or {}
        save_session(cookies)
        body = lesson.get("body") or lesson.get("content")
        if not body:
            print("The LMS did not grant access to that lesson. Reconnect with --login if needed.", file=sys.stderr)
            return 4
        print(f"# Week {args.week}, Lesson {args.lesson}: {lesson['title']}\n\n{body}")
        return 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError) as error:
        print(f"LMS request failed: {error}", file=sys.stderr)
        return 6
    finally:
        cookies.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
