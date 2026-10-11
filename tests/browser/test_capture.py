"""Real Chrome against a controlled server. Never counted as public-web evidence."""

import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scrape import ScrapeOptions, scrape_page


class Handler(BaseHTTPRequestHandler):
    attempts = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/delayed")
            self.end_headers()
            return
        if self.path == "/blocked":
            self.send_response(302)
            self.send_header(
                "Location",
                "http://localhost:" + str(self.server.server_port) + "/delayed",
            )
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(3)
        if self.path == "/body-empty-main":
            body = "<main></main><div>Readable product content</div>"
        elif self.path == "/body-hidden-main":
            body = '<main style="display:none">Hidden</main><div>Readable product content</div>'
        elif self.path == "/retry":
            Handler.attempts += 1
            body = (
                "<body></body>"
                if Handler.attempts == 1
                else '<main id="data">Recovered content</main>'
            )
        elif self.path == "/empty":
            body = "<body></body>"
        elif self.path == "/changing":
            body = '<main id="data">Start</main><script>setInterval(()=>document.querySelector("main").textContent=String(Date.now()),40)</script>'
        else:
            body = '<main id="data"></main><script>setTimeout(()=>document.querySelector("main").textContent="Delayed product £12.50",500)</script>'
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
        except (BrokenPipeError, ConnectionResetError):
            pass


@unittest.skipUnless(
    os.getenv("RUN_BROWSER_TESTS") == "1", "Opt in to real Chrome tests"
)
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Provision driver/browser before timing individual capture scenarios.
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service

        chrome = Options()
        chrome.add_argument("--headless=new")
        if os.getenv("CHROME_BINARY"):
            chrome.binary_location = os.environ["CHROME_BINARY"]
        service = (
            Service(executable_path=os.environ["CHROMEDRIVER"])
            if os.getenv("CHROMEDRIVER")
            else Service()
        )
        warm = webdriver.Chrome(options=chrome, service=service)
        cls.driver_path = warm.service.path
        cls.browser_version = warm.capabilities["browserVersion"]
        warm.quit()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = ("http", "127.0.0.1", cls.server.server_port)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def capture(self, path, **kwargs):
        with tempfile.TemporaryDirectory() as root:
            options = {
                "content_selector": "#data",
                "stable_seconds": 0.2,
                # Ordinary pages must finish navigation before content readiness
                # is evaluated, including on shared hosted runners.
                "navigation_timeout": 5,
                "content_timeout": 1.5,
                "overall_timeout": 25,
            }
            options.update(kwargs)
            opts = ScrapeOptions(**options)
            r = scrape_page(
                self.base + path, opts, Path(root) / "capture", _test_origin=self.origin
            )
            if r.status == "success":
                self.assertTrue(Path(r.artifacts["screenshot"]).exists())
                self.assertTrue(Path(r.artifacts["html"]).exists())
            return r

    def test_delayed_target_and_redirect(self):
        r = self.capture("/redirect", attempts=1)
        self.assertEqual(r.status, "success", r.as_dict())
        self.assertIn("Delayed product", r.html)
        self.assertTrue(r.final_url.endswith("/delayed"))
        self.assertIsNotNone(r.browser_version)

    def test_empty_target_and_changing_content_timeout(self):
        for path in ["/empty", "/changing"]:
            r = self.capture(path, attempts=1)
            self.assertEqual(r.error_code, "content_timeout", r.as_dict())
            self.assertEqual(r.html, "")

    def test_navigation_timeout_is_not_success(self):
        self.assertEqual(
            self.capture("/slow", attempts=1, navigation_timeout=1).error_code,
            "navigation_timeout",
        )

    def test_retry_uses_fresh_browser_and_retains_failure_diagnostics(self):
        Handler.attempts = 0
        r = self.capture("/retry", attempts=2)
        self.assertEqual(r.status, "success", r.as_dict())
        self.assertEqual([a["status"] for a in r.attempts], ["failed", "success"])

    def test_invalid_selector_and_cross_origin_redirect_are_not_retried(self):
        with tempfile.TemporaryDirectory() as root:
            r = scrape_page(
                self.base + "/delayed",
                ScrapeOptions(content_selector="[", overall_timeout=25),
                Path(root) / "invalid",
                _test_origin=self.origin,
            )
        self.assertEqual(r.error_code, "invalid_selector", r.as_dict())
        self.assertEqual(len(r.attempts), 1)
        r = self.capture("/blocked", attempts=2)
        self.assertEqual(r.error_code, "blocked_redirect")
        self.assertEqual(len(r.attempts), 1)

    def test_implicit_readiness_falls_back_but_explicit_target_does_not(self):
        for suffix in ("/body-empty-main", "/body-hidden-main"):
            with tempfile.TemporaryDirectory() as root:
                r = scrape_page(
                    self.base + suffix,
                    ScrapeOptions(stable_seconds=0.2, attempts=1, overall_timeout=25),
                    Path(root) / "fallback",
                    _test_origin=self.origin,
                )
                self.assertEqual(r.status, "success", r.as_dict())
                self.assertIn("Readable product content", r.html)
        with tempfile.TemporaryDirectory() as root:
            r = scrape_page(
                self.base + "/body-empty-main",
                ScrapeOptions(
                    content_selector="main",
                    stable_seconds=0.2,
                    content_timeout=0.5,
                    attempts=1,
                    overall_timeout=25,
                ),
                Path(root) / "explicit",
                _test_origin=self.origin,
            )
            self.assertEqual(r.error_code, "content_timeout", r.as_dict())

    def test_capture_reuses_verified_driver_when_manager_is_unavailable(self):
        from unittest.mock import patch

        from browser_driver import save_verified_driver
        from scrape import _capture_once

        with tempfile.TemporaryDirectory() as root:
            record = Path(root) / "driver.json"
            save_verified_driver(self.driver_path, self.browser_version, record)
            with (
                patch.dict(os.environ, {"CHROMEDRIVER": ""}),
                patch("browser_driver.DRIVER_RECORD", record),
                patch(
                    "selenium.webdriver.common.selenium_manager.SeleniumManager.binary_paths",
                    side_effect=AssertionError("Manager must not run"),
                ),
            ):
                result = _capture_once(
                    self.base + "/delayed",
                    ScrapeOptions(content_selector="#data", stable_seconds=0.2),
                    Path(root),
                    self.origin,
                )
            self.assertEqual(result["status"], "success", result)

    def test_hard_deadline_and_default_public_policy(self):
        with tempfile.TemporaryDirectory() as root:
            r = scrape_page(
                self.base + "/slow",
                ScrapeOptions(overall_timeout=0.15),
                Path(root) / "deadline",
                _test_origin=self.origin,
            )
            self.assertEqual(r.error_code, "overall_timeout")
            self.assertLess(r.elapsed_seconds, 2)
            r = scrape_page(
                self.base + "/delayed",
                ScrapeOptions(overall_timeout=5),
                Path(root) / "private",
            )
            self.assertEqual(r.error_code, "invalid_url")


if __name__ == "__main__":
    unittest.main()
