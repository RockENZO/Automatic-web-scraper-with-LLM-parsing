"""Verified setup state is consumed by capture; explicit overrides retain priority."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from browser_driver import resolve_driver
from setup_chromedriver import setup_chromedriver


class DriverTests(unittest.TestCase):
    def test_setup_persists_verified_path_and_resolver_reuses_it(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, {}, clear=True),
        ):
            path = Path(tmp) / "driver"
            path.write_text("fixture")
            path.chmod(0o700)
            record = Path(tmp) / "state.json"
            driver = MagicMock()
            driver.capabilities = {"browserVersion": "154.0.1"}
            self.assertTrue(
                setup_chromedriver(
                    driver_installer=lambda: str(path),
                    driver_factory=lambda p: driver,
                    version_reader=lambda: "Chrome 154.0.1",
                    record_path=record,
                )
            )
            driver.get.assert_called_once_with("about:blank")
            driver.quit.assert_called_once()
            with patch(
                "browser_driver.get_chrome_version", return_value="Chrome 154.0.9"
            ):
                self.assertEqual(resolve_driver(record), str(path.resolve()))
            with patch(
                "browser_driver.get_chrome_version", return_value="Chrome 155.0.1"
            ):
                self.assertIsNone(resolve_driver(record))
            with patch.dict(os.environ, {"CHROMEDRIVER": str(path)}):
                self.assertEqual(
                    resolve_driver(Path(tmp) / "absent"), str(path.resolve())
                )
            path.unlink()
            self.assertIsNone(resolve_driver(record))

    def test_failed_setup_does_not_persist_a_success_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "state.json"
            driver = MagicMock()
            driver.get.side_effect = RuntimeError("cannot start")
            self.assertFalse(
                setup_chromedriver(
                    driver_installer=lambda: "missing",
                    driver_factory=lambda p: driver,
                    version_reader=lambda: "Chrome 154.0.1",
                    record_path=record,
                )
            )
            self.assertFalse(record.exists())
            driver.quit.assert_called_once()
