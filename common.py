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
DATA_DIR = REPO_ROOT / "data"
# All computed data for a region lives under one portable folder so a region
# (e.g. "uk") can be copied between machines as a single tree.
REGION_DATA_DIR = DATA_DIR / "regions"
# Cross-region assets that are not specific to any single region (e.g. the fuel
# taxonomy shared by every region's prep + the browser).
SHARED_DIR = DATA_DIR / "shared"
FILE_ENCODING = "utf-8"


def region_data_dir(region_id: str) -> Path:
    path = REGION_DATA_DIR / region_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir(region_id: str) -> Path:
    path = region_data_dir(region_id) / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def map_dir(region_id: str) -> Path:
    path = region_data_dir(region_id) / "map"
    path.mkdir(parents=True, exist_ok=True)
    return path


def zones_dir(region_id: str) -> Path:
    path = region_data_dir(region_id) / "zones"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reference_dir(region_id: str) -> Path:
    path = region_data_dir(region_id) / "reference"
    path.mkdir(parents=True, exist_ok=True)
    return path


def source_dir(region_id: str) -> Path:
    path = region_data_dir(region_id) / "source"
    path.mkdir(parents=True, exist_ok=True)
    return path


for _dir in (CACHE_DIR, REGION_DATA_DIR, SHARED_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


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
