"""Bounded browser capture with structured outcomes and compatibility HTML wrapper."""

import hashlib
import json
import math
import multiprocessing
import os
import signal
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from content import clean_body_content as clean_body_content
from content import extract_body_content as extract_body_content
from content import split_dom_content as split_dom_content
from utils import validate_url


@dataclass(frozen=True)
class ScrapeOptions:
    content_selector: str | None = None
    navigation_timeout: float = 12
    content_timeout: float = 10
    overall_timeout: float = 40
    stable_seconds: float = 0.75
    attempts: int = 2
    retry_delay: float = 0.5
    headless: bool = True
    max_html_chars: int = 2_000_000

    def validate(self):
        for name in (
            "navigation_timeout",
            "content_timeout",
            "overall_timeout",
            "stable_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(
                    "Timeouts and stability window must be finite and positive"
                )
        if (
            not isinstance(self.attempts, int)
            or isinstance(self.attempts, bool)
            or not 1 <= self.attempts <= 3
        ):
            raise ValueError("Attempts must be 1–3")
        if self.retry_delay < 0 or not math.isfinite(self.retry_delay):
            raise ValueError("Retry delay must be finite and non-negative")
        if self.content_selector is not None and (
            not isinstance(self.content_selector, str)
            or not self.content_selector.strip()
        ):
            raise ValueError("Content selector must be a non-empty CSS selector")
        if not isinstance(self.max_html_chars, int) or self.max_html_chars <= 0:
            raise ValueError("HTML limit must be a positive integer")
        if type(self.headless) is not bool:
            raise ValueError("headless must be boolean")


@dataclass
class ScrapeResult:
    status: str
    requested_url: str
    final_url: str | None = None
    html: str = ""
    error_code: str | None = None
    elapsed_seconds: float = 0
    attempts: list = field(default_factory=list)
    artifacts: dict = field(default_factory=dict)
    browser_version: str | None = None

    def as_dict(self):
        data = asdict(self)
        data.pop("html")
        data["html_sha256"] = (
            hashlib.sha256(self.html.encode()).hexdigest() if self.html else None
        )
        data["html_characters"] = len(self.html)
        return data


class ScrapeError(RuntimeError):
    def __init__(self, result):
        self.result = result
        super().__init__(f"Browser capture failed: {result.error_code}")


def _origin(url):
    p = urlsplit(url)
    return p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80)


def _allowed(url, test_origin=None):
    # Exact loopback origin is injectable only by the controlled browser tests.
    if test_origin is not None:
        return (
            _origin(url) == tuple(test_origin)
            and _origin(url)[1] == "127.0.0.1"
            and not urlsplit(url).username
            and not urlsplit(url).password
        )
    return validate_url(url)


READY_SCRIPT = """
const selector = arguments[0];
let nodes;
try { nodes = selector ? [...document.querySelectorAll(selector)] :
  [...document.querySelectorAll('main, article, [role="main"]')]; }
catch (_) { return {invalid_selector: true}; }
const candidates = nodes.length ? nodes : (selector ? [] : [document.body]);
return candidates.filter(n => n && getComputedStyle(n).display !== 'none' &&
  getComputedStyle(n).visibility !== 'hidden').map(n => (n.innerText || '').trim()).join('\\n').trim();
"""


def _capture_once(url, options, directory, test_origin=None, driver_factory=None):
    """Child-only browser work; the parent supervises a hard overall deadline."""
    result = {
        "status": "failed",
        "final_url": None,
        "html": "",
        "error_code": None,
        "artifacts": {},
        "browser_version": None,
    }
    driver = None
    try:
        if not _allowed(url, test_origin):
            result["error_code"] = "invalid_url"
            return result
        if driver_factory is None:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            chrome = Options()
            chrome.page_load_strategy = "eager"
            if options.headless:
                chrome.add_argument("--headless=new")
            chrome.add_argument("--window-size=1920,1080")
            chrome.add_argument("--disable-dev-shm-usage")
            if os.getenv("CHROME_BINARY"):
                chrome.binary_location = os.environ["CHROME_BINARY"]
            service = (
                Service(executable_path=os.environ["CHROMEDRIVER"])
                if os.getenv("CHROMEDRIVER")
                else Service()
            )
            driver = webdriver.Chrome(options=chrome, service=service)
        else:
            driver = driver_factory()
        result["browser_version"] = driver.capabilities.get("browserVersion")
        driver.set_page_load_timeout(options.navigation_timeout)
        driver.set_script_timeout(min(options.content_timeout, 5))
        from selenium.common.exceptions import TimeoutException

        try:
            driver.get(url)
        except TimeoutException:
            result["error_code"] = "navigation_timeout"
            return result
        result["final_url"] = driver.current_url
        if not _allowed(result["final_url"], test_origin):
            result["error_code"] = "blocked_redirect"
            return result
        limit = time.monotonic() + options.content_timeout
        previous = None
        stable_since = None
        saw_content = False
        while time.monotonic() < limit:
            current_url = driver.current_url
            if current_url != result["final_url"]:
                result["final_url"] = current_url
                if not _allowed(current_url, test_origin):
                    result["error_code"] = "blocked_redirect"
                    return result
                previous = stable_since = None
            text = driver.execute_script(READY_SCRIPT, options.content_selector)
            if isinstance(text, dict) and text.get("invalid_selector"):
                result["error_code"] = "invalid_selector"
                return result
            if text:
                saw_content = True
                if text != previous:
                    previous, stable_since = text, time.monotonic()
                elif time.monotonic() - stable_since >= options.stable_seconds:
                    html = driver.page_source
                    if len(html) > options.max_html_chars:
                        result["error_code"] = "html_limit"
                    else:
                        result.update(status="success", html=html)
                    return result
            else:
                previous = stable_since = None
            time.sleep(0.1)
        result["error_code"] = (
            "content_timeout"
            if saw_content or options.content_selector
            else "empty_content"
        )
    except Exception as error:
        name = type(error).__name__
        result["error_code"] = (
            "invalid_selector"
            if name in ("InvalidSelectorException", "JavascriptException")
            else "network_error"
            if "net::ERR_" in str(error)
            else "browser_error"
        )
        result["exception_type"] = name
    finally:
        if driver is not None:
            for key, filename in [("html", "page.html"), ("screenshot", "page.png")]:
                try:
                    path = directory / filename
                    if key == "html":
                        path.write_text(driver.page_source[: options.max_html_chars])
                    else:
                        driver.save_screenshot(str(path))
                    if path.exists():
                        result["artifacts"][key] = str(path)
                except Exception:
                    pass
            try:
                driver.quit()
            except Exception:
                pass
    return result


