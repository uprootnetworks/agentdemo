import io
import unittest
import urllib.error
from email.message import Message
from unittest.mock import patch

import netcheck


class Response(io.BytesIO):
    def __init__(self, data, content_type="text/plain"):
        super().__init__(data)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


class NetcheckTests(unittest.TestCase):
    def fetch_with(self, data, content_type="text/plain"):
        with patch("netcheck.urllib.request.build_opener") as factory:
            factory.return_value.open.return_value = Response(data, content_type)
            result = netcheck.fetch_notes()
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, netcheck.PROFILE_URL)
            self.assertEqual(factory.return_value.open.call_args.kwargs["timeout"], 10)
            return result

    def test_notes_are_returned_as_text(self):
        self.assertEqual(self.fetch_with(b"bash scripts/finish-setup.sh"), "bash scripts/finish-setup.sh")

    def test_html_is_rejected(self):
        with self.assertRaises(ValueError):
            self.fetch_with(b"<html>not the profile</html>", "text/html")

    def test_oversized_response_is_rejected(self):
        with self.assertRaises(ValueError):
            self.fetch_with(b"x" * (netcheck.MAX_BYTES + 1))

    def test_terminal_escape_is_removed(self):
        self.assertNotIn("\x1b", self.fetch_with(b"\x1b[2Jnotes"))

    def test_redirect_is_not_followed(self):
        handler = netcheck.NoRedirects()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://example.org"))

    def test_report_counts_failures(self):
        result = netcheck.summarize([
            {"destination": "support.example", "status": "ok"},
            {"destination": "support.example", "status": "dns_timeout"},
        ])
        self.assertIn("support.example: 1/2 failed (50%)", result)
        self.assertIn("dns_timeout: 1", result)

    def test_invalid_sample_is_rejected(self):
        with self.assertRaises(ValueError):
            netcheck.summarize([{"destination": "support.example", "status": "unknown"}])


if __name__ == "__main__":
    unittest.main()
