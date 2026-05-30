from __future__ import annotations

import json
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beszel_exporter.client import PocketBaseClient, escape_filter_value


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


class ClientTests(unittest.TestCase):
    def test_auth_and_paginated_fetch(self) -> None:
        requests = []

        def fake_urlopen(request, timeout, context=None):
            requests.append(request)
            if request.full_url.endswith("/api/collections/users/auth-with-password"):
                return FakeResponse({"token": "test-token"})
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            if "page=1" in request.full_url:
                return FakeResponse({"page": 1, "totalPages": 2, "items": [{"id": "one"}]})
            return FakeResponse({"page": 2, "totalPages": 2, "items": [{"id": "two"}]})

        client = PocketBaseClient("http://beszel.example")
        with patch("beszel_exporter.client.urlopen", side_effect=fake_urlopen):
            client.authenticate("user@example.com", "secret")
            records = client.fetch_system_stats(
                "sys1",
                "2026-01-01 01:00:00",
                "2026-01-01 04:00:00",
                per_page=1,
                record_type="1m",
            )

        self.assertEqual(records, [{"id": "one"}, {"id": "two"}])
        self.assertEqual(requests[0].full_url, "http://beszel.example/api/collections/users/auth-with-password")
        self.assertIn("/api/collections/system_stats/records?", requests[1].full_url)
        self.assertIn("sort=created", requests[1].full_url)
        self.assertIn("type+%3D+%221m%22", requests[1].full_url)

    def test_escape_filter_value(self) -> None:
        self.assertEqual(escape_filter_value('sys"\\1'), 'sys\\"\\\\1')

    def test_http_url_does_not_build_ssl_context(self) -> None:
        client = PocketBaseClient("http://beszel.example")

        self.assertIsNone(client._ssl_context)

    def test_insecure_https_builds_unverified_context(self) -> None:
        client = PocketBaseClient("https://beszel.example", verify_tls=False)

        self.assertIsInstance(client._ssl_context, ssl.SSLContext)
        self.assertFalse(client._ssl_context.check_hostname)
        self.assertEqual(client._ssl_context.verify_mode, ssl.CERT_NONE)

    def test_ca_file_builds_verified_context_with_custom_ca(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ca_file = Path(temp_dir) / "ca.pem"
            ca_file.write_text("not a real cert", encoding="utf-8")

            with patch("beszel_exporter.client.ssl.create_default_context") as create_context:
                PocketBaseClient("https://beszel.example", ca_file=ca_file)

        create_context.assert_called_once_with(cafile=str(ca_file))


if __name__ == "__main__":
    unittest.main()
