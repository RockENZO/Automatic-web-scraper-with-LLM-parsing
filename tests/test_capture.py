"""Pure API contracts, separate from opt-in browser evidence."""

import unittest
from unittest.mock import patch

from scrape import ScrapeError, ScrapeOptions, ScrapeResult, scrape_website


class CaptureTests(unittest.TestCase):
    def test_invalid_options_fail_before_starting_browser(self):
        for opts in [
            ScrapeOptions(attempts=0),
            ScrapeOptions(overall_timeout=float("nan")),
            ScrapeOptions(content_selector=""),
            ScrapeOptions(headless=1),
        ]:
            with self.assertRaises(ValueError):
                opts.validate()

    def test_metadata_does_not_include_raw_html_and_has_hash(self):
        r = ScrapeResult("success", "https://example.com", html="<main>Hi</main>")
        self.assertNotIn("html", r.as_dict())
        self.assertEqual(len(r.as_dict()["html_sha256"]), 64)

    def test_compatibility_wrapper_preserves_html_or_typed_failure(self):
        with patch(
            "scrape.scrape_page",
            return_value=ScrapeResult("success", "https://example.com", html="value"),
        ):
            self.assertEqual(scrape_website("https://example.com"), "value")
        with patch(
            "scrape.scrape_page",
            return_value=ScrapeResult(
                "failed", "https://example.com", error_code="content_timeout"
            ),
        ):
            with self.assertRaises(ScrapeError) as context:
                scrape_website("https://example.com")
            self.assertEqual(context.exception.result.error_code, "content_timeout")


if __name__ == "__main__":
    unittest.main()
