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


if __name__ == "__main__":
    unittest.main()
