"""Stdout/stderr helpers: always JSON, agent-friendly."""

from __future__ import annotations

import json
import sys
from typing import Any


def select_fields(data: Any, fields: str) -> Any:
    """Keep only the listed top-level keys (comma-separated) in dicts."""
    keep = [f.strip() for f in fields.split(",") if f.strip()]
    if not keep:
        return data
    if isinstance(data, list):
        return [select_fields(item, fields) if isinstance(item, dict) else item for item in data]
    if isinstance(data, dict):
        return {k: data[k] for k in keep if k in data}
    return data


def print_json(data: Any, *, fields: str | None = None, compact: bool = False) -> None:
    if fields:
        data = select_fields(data, fields)
    text = json.dumps(
        data,
        ensure_ascii=False,
        indent=None if compact else 2,
        separators=(",", ":") if compact else None,
        default=str,
    )
    print(text)


def fail(message: str, *, status: int | None = None) -> None:
    payload: dict[str, Any] = {"error": message}
    if status is not None:
        payload = {"error": message, "status": status}
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)
