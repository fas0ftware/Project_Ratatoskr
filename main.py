"""Ratatoskr: sends a WhatsApp Web message to a contact through a dedicated Chrome profile."""

import argparse
import os
import sys
import time

DEFAULT_PROFILE = os.path.join(os.path.expanduser("~"), ".ratatoskr_profile")
MAX_REPEAT = 20


def default_profile_dir(environ=os.environ):
    return environ.get("RATATOSKR_PROFILE") or DEFAULT_PROFILE


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Send a WhatsApp Web message with Selenium.")
    parser.add_argument("contact", help="exact name of the contact or group as shown in WhatsApp")
    parser.add_argument("message", help="message text")
    parser.add_argument("-n", "--repeat", type=int, default=1,
                        help=f"how many times to send it (1-{MAX_REPEAT}, default 1)")
    parser.add_argument("--login-wait", type=int, default=30,
                        help="seconds to wait for the page / QR login (default 30)")
    parser.add_argument("--profile", default=None, help="Chrome profile folder (default ~/.ratatoskr_profile)")
    args = parser.parse_args(argv)
    if not 1 <= args.repeat <= MAX_REPEAT:
        parser.error(f"--repeat must be between 1 and {MAX_REPEAT}")
    if not args.message.strip() or not args.contact.strip():
        parser.error("contact and message must not be empty")
    return args


def send_whatsapp(contact_name, message, repeat=1, login_wait=30, profile_dir=None):
    # Selenium is imported here so the argument handling can be used and tested without it.
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from webdriver_manager.chrome import ChromeDriverManager

    profile_dir = profile_dir or default_profile_dir()
    os.makedirs(profile_dir, exist_ok=True)

    options = Options()
    # A dedicated profile keeps the WhatsApp login and does not touch your normal Chrome.
    options.add_argument(f"user-data-dir={profile_dir}")
    options.add_argument("--disable-dev-shm-usage")

    print("Ratatoskr: starting Chrome with the dedicated profile...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get("https://web.whatsapp.com")
        print(f"Waiting {login_wait}s. On the first run, scan the QR code in this window.")
        time.sleep(login_wait)

        search_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]')
        search_box.click()
        time.sleep(1)
        search_box.send_keys(contact_name)
        time.sleep(2)
        search_box.send_keys(Keys.ENTER)
        time.sleep(2)

        for _ in range(repeat):
            message_box = driver.find_element(By.XPATH, '//div[@contenteditable="true"][@data-tab="10"]')
            message_box.click()
            message_box.send_keys(message)
            time.sleep(1)
            message_box.send_keys(Keys.ENTER)
            time.sleep(1)
        print(f"Sent {repeat} message(s).")
        time.sleep(3)
        return True
    except Exception as error:
        print(f"Failed (not logged in yet, or WhatsApp changed its layout?): {type(error).__name__}: {error}")
        return False
    finally:
        driver.quit()
        print("Ratatoskr closed.")


def main(argv=None):
    args = parse_args(argv)
    ok = send_whatsapp(args.contact, args.message, args.repeat, args.login_wait, args.profile)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
