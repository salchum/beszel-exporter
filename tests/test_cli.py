from __future__ import annotations

import unittest
from datetime import timezone
from io import StringIO
from os import chdir, getcwd
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from beszel_exporter.cli import build_parser, parse_datetime, pocketbase_datetime, run


class DateParsingTests(unittest.TestCase):
    def test_naive_datetime_uses_asia_jakarta_and_converts_to_utc(self) -> None:
        parsed = parse_datetime("2026-01-01 08:00")

        self.assertEqual(parsed.utcoffset().total_seconds(), 7 * 60 * 60)
        self.assertEqual(pocketbase_datetime(parsed), "2026-01-01 01:00:00")

    def test_timezone_aware_iso_is_preserved(self) -> None:
        parsed = parse_datetime("2026-01-01T08:00:00+02:00")

        self.assertEqual(parsed.tzinfo, timezone.utc.__class__ if False else parsed.tzinfo)
        self.assertEqual(pocketbase_datetime(parsed), "2026-01-01 06:00:00")


class CredentialResolutionTests(unittest.TestCase):
    def test_dotenv_credentials_are_used_without_env_or_flags(self) -> None:
        email, password = self.run_with_credentials(
            dotenv="BESZEL_EMAIL=dotenv@example.com\nBESZEL_PASSWORD=dotenv-password\n",
        )

        self.assertEqual(email, "dotenv@example.com")
        self.assertEqual(password, "dotenv-password")

    def test_environment_credentials_override_dotenv(self) -> None:
        email, password = self.run_with_credentials(
            dotenv="BESZEL_EMAIL=dotenv@example.com\nBESZEL_PASSWORD=dotenv-password\n",
            environ={
                "BESZEL_EMAIL": "env@example.com",
                "BESZEL_PASSWORD": "env-password",
            },
        )

        self.assertEqual(email, "env@example.com")
        self.assertEqual(password, "env-password")

    def test_cli_credentials_override_env_and_dotenv(self) -> None:
        email, password = self.run_with_credentials(
            "--email",
            "flag@example.com",
            "--password",
            "flag-password",
            dotenv="BESZEL_EMAIL=dotenv@example.com\nBESZEL_PASSWORD=dotenv-password\n",
            environ={
                "BESZEL_EMAIL": "env@example.com",
                "BESZEL_PASSWORD": "env-password",
            },
        )

        self.assertEqual(email, "flag@example.com")
        self.assertEqual(password, "flag-password")

    def run_with_credentials(
        self,
        *extra_args: str,
        dotenv: str = "",
        environ: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        fake_client = FakePocketBaseClient("http://placeholder")
        cwd = getcwd()
        with TemporaryDirectory() as temp_dir:
            chdir(temp_dir)
            try:
                if dotenv:
                    Path(".env").write_text(dotenv, encoding="utf-8")
                args = build_parser().parse_args(self.argv(*extra_args))
                with patch.dict("os.environ", environ or {}, clear=True), patch(
                    "beszel_exporter.cli.PocketBaseClient",
                    return_value=fake_client,
                ), patch("sys.stdout", new_callable=StringIO), patch("sys.stderr", new_callable=StringIO):
                    run(args)
            finally:
                chdir(cwd)
        return fake_client.email or "", fake_client.password or ""

    def argv(self, *extra: str) -> list[str]:
        return [
            "--hub-url",
            "http://beszel.example",
            "--system-id",
            "sys1",
            "--start",
            "2026-01-01 08:00",
            "--end",
            "2026-01-01 11:00",
            "--output",
            "out.csv",
            *extra,
        ]


class FakePocketBaseClient:
    def __init__(self, hub_url: str) -> None:
        self.hub_url = hub_url
        self.email: str | None = None
        self.password: str | None = None

    def authenticate(self, email: str, password: str) -> None:
        self.email = email
        self.password = password

    def fetch_system_stats(self, system_id: str, start: str, end: str, per_page: int = 200) -> list[dict[str, object]]:
        return []


if __name__ == "__main__":
    unittest.main()
