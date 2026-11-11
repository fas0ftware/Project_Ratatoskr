"""Manual smoke test: opens WhatsApp Web in a clean Chrome (no profile) to check Selenium works."""
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def test_connection(seconds: int = 30) -> None:
    print("Opening a clean Chrome without a profile...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    try:
        driver.get("https://web.whatsapp.com")
        print("OK: page opened. Closing in", seconds, "seconds.")
        time.sleep(seconds)
    finally:
        driver.quit()


if __name__ == "__main__":
    test_connection()