def _worker(url, values, directory, test_origin):
    directory = Path(directory)
    if os.name == "posix":
        os.setsid()
        (directory / "process-group-ready").write_text(str(os.getpid()))
    result = _capture_once(url, ScrapeOptions(**values), directory, test_origin)
    temporary = directory / "result.tmp"
    temporary.write_text(json.dumps(result, allow_nan=False))
    temporary.replace(directory / "result.json")


def _stop(process, directory):
    if os.name == "posix" and (directory / "process-group-ready").exists():
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                # Darwin can report EPERM after the terminated group disappears.
                # A still-live direct worker must nevertheless be killed.
                if process.is_alive():
                    process.kill()
            process.join(0.15)
    elif os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
        )
    elif process.is_alive():
        process.kill()
    process.join(0.2)
    process.close()


def scrape_page(url, options=None, artifact_dir=None, *, _test_origin=None):
    options = options or ScrapeOptions()
    options.validate()
    root = Path(artifact_dir or Path("runs/browser") / uuid.uuid4().hex).resolve()
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    deadline = started + options.overall_timeout
    attempts = []
    last = {"status": "failed", "html": "", "error_code": "overall_timeout"}
    ctx = multiprocessing.get_context("spawn")
    for index in range(1, options.attempts + 1):
        if time.monotonic() >= deadline:
            break
        directory = root / f"attempt-{index}"
        directory.mkdir()
        process = ctx.Process(
            target=_worker, args=(url, asdict(options), str(directory), _test_origin)
        )
        process.start()
        try:
            while (
                time.monotonic() < deadline
                and process.is_alive()
                and not (directory / "result.json").exists()
            ):
                time.sleep(0.05)
            if (directory / "result.json").exists():
                last = json.loads((directory / "result.json").read_text())
            else:
                last = {
                    "status": "failed",
                    "html": "",
                    "error_code": "overall_timeout"
                    if time.monotonic() >= deadline
                    else "worker_crash",
                }
        finally:
            _stop(process, directory)
        attempts.append(
            {
                "attempt": index,
                "status": last["status"],
                "error_code": last.get("error_code"),
                "artifacts": last.get("artifacts", {}),
            }
        )
        if last["status"] == "success" or last.get("error_code") not in (
            "navigation_timeout",
            "content_timeout",
            "browser_error",
            "network_error",
            "worker_crash",
        ):
            break
        remaining = deadline - time.monotonic()
        if remaining <= options.retry_delay:
            last["error_code"] = "overall_timeout"
            break
        time.sleep(options.retry_delay)
    result = ScrapeResult(
        status=last["status"],
        requested_url=url,
        final_url=last.get("final_url"),
        html=last.get("html", ""),
        error_code=last.get("error_code"),
        elapsed_seconds=time.monotonic() - started,
        attempts=attempts,
        artifacts=last.get("artifacts", {}),
        browser_version=last.get("browser_version"),
    )
    (root / "capture.json").write_text(
        json.dumps(result.as_dict(), indent=2, allow_nan=False) + "\n"
    )
    return result


def scrape_website(website, wait_time=None, headless=True):
    """Compatibility API. wait_time is now a content deadline, never fixed sleep."""
    options = ScrapeOptions(
        headless=headless,
        **({"content_timeout": wait_time} if wait_time is not None else {}),
    )
    result = scrape_page(website, options)
    if result.status != "success":
        raise ScrapeError(result)
    return result.html
