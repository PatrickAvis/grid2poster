"""Shared plant fuel taxonomy and OSM source bucketing."""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
# Fuel taxonomy is shared across all regions (and the browser legend).
FUEL_TYPES_PATH = REPO_ROOT / "data" / "shared" / "fuel_types.json"


@lru_cache(maxsize=1)
def load_fuel_types() -> list[dict[str, Any]]:
    with FUEL_TYPES_PATH.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return list(data.get("types", []))


def fuel_type_ids() -> tuple[str, ...]:
    return tuple(item["id"] for item in load_fuel_types())


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _tokens(value: Any) -> list[str]:
    if _is_empty(value):
        return []
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            result.extend(_tokens(item))
        return result
    text = str(value).lower()
    return [token.strip() for token in re.split(r"[;,/|]+", text) if token.strip()]


def bucket_fuel_source(source: Any) -> str:
    """Map OSM plant:source text to the first matching fuel taxonomy bucket."""
    for token in _tokens(source):
        for fuel_type in load_fuel_types():
            for keyword in fuel_type.get("keywords", []):
                if keyword.lower() in token:
                    return fuel_type["id"]
    return "other"


def bucket_fuel_properties(source: Any, *context_fields: Any) -> str:
    """Map plant fields to a taxonomy bucket, using specific text overrides first."""
    context = " ".join(str(item).lower() for item in context_fields if not _is_empty(item))
    if context:
        for fuel_type in load_fuel_types():
            for keyword in fuel_type.get("name_keywords", []):
                if keyword.lower() in context:
                    return fuel_type["id"]
    return bucket_fuel_source(source)
