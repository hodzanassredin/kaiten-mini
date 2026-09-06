"""User knowledge base at faq-ru.kaiten.site: sitemap search and article fetch.

The KB has 860+ articles with human-readable transliterated slugs
(``integraciya-s-github-dopolnenie``), and its pages are server-rendered enough
to be read with a plain GET — no JS execution needed. The sitemap is cached
locally (same TTL strategy as the API docs).
"""

from __future__ import annotations

import html
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

from kaiten_mini.client import _proxy_from_env
from kaiten_mini.output import warn

KB_HOME = os.environ.get("KAITEN_MINI_KB_URL", "https://faq-ru.kaiten.site")
CACHE_TTL = 24 * 3600

_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _cache_path() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "kaiten-mini" / "kb_sitemap.xml"


def _fetch_sitemap() -> str:
    with httpx.Client(timeout=30.0, proxy=_proxy_from_env(), follow_redirects=True) as http:
        resp = http.get(KB_HOME.rstrip("/") + "/sitemap.xml")
        resp.raise_for_status()
        return resp.text


def load_sitemap(*, refresh: bool = False) -> list[str]:
    """Article URLs from the KB sitemap, with a 24h local cache."""
    cache = _cache_path()
    if not refresh and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        return _LOC_RE.findall(cache.read_text(encoding="utf-8"))
    try:
        text = _fetch_sitemap()
    except Exception as e:
        if cache.exists():
            warn(f"KB sitemap fetch failed ({e}); using the local cache from {cache} — it may be stale")
            return _LOC_RE.findall(cache.read_text(encoding="utf-8"))
        raise
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return _LOC_RE.findall(text)


def search_articles(query: str, *, refresh: bool = False) -> list[dict[str, str]]:
    """Articles whose URL slug contains the query (slugs are transliterated Russian)."""
    hits = []
    for url in load_sitemap(refresh=refresh):
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if query.lower() in slug.lower():
            hits.append({"slug": slug, "url": url})
    return hits


def _html_to_text(raw: str) -> str:
    text = _SCRIPT_STYLE_RE.sub(" ", raw)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def get_article(slug: str) -> dict[str, Any]:
    """Article by slug as plain text (title + body)."""
    slug = slug.strip().strip("/")
    if "/" in slug:
        raise ValueError(f"slug must be a single path segment, got: {slug!r}")
    url = f"{KB_HOME.rstrip('/')}/{slug}"
    with httpx.Client(timeout=30.0, proxy=_proxy_from_env(), follow_redirects=True) as http:
        resp = http.get(url)
        if resp.status_code == 404:
            raise ValueError(f"no article with slug {slug!r}; try: kb search <keyword>")
        resp.raise_for_status()
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.S | re.I)
    if m:
        title = html.unescape(m.group(1)).strip()
    return {"slug": slug, "url": url, "title": title, "text": _html_to_text(resp.text)}
