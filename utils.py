"""Utility functions for the Automatic Web Scraper."""

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse


def setup_logging(level="INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def validate_url(url):
    """Allow HTTP(S) sites that resolve only to public addresses.

    This is a local safety check, not a substitute for network egress controls
    when the application is deployed as a public service.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host:
            return False
        if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
            return False
        normalized_host = host.rstrip(".").lower()
        if normalized_host == "localhost" or normalized_host.endswith(
            (".localhost", ".local", ".internal", ".test")
        ):
            return False
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80),
                                       type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(item[4][0].split("%", 1)[0]).is_global
            for item in addresses
        )
    except (ValueError, OSError, TypeError):
        return False


def format_time(seconds):
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    if seconds < 3600:
        return f"{seconds / 60:.1f} minutes"
    return f"{seconds / 3600:.1f} hours"


def extract_domain(url):
    try:
        return urlparse(url).netloc
    except ValueError:
        return "unknown"


def clean_text(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s\.,!?;:()\-]", "", text)
    return text.strip()


def estimate_reading_time(text, words_per_minute=200):
    minutes = len(text.split()) / words_per_minute
    if minutes < 1:
        return "< 1 minute"
    if minutes < 60:
        return f"{minutes:.0f} minutes"
    return f"{minutes / 60:.1f} hours"
