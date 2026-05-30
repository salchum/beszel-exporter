from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PocketBaseError(RuntimeError):
    """Raised when PocketBase returns an error or an invalid response."""


@dataclass
class PocketBaseClient:
    hub_url: str
    token: str | None = None
    timeout: int = 30
    verify_tls: bool = True
    ca_file: Path | None = None

    def __post_init__(self) -> None:
        self.hub_url = self.hub_url.rstrip("/")
        self._ssl_context = self._build_ssl_context()

    def authenticate(self, email: str, password: str) -> None:
        response = self._request_json(
            "POST",
            "/api/collections/users/auth-with-password",
            body={"identity": email, "password": password},
            authenticated=False,
        )
        token = response.get("token")
        if not isinstance(token, str) or not token:
            raise PocketBaseError("authentication response did not include a token")
        self.token = token

    def fetch_system_stats(
        self,
        system_id: str,
        start: str,
        end: str,
        per_page: int = 200,
        record_type: str | None = None,
    ) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []
        page = 1
        filters = [
            f'system = "{escape_filter_value(system_id)}"',
            f'created >= "{escape_filter_value(start)}"',
            f'created <= "{escape_filter_value(end)}"',
        ]
        if record_type is not None:
            filters.append(f'type = "{escape_filter_value(record_type)}"')
        filter_expr = " && ".join(filters)

        while True:
            query = urlencode(
                {
                    "page": page,
                    "perPage": per_page,
                    "sort": "created",
                    "filter": filter_expr,
                }
            )
            response = self._request_json("GET", f"/api/collections/system_stats/records?{query}")
            items = response.get("items")
            if not isinstance(items, list):
                raise PocketBaseError("records response did not include an items list")
            all_records.extend(items)

            total_pages = response.get("totalPages", page)
            if not isinstance(total_pages, int):
                raise PocketBaseError("records response included an invalid totalPages value")
            if page >= total_pages:
                break
            page += 1

        return all_records

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if authenticated:
            if not self.token:
                raise PocketBaseError("client is not authenticated")
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(
            f"{self.hub_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout, context=self._ssl_context) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise PocketBaseError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise PocketBaseError(str(exc.reason)) from exc

        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PocketBaseError("response was not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise PocketBaseError("response JSON was not an object")
        return decoded

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if self.hub_url.startswith("http://"):
            return None
        if not self.verify_tls:
            return ssl._create_unverified_context()
        if self.ca_file is not None:
            return ssl.create_default_context(cafile=str(self.ca_file))
        return None


def escape_filter_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
