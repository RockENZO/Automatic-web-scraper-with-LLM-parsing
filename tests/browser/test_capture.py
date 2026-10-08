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
        if self.path == "/retry":
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
            opts = ScrapeOptions(
                content_selector="#data",
                stable_seconds=0.2,
                navigation_timeout=1,
                content_timeout=1.5,
                overall_timeout=25,
                **kwargs,
            )
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
            self.capture("/slow", attempts=1).error_code, "navigation_timeout"
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
