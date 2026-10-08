"""Share a verified setup-tool driver with normal browser capture."""

import json
import os
import shutil
import subprocess
from pathlib import Path

DRIVER_RECORD = Path(__file__).resolve().parent / "runs/chromedriver.json"


def get_chrome_version():
    paths = [
        os.getenv("CHROME_BINARY"),
        shutil.which("google-chrome"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for path in paths:
        if path and Path(path).is_file():
            try:
                return subprocess.check_output(
                    [path, "--version"], text=True, timeout=3
                ).strip()
            except (OSError, subprocess.SubprocessError):
                continue
    return None


def _major(version):
    import re

    match = re.search(r"(\d+)\.", version or "")
    return match.group(1) if match else None


def save_verified_driver(path, browser_version, record_path=None):
    path = Path(path).resolve()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Verified driver executable is missing")
    record = Path(record_path or DRIVER_RECORD)
    record.parent.mkdir(parents=True, exist_ok=True)
    temporary = record.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "driver_path": str(path),
                "browser_version": browser_version,
            },
            indent=2,
        )
        + "\n"
    )
    temporary.replace(record)


def resolve_driver(record_path=None):
    explicit = os.getenv("CHROMEDRIVER")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("CHROMEDRIVER does not identify an executable file")
        return str(path)
    record = Path(record_path or DRIVER_RECORD)
    if not record.exists():
        return None
    try:
        data = json.loads(record.read_text())
        path = Path(data["driver_path"])
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            return None
        installed, verified = (
            _major(get_chrome_version()),
            _major(data.get("browser_version")),
        )
        if not verified or (installed and installed != verified):
            return None
        return str(path)
    except (OSError, ValueError, KeyError, TypeError):
        return None
