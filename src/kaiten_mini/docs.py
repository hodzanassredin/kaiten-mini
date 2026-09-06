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
from kaiten_mini.output import warn

DOCS_HOME = os.environ.get("KAITEN_MINI_DOCS_URL", "https://developers.kaiten.ru/")
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


def _bundled_cache_path() -> Path:
    # snapshot committed to the repo: last-known-good reference for the day the
    # docs site changes its bundle format and extraction breaks
    return Path(__file__).parent / "docs_cache.json"


def _read_cache(path: Path) -> list[dict[str, Any]] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))["entities"]
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def _fetch_entities() -> tuple[list[dict[str, Any]], str]:
    with httpx.Client(timeout=60.0, proxy=_proxy_from_env(), follow_redirects=True) as http:
        html = http.get(DOCS_HOME).text
        match = _APP_CHUNK_RE.search(html)
        if not match:
            raise ValueError("docs site layout changed: _app chunk not found on " + DOCS_HOME)
        js = http.get(DOCS_HOME.rstrip("/") + match.group(0)).text
    entities = _extract_entities(js)
    if not entities:
        raise ValueError("docs site layout changed: no embedded entities found in " + match.group(0))
    return entities, match.group(0)


def load_entities(*, refresh: bool = False) -> list[dict[str, Any]]:
    cache = _cache_path()
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        cached = _read_cache(cache)
        if cached is not None:
            return cached
    try:
        entities, source = _fetch_entities()
    except Exception as e:
        # fall back to whatever metadata we have rather than failing outright
        stale = _read_cache(cache)
        if stale is not None:
            warn(f"docs fetch failed ({e}); using the local cache from {cache} — metadata may be stale")
            return stale
        bundled = _read_cache(_bundled_cache_path())
        if bundled is not None:
            warn(f"docs fetch failed ({e}); using the cache bundled with kaiten-mini — metadata may be stale")
            return bundled
        raise
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"source": source, "entities": entities}, ensure_ascii=False), encoding="utf-8")
    return entities


def _matches(text: str, query: str) -> bool:
    return query.lower() in (text or "").lower()


def _is_rest_op(op: dict[str, Any]) -> bool:
    return bool(op.get("type") and op.get("path"))


def _is_event_op(op: dict[str, Any]) -> bool:
    # webhook event docs ship as "operations" too, but carry no method/path —
    # just the event name ("card:add") and a description (PROV: developers.kaiten.ru
    # bundle, checked 2026-09-06)
    return not _is_rest_op(op) and bool(op.get("name"))


def is_event_entity(entity: dict[str, Any]) -> bool:
    """Entity whose operations are all webhook events (no REST method/path).

    The bundle names these like plain domain objects ("Card", "Comment") with no
    "webhook" marker, so we recognize them by shape — this lets a "webhook"
    query match them.
    """
    ops = entity.get("operations") or []
    return bool(ops) and all(_is_event_op(op) for op in ops)


def search_operations(entities: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Operations whose entity name, operation name or path contains the query.

    Includes webhook events, labeled ``method == "EVENT"`` (no ``path``);
    event-only entities also match the query "webhook".
    """
    hits = []
    for entity in entities:
        entity_matches = _matches(entity.get("name", ""), query) or (
            is_event_entity(entity) and _matches("webhook", query)
        )
        for op in entity.get("operations", []):
            is_rest = _is_rest_op(op)
            if not is_rest and not _is_event_op(op):
                continue
            if entity_matches or _matches(op.get("name", ""), query) or _matches(op.get("path", ""), query):
                hits.append(
                    {
                        "entity": entity.get("name"),
                        "operation": op.get("name"),
                        "method": op.get("type") if is_rest else "EVENT",
                        "path": op.get("path"),
                        "beta": entity.get("isBeta", False),
                    }
                )
    return hits


def operation_details(entities: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Full operation objects (request schema, response examples) matching the query.

    Webhook events match too — they carry only name/description, no schemas.
    """
    hits = []
    for entity in entities:
        entity_matches = _matches(entity.get("name", ""), query) or (
            is_event_entity(entity) and _matches("webhook", query)
        )
        for op in entity.get("operations", []):
            if not _is_rest_op(op) and not _is_event_op(op):
                continue
            if entity_matches or _matches(op.get("name", ""), query) or _matches(op.get("path", ""), query):
                hits.append({"entity": entity.get("name"), **op})
    return hits
