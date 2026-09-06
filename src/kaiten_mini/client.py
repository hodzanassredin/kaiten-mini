"""Minimal synchronous client for the Kaiten REST API."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

API_VERSION = "latest"
DEFAULT_BASE_DOMAIN = "kaiten.ru"
MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _proxy_from_env() -> str | None:
    """ALL_PROXY with the ``socks://`` scheme rewritten to ``socks5h://``.

    httpx understands ``socks5://`` / ``socks5h://`` but not the bare ``socks://``
    that some environments export (e.g. local ALL_PROXY=socks://127.0.0.1:12345);
    an explicit proxy kwarg also stops httpx from re-reading proxy env vars.
    """
    proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")
    if proxy and proxy.startswith("socks://"):
        return "socks5h://" + proxy[len("socks://"):]
    return proxy


class KaitenApiError(Exception):
    """Non-2xx answer from Kaiten."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def normalize_base_url(base_url: str) -> str:
    """Turn any reasonable host spelling into the ``.../api/latest`` root."""
    parsed = urlsplit(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"base URL must be absolute (https://host), got: {base_url!r}")
    path = parsed.path.rstrip("/")
    suffix = f"/api/{API_VERSION}"
    if not path.endswith(suffix):
        path = f"{path}/{API_VERSION}" if path.endswith("/api") else path + suffix
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def build_base_url(
    subdomain: str | None,
    base_domain: str = DEFAULT_BASE_DOMAIN,
    base_url: str | None = None,
) -> str:
    if base_url:
        return normalize_base_url(base_url)
    if not subdomain:
        raise ValueError(
            "Kaiten host is not configured: pass --subdomain / KAITEN_SUBDOMAIN "
            "or --base-url / KAITEN_BASE_URL"
        )
    for name, value in (("subdomain", subdomain), ("base_domain", base_domain)):
        if "://" in value or "/" in value:
            raise ValueError(f"{name} must be a bare hostname component, got: {value!r}")
    return normalize_base_url(f"https://{subdomain}.{base_domain}")


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:500] or resp.reason_phrase
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            if isinstance(body.get(key), str):
                return body[key]
    return str(body)[:500]


class KaitenClient:
    def __init__(self, base_url: str, token: str):
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30.0,
            proxy=_proxy_from_env(),
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp: httpx.Response | None = None
        for attempt in range(MAX_RETRIES):
            resp = self._http.request(method, path, **kwargs)
            if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            break
        assert resp is not None
        if resp.status_code >= 400:
            raise KaitenApiError(resp.status_code, _error_message(resp))
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params={k: v for k, v in (params or {}).items() if v is not None} or None)

    def post(self, path: str, body: dict) -> Any:
        return self._request("POST", path, json=body)

    def patch(self, path: str, body: dict) -> Any:
        return self._request("PATCH", path, json=body)

    def put(self, path: str, body: dict) -> Any:
        return self._request("PUT", path, json=body)

    def upload(self, method: str, path: str, file_path: str, field: str = "file") -> Any:
        with open(file_path, "rb") as f:
            return self._request(method, path, files={field: (os.path.basename(file_path), f)})

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)

    def close(self) -> None:
        self._http.close()
