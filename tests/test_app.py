"""Verify table/evidence rendering and persistence using Streamlit's real AppTest."""

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from structured_parse import StructuredResult


@unittest.skipUnless(
    importlib.util.find_spec("streamlit"), "Streamlit required for UI checks"
)
class AppTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "main.py"), default_timeout=20
        )
        app.session_state["page_html"] = (
            "<body><article>name: Ada\nemail: ada@example.test</article></body>"
        )
        app.session_state["original_url"] = "https://example.test"
        return app.run()

    def test_structured_table_evidence_and_rerun_persist(self):
        app = self.app()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value("Extract contacts")
        app.text_input[1].set_value("name,email")
        record = {
            "values": {"name": "Ada", "email": "ada@example.test"},
            "evidence": {
                "name": {"block_id": "b0001", "quote": "name: Ada"},
                "email": {"block_id": "b0001", "quote": "email: ada@example.test"},
            },
            "evidence_sets": [],
        }
        with patch(
            "structured_parse.extract_structured",
            return_value=StructuredResult([record], 1, 1),
        ) as extract:
            app.button[1].click().run()
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.dataframe), 1)
            self.assertEqual(len(app.json), 1)
            document = app.session_state["extraction_document"]
            self.assertEqual(document["records"][0]["values"]["name"], "Ada")
            self.assertIn("b0001", document["source_blocks"])
            self.assertEqual(len(app.get("download_button")), 1)
            app.run()
            self.assertEqual(extract.call_count, 1)
            self.assertEqual(len(app.dataframe), 1)

    def test_failure_has_no_download(self):
        app = self.app()
        app.text_area[0].set_value("Extract products")
        with patch(
            "structured_parse.extract_structured",
            return_value=StructuredResult([], 1, failed_chunks=[1]),
        ):
            app.button[1].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(len(app.get("download_button")), 0)

    def app_with_successful_extraction(self):
        app = self.app()
        app.text_area[0].set_value("Extract products")
        record = {"values": {"name": "Ada", "price": None}, "evidence": {}}
        with patch(
            "structured_parse.extract_structured",
            return_value=StructuredResult([record], 1, 1),
        ):
            app.button[1].click().run()
        self.assertEqual(len(app.dataframe), 1)
        self.assertIn("extraction_document", app.session_state)
        return app

    def assert_no_previous_result(self, app):
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("extraction_document", app.session_state)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual(len(app.get("download_button")), 0)
        self.assertEqual(len(app.success), 0)

    def test_invalid_fields_clear_previous_result(self):
        app = self.app_with_successful_extraction()
        app.text_input[1].set_value("name,name")
        with patch("structured_parse.extract_structured") as extract:
            app.button[1].click().run()
        extract.assert_not_called()
        self.assert_no_previous_result(app)

    def test_empty_description_clears_previous_result(self):
        app = self.app_with_successful_extraction()
        app.text_area[0].set_value("   ")
        app.button[1].click().run()
        self.assert_no_previous_result(app)

    def test_extractor_exception_clears_previous_result_and_allows_retry(self):
        app = self.app_with_successful_extraction()
        with patch("structured_parse.extract_structured", side_effect=RuntimeError("offline")):
            app.button[1].click().run()
        self.assert_no_previous_result(app)
        self.assertIn("page_html", app.session_state)
        # A normal rerun must not resurrect stale output, and the captured page
        # remains available for a later successful request.
        app.run()
        self.assertNotIn("extraction_document", app.session_state)
        self.assertEqual(len(app.dataframe), 0)
        with patch(
            "structured_parse.extract_structured",
            return_value=StructuredResult([], 1, 1),
        ):
            app.button[1].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["extraction_document"]["status"], "empty")

    def test_capture_failure_exposes_diagnostics_without_extraction_source(self):
        from streamlit.testing.v1 import AppTest

        from scrape import ScrapeResult

        app = AppTest.from_file(
            str(Path(__file__).resolve().parents[1] / "main.py"), default_timeout=20
        ).run()
        app.text_input[0].set_value("https://example.com")
        with patch(
            "scrape.scrape_page",
            return_value=ScrapeResult(
                "failed", "https://example.com", error_code="content_timeout"
            ),
        ):
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("page_html", app.session_state)
        self.assertEqual(
            app.session_state["capture_document"]["error_code"], "content_timeout"
        )
        self.assertEqual(app.get("download_button")[0].label, "Download capture report")


if __name__ == "__main__":
    unittest.main()
