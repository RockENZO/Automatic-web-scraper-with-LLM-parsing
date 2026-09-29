import socket
import unittest
from unittest.mock import patch

from utils import validate_url


def answers(*addresses):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
            for address in addresses]


class UrlValidationTests(unittest.TestCase):
    @patch("utils.socket.getaddrinfo", return_value=answers("8.8.8.8"))
    def test_public_https_allowed(self, resolver):
        self.assertTrue(validate_url("https://example.com/article"))
        resolver.assert_called_once()

    @patch("utils.socket.getaddrinfo", return_value=answers("8.8.8.8", "127.0.0.1"))
    def test_mixed_public_private_addresses_blocked(self, resolver):
        self.assertFalse(validate_url("https://example.com"))

    def test_local_and_non_http_urls_blocked(self):
        for url in ("file:///etc/passwd", "http://localhost:8000/",
                    "https://printer.local", "http://127.0.0.1/",
                    "https://user:pass@example.com", "http://example.com:8080/"):
            with self.subTest(url=url):
                self.assertFalse(validate_url(url))

    @patch("utils.socket.getaddrinfo", side_effect=OSError("DNS failure"))
    def test_dns_failure_blocked(self, resolver):
        self.assertFalse(validate_url("https://example.com"))


if __name__ == "__main__":
    unittest.main()
