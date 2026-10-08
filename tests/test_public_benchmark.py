"""Reference associations and immutable-input checks, not benchmark accuracy evidence."""

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.public_benchmark import evaluate, region


class PublicBenchmarkTests(unittest.TestCase):
    def test_reference_joins_fields_within_the_same_record_and_bounds_scope(self):
        case = {
            "scope_selector": ".record",
            "limit": 2,
            "fields": {"name": ".name", "price": ".price"},
        }
        html = '<div class="record"><b class="name">Ada</b><i class="price">1</i></div><div class="record"><b class="name">Bo</b><i class="price">2</i></div><div class="record"><b class="name">Ignore</b></div>'
        scoped, refs = region(html, case)
        self.assertEqual(
            refs, [{"name": "Ada", "price": "1"}, {"name": "Bo", "price": "2"}]
        )
        self.assertNotIn("Ignore", scoped)
        with self.assertRaises(ValueError):
            region('<div class="record"></div>', case)

    def test_mutated_snapshot_is_rejected_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "snapshot.html").write_text("changed")
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "snapshot": "snapshot.html",
                                "snapshot_sha256": "not_the_hash",
                            }
                        ]
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "snapshot changed"):
                evaluate(root, root / "output", "model")
            self.assertFalse((root / "output").exists())


class ReviewRegressionTests(unittest.TestCase):
    def run_benchmark(self, root, live_html=None):
        import importlib.metadata
        import io
        from contextlib import ExitStack
        from unittest.mock import patch

        import evaluation.public_benchmark as benchmark
        from evaluation.benchmark import sha
        from scrape import ScrapeResult
        from structured_parse import StructuredResult

        dataset = root / "dataset"
        dataset.mkdir()
        html = '<div class="record"><b class="name">Ada</b><i class="price">1</i></div>'
        scoped, expected = region(
            html,
            {
                "scope_selector": ".record",
                "limit": 1,
                "fields": {"name": ".name", "price": ".price"},
            },
        )
        (dataset / "snapshot.html").write_text(scoped)
        case = {
            "id": "fixture",
            "url": "https://example.com",
            "selector": ".record",
            "scope_selector": ".record",
            "limit": 1,
            "fields": {"name": ".name", "price": ".price"},
            "snapshot": "snapshot.html",
            "snapshot_sha256": sha(dataset / "snapshot.html"),
            "expected": expected,
        }
        (dataset / "manifest.json").write_text(
            json.dumps({"scope": "unit fixture, not public evidence", "cases": [case]})
        )

        def versions(name):
            if name in ("selenium", "streamlit"):
                raise importlib.metadata.PackageNotFoundError(name)
            return "test-version"

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "evaluation.public_benchmark.urllib.request.urlopen",
                    return_value=io.StringIO(
                        json.dumps({"models": [{"name": "fake", "digest": "fixture"}]})
                    ),
                )
            )
            stack.enter_context(
                patch(
                    "evaluation.public_benchmark.importlib.metadata.version",
                    side_effect=versions,
                )
            )
            stack.enter_context(
                patch.multiple(
                    benchmark.config, OLLAMA_MODEL="fake", OLLAMA_FALLBACK_MODEL="fake"
                )
            )
            stack.enter_context(patch("evaluation.public_benchmark.time.sleep"))
            extractor = stack.enter_context(
                patch(
                    "evaluation.public_benchmark.extract_structured",
                    return_value=StructuredResult([], 1, 1),
                )
            )
            if live_html is not None:
                stack.enter_context(
                    patch(
                        "evaluation.public_benchmark.scrape_page",
                        return_value=ScrapeResult(
                            "success", case["url"], html=live_html
                        ),
                    )
                )
            report = evaluate(
                dataset,
                root / "out",
                "fake",
                mode="live" if live_html is not None else "frozen",
            )
        return report, extractor.call_count, root / "out/report.json"

    def test_frozen_report_finishes_without_selenium_or_streamlit_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            report, calls, path = self.run_benchmark(Path(tmp))
            self.assertTrue(path.exists())
            self.assertEqual(calls, 1)
            self.assertIsNone(report["runtime"]["packages"]["streamlit"])
            self.assertIsNone(report["runtime"]["packages"]["selenium"])
            self.assertIn("evaluation/benchmark.py", report["code_sha256"])
            self.assertIn("config.py", report["code_sha256"])
            self.assertIn("browser_driver.py", report["code_sha256"])
            self.assertEqual(report["effective_settings"]["primary_model"], "fake")

    def test_structural_live_drift_is_excluded_without_calling_model(self):
        for changed in [
            "<main>No records</main>",
            '<div class="record"><b class="name">Ada</b></div>',
            '<div class="record"><b class="name">Ada</b><i class="price"></i></div>',
        ]:
            with self.subTest(html=changed), tempfile.TemporaryDirectory() as tmp:
                report, calls, _ = self.run_benchmark(Path(tmp), changed)
                self.assertEqual(calls, 0)
                case = report["cases"][0]
                self.assertTrue(case["reference_changed"])
                self.assertIsNone(case["scores"])
                self.assertEqual(case["error_code"], "reference_changed")
                self.assertEqual(report["aggregate"]["live"]["scored_cases"], 0)
                self.assertEqual(
                    report["aggregate"]["live"]["reference_changed_cases"], 1
                )


if __name__ == "__main__":
    unittest.main()
