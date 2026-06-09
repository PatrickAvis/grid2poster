"""Shared constants, the on-disk pickle cache, and small utilities."""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover - optional progress-bar dependency
    class tqdm:  # no-op stand-in supporting both iteration and manual updates
        def __init__(self, iterable=None, *args, **kwargs):
            self._iterable = iterable

        def __iter__(self):
            return iter(self._iterable or [])

        def update(self, n=1):
            pass

        def set_description(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

REPO_ROOT = Path(__file__).resolve().parent
CACHE_DIR = REPO_ROOT / "cache"
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_MAP_DIR = REPO_ROOT / "data" / "map"
DATA_ZONES_DIR = REPO_ROOT / "data" / "zones"
FILE_ENCODING = "utf-8"


def raw_dir(region_id: str) -> Path:
    path = DATA_RAW_DIR / region_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def map_dir(region_id: str) -> Path:
    path = DATA_MAP_DIR / region_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def zones_dir(region_id: str) -> Path:
    path = DATA_ZONES_DIR / region_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def uk_raw_dir() -> Path:
    return raw_dir("uk")


def uk_map_dir() -> Path:
    return map_dir("uk")

for _dir in (CACHE_DIR, DATA_RAW_DIR, DATA_MAP_DIR, DATA_ZONES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
uk_raw_dir().mkdir(parents=True, exist_ok=True)
uk_map_dir().mkdir(parents=True, exist_ok=True)


def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str).encode(FILE_ENCODING)
    return hashlib.sha256(raw).hexdigest()[:24]


def cache_get(key: str) -> Any | None:
    path = CACHE_DIR / f"{key}.pkl"
    if not path.exists():
        return None
    with path.open("rb") as handle:
        return pickle.load(handle)


def cache_set(key: str, value: Any) -> None:
    path = CACHE_DIR / f"{key}.pkl"
    with path.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
