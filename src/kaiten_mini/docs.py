"""API reference extracted from the developers.kaiten.ru JS bundle.

Kaiten does not publish OpenAPI/$metadata, but the docs site (Next.js) embeds
the whole reference in its ``_app`` chunk as ``JSON.parse('...')`` literals:
entities with operations (method, path, pathParams, request schema, response
examples). This module fetches that chunk and parses the literals back out.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from kaiten_mini.client import _proxy_from_env

DOCS_HOME = "https://developers.kaiten.ru/"
CACHE_TTL = 24 * 3600

_APP_CHUNK_RE = re.compile(r"/_next/static/chunks/pages/_app-[^\"']+\.js")
_JSON_BLOB_RE = re.compile(r"JSON\.parse\('((?:[^'\\]|\\.)*)'\)")

_SIMPLE_ESCAPES = {"'": "'", '"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f"}


def _unescape_js_string(s: str) -> str:
    """Decode a JS single-quoted string literal body ('\\'', '\\\\', '\\n', '\\uXXXX')."""
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "u" and i + 5 < len(s) + 1:
                hexpart = s[i + 2 : i + 6]
                try:
                    out.append(chr(int(hexpart, 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            if nxt == "x" and i + 3 < len(s) + 1:
                hexpart = s[i + 2 : i + 4]
                try:
                    out.append(chr(int(hexpart, 16)))
                    i += 4
                    continue
                except ValueError:
                    pass
            if nxt in _SIMPLE_ESCAPES:
                out.append(_SIMPLE_ESCAPES[nxt])
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _extract_entities(js: str) -> list[dict[str, Any]]:
    entities = []
    for blob in _JSON_BLOB_RE.findall(js):
        try:
            obj = json.loads(_unescape_js_string(blob))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("operations"), list):
            entities.append(obj)
    return entities


def _cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kaiten-mini" / "docs.json"


def load_entities(*, refresh: bool = False) -> list[dict[str, Any]]:
    cache = _cache_path()
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))["entities"]
        except (json.JSONDecodeError, KeyError):
            pass
    with httpx.Client(timeout=60.0, proxy=_proxy_from_env(), follow_redirects=True) as http:
        html = http.get(DOCS_HOME).text
        match = _APP_CHUNK_RE.search(html)
        if not match:
            raise ValueError("docs site layout changed: _app chunk not found on " + DOCS_HOME)
        js = http.get(DOCS_HOME.rstrip("/") + match.group(0)).text
    entities = _extract_entities(js)
    if not entities:
        raise ValueError("docs site layout changed: no embedded entities found in " + match.group(0))
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"source": match.group(0), "entities": entities}, ensure_ascii=False), encoding="utf-8")
    return entities


def _matches(text: str, query: str) -> bool:
    return query.lower() in (text or "").lower()


def _is_rest_op(op: dict[str, Any]) -> bool:
    # webhook event docs also ship as "operations" but carry no method/path
    return bool(op.get("type") and op.get("path"))


def search_operations(entities: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """REST operations whose entity name, operation name or path contains the query."""
    hits = []
    for entity in entities:
        for op in entity.get("operations", []):
            if not _is_rest_op(op):
                continue
            if (
                _matches(entity.get("name", ""), query)
                or _matches(op.get("name", ""), query)
                or _matches(op.get("path", ""), query)
            ):
                hits.append(
                    {
                        "entity": entity.get("name"),
                        "operation": op.get("name"),
                        "method": op.get("type"),
                        "path": op.get("path"),
                        "beta": entity.get("isBeta", False),
                    }
                )
    return hits


def operation_details(entities: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Full REST operation objects (request schema, response examples) matching the query."""
    hits = []
    for entity in entities:
        for op in entity.get("operations", []):
            if not _is_rest_op(op):
                continue
            if (
                _matches(entity.get("name", ""), query)
                or _matches(op.get("name", ""), query)
                or _matches(op.get("path", ""), query)
            ):
                hits.append({"entity": entity.get("name"), **op})
    return hits
