"""Ratatoskr: sends WhatsApp Web messages through a dedicated Chrome profile.

    python main.py "Alice" "See you at 8"
    python main.py --to Alice --to "Family" --file note.txt --at 21:30
    echo "multi\\nline" | python main.py Alice - --dry-run
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

__version__ = "2.0.0"

DEFAULT_PROFILE = os.path.join(os.path.expanduser("~"), ".ratatoskr_profile")
MAX_TOTAL = 20          # messages per run, all contacts together: this is not a spam tool
MAX_LENGTH = 4000
SEARCH_BOX = '//div[@contenteditable="true"][@data-tab="3"]'
MESSAGE_BOX = '//footer//div[@contenteditable="true"]'


def default_profile_dir(environ=os.environ):
    return os.path.expanduser(environ.get("RATATOSKR_PROFILE") or DEFAULT_PROFILE)


def parse_at(text: str, now: dt.datetime) -> dt.datetime:
    """'21:30' -> the next 21:30 (today or tomorrow)."""
    try:
        hour, minute = (int(x) for x in text.split(":"))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except ValueError:
        raise ValueError("--at expects HH:MM, e.g. 21:30")
    return target if target > now else target + dt.timedelta(days=1)


def is_bmp(text: str) -> bool:
    """ChromeDriver can only type Basic Multilingual Plane characters (no emoji)."""
    return all(ord(ch) <= 0xFFFF for ch in text)


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="ratatoskr", description="Send WhatsApp Web messages with Selenium.")
    p.add_argument("contact", nargs="?", help="exact name of the contact or group (or use --to)")
    p.add_argument("message", nargs="?", help="message text, or '-' to read it from stdin")
    p.add_argument("--to", action="append", default=[], help="recipient; repeat for several")
    p.add_argument("--file", help="read the message from a UTF-8 text file")
    p.add_argument("-n", "--repeat", type=int, default=1, help="send each message N times (default 1)")
    p.add_argument("--delay", type=float, default=1.5, help="seconds between messages (min 1)")
    p.add_argument("--at", help="wait until HH:MM before sending")
    p.add_argument("--login-wait", type=int, default=60, help="max seconds to wait for login / QR scan")
    p.add_argument("--profile", default=None, help="Chrome profile folder (default ~/.ratatoskr_profile)")
    p.add_argument("--dry-run", action="store_true", help="show what would be sent, open no browser")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)
    if args.to and args.contact and args.message is None:
        args.contact, args.message = None, args.contact  # `--to A "text"`: the positional is the message

    contacts = [c.strip() for c in ([args.contact] if args.contact else []) + args.to if c and c.strip()]
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as fh:
                message = fh.read()
        except OSError as exc:
            p.error(f"cannot read {args.file}: {exc.strerror}")
    elif args.message == "-":
        message = sys.stdin.read()
    else:
        message = args.message or ""
    message = message.strip()

    if not contacts:
        p.error("give a contact (positional or --to)")
    if not message:
        p.error("contact and message must not be empty")
    if len(message) > MAX_LENGTH:
        p.error(f"message is longer than {MAX_LENGTH} characters")
    if args.repeat < 1 or len(contacts) * args.repeat > MAX_TOTAL:
        p.error(f"--repeat must be at least 1 and recipients x repeat at most {MAX_TOTAL}")
    if args.delay < 1:
        p.error("--delay must be at least 1 second")
    if not 5 <= args.login_wait <= 600:
        p.error("--login-wait must be 5-600 seconds")
    if args.at:
        try:
            args.send_at = parse_at(args.at, dt.datetime.now())
        except ValueError as exc:
            p.error(str(exc))
    else:
        args.send_at = None
    args.contacts, args.text = list(dict.fromkeys(contacts)), message
    return args


class WhatsApp:
    """Drives an already opened WhatsApp Web page. The driver and the wait are injected,
    so the flow can be tested with fakes."""

    def __init__(self, driver, wait_for, keys, by_xpath="xpath", sleep=time.sleep):
        self.driver, self.wait_for, self.keys, self.by, self.sleep = driver, wait_for, keys, by_xpath, sleep

    def open_chat(self, contact: str) -> None:
        box = self.wait_for(SEARCH_BOX)
        box.click()
        box.send_keys(self.keys.CONTROL + "a")
        box.send_keys(self.keys.BACKSPACE)
        box.send_keys(contact)
        self.sleep(2)
        box.send_keys(self.keys.ENTER)
        self.wait_for(MESSAGE_BOX)

    def type_message(self, box, text: str) -> None:
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line:
                if is_bmp(line):
                    box.send_keys(line)
                else:  # emoji: insert through the browser, typing would fail
                    self.driver.execute_script("arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
                                               box, line)
            if i < len(lines) - 1:
                box.send_keys(self.keys.SHIFT + self.keys.ENTER)  # new line, do not send yet

    def send(self, contact: str, text: str, repeat: int, delay: float) -> int:
        self.open_chat(contact)
        sent = 0
        for _ in range(repeat):
            box = self.wait_for(MESSAGE_BOX)
            box.click()
            self.type_message(box, text)
            box.send_keys(self.keys.ENTER)
            sent += 1
            self.sleep(delay)
        return sent


def run(args) -> int:
    if args.dry_run:
        when = f" at {args.send_at:%Y-%m-%d %H:%M}" if args.send_at else ""
        for contact in args.contacts:
            print(f"would send to {contact!r}{when}, {args.repeat}x:")
            for line in args.text.splitlines():
                print(f"  | {line}")
        return 0
    if args.send_at:
        wait = (args.send_at - dt.datetime.now()).total_seconds()
        print(f"Waiting until {args.send_at:%H:%M} ({wait / 60:.0f} min). Ctrl+C cancels.")
        time.sleep(max(0, wait))

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager

    profile = args.profile or default_profile_dir()
    os.makedirs(profile, mode=0o700, exist_ok=True)  # holds your WhatsApp session
    options = Options()
    options.add_argument(f"user-data-dir={profile}")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get("https://web.whatsapp.com")
        print(f"Waiting up to {args.login_wait}s for WhatsApp (scan the QR code on the first run)...")
        WebDriverWait(driver, args.login_wait).until(EC.presence_of_element_located((By.XPATH, SEARCH_BOX)))

        def wait_for(xpath):
            return WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, xpath)))

        app = WhatsApp(driver, wait_for, Keys)
        total = 0
        for contact in args.contacts:
            try:
                total += app.send(contact, args.text, args.repeat, args.delay)
                print(f"  sent to {contact}")
            except Exception as exc:  # one unknown contact must not stop the others
                print(f"  could not send to {contact}: {type(exc).__name__}")
        time.sleep(3)  # let the last message leave
        print(f"Done: {total} message(s).")
        return 0 if total == len(args.contacts) * args.repeat else 1
    except Exception as exc:
        print(f"Failed (not logged in, or WhatsApp changed its layout?): {type(exc).__name__}")
        return 1
    finally:
        driver.quit()


def main(argv=None) -> int:
    try:
        return run(parse_args(argv))
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


# v1 compatibility
def send_whatsapp(contact_name, message, repeat=1, login_wait=60, profile_dir=None):
    argv = [contact_name, message, "-n", str(repeat), "--login-wait", str(login_wait)]
    if profile_dir:
        argv += ["--profile", profile_dir]
    return main(argv) == 0


if __name__ == "__main__":
    sys.exit(main())
