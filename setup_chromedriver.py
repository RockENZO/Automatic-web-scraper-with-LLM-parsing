#!/usr/bin/env python3
"""Install, verify and persist a recovery driver consumed by the scraper."""

from browser_driver import get_chrome_version, save_verified_driver


def setup_chromedriver(
    *, driver_installer=None, driver_factory=None, version_reader=None, record_path=None
):
    version = (version_reader or get_chrome_version)()
    if not version:
        print("Could not detect Chrome. Install it or set CHROME_BINARY.")
        return False
    driver = None
    try:
        if driver_installer is None:
            from webdriver_manager.chrome import ChromeDriverManager

            driver_installer = lambda: ChromeDriverManager().install()
        path = driver_installer()
        if driver_factory is None:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument("--headless=new")
            import os

            if os.getenv("CHROME_BINARY"):
                options.binary_location = os.environ["CHROME_BINARY"]
            driver = webdriver.Chrome(service=Service(path), options=options)
        else:
            driver = driver_factory(path)
        driver.get("about:blank")
        save_verified_driver(path, driver.capabilities["browserVersion"], record_path)
        print("Verified driver saved for subsequent scraper sessions:", path)
        return True
    except Exception as error:
        print("ChromeDriver setup failed:", error)
        return False
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def main():
    raise SystemExit(0 if setup_chromedriver() else 1)


if __name__ == "__main__":
    main()
