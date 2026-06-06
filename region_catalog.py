"""Load and resolve paths from data/catalog.json and regions/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd

from common import DATA_MAP_DIR, DATA_RAW_DIR, DATA_ZONES_DIR, FILE_ENCODING, REPO_ROOT

CATALOG_PATH = REPO_ROOT / "data" / "catalog.json"
REGIONS_DIR = REPO_ROOT / "regions"
REGIONS_MANIFEST_PATH = REGIONS_DIR / "manifest.json"

# Catalog region id -> boundary filename stem under regions/
BOUNDARY_ALIASES: dict[str, str] = {
    "uk": "uk_no_shetland",
}

RAW_STEMS: dict[str, str] = {
    "lines": "powerlines",
    "plants": "plants",
    "substations": "substations",
    "turbines": "wind_turbines",
}

MAP_STEMS: dict[str, str] = {
    "lines": "lines_transmission",
    "plants": "plants_web",
    "substations": "substations_web",
    "turbines": "turbines_web",
}

ZONE_STEMS: dict[str, str] = {
    "dno": "dno_areas",
    "gsp": "gsp_areas",
}

ZONE_WEB_STEMS: dict[str, str] = {
    "dno": "dno_areas_web",
    "gsp": "gsp_areas_web",
}


def load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open(encoding=FILE_ENCODING) as handle:
        return json.load(handle)


def load_regions_manifest() -> dict[str, Any]:
    if not REGIONS_MANIFEST_PATH.exists():
        return {"regions": {}}
    with REGIONS_MANIFEST_PATH.open(encoding=FILE_ENCODING) as handle:
        return json.load(handle)


def boundary_stem_for(region_id: str) -> str:
    return BOUNDARY_ALIASES.get(region_id, region_id)


def boundary_rel_path(stem: str) -> str:
    return f"regions/{stem}.geojson"


def list_boundary_stems() -> list[str]:
    """Boundary filename stems from manifest and on-disk GeoJSON."""
    stems: set[str] = set()
    manifest = load_regions_manifest().get("regions", {})
    stems.update(manifest.keys())
    for path in REGIONS_DIR.glob("*.geojson"):
        stems.add(path.stem)
    return sorted(stems)


def list_region_ids() -> list[str]:
    """Region ids registered in data/catalog.json (map + prepared data)."""
    return list(load_catalog()["regions"].keys())


def list_exportable_region_ids() -> list[str]:
    """Catalog regions plus predefined boundaries from regions/."""
    ids = set(list_region_ids())
    for stem in list_boundary_stems():
        ids.add(stem)
    for region_id in BOUNDARY_ALIASES:
        ids.add(region_id)
    return sorted(ids)


def resolve_boundary_rel_path(region_id: str) -> str | None:
    """Resolve a boundary path relative to repo root (regions/*.geojson)."""
    catalog = load_catalog()
    catalog_region = catalog.get("regions", {}).get(region_id)
    if catalog_region and catalog_region.get("boundary"):
        return catalog_region["boundary"]

    stem = boundary_stem_for(region_id)
    rel = boundary_rel_path(stem)
    if (REPO_ROOT / rel).exists():
        return rel

    manifest = load_regions_manifest().get("regions", {})
    if stem in manifest:
        return rel
    return None


def bounds_from_boundary(path: Path) -> list[list[float]] | None:
    """Leaflet bounds [[south, west], [north, east]] from a boundary GeoJSON."""
    if not path.exists():
        return None
    frame = gpd.read_file(path)
    if frame.empty:
        return None
    minx, miny, maxx, maxy = frame.total_bounds
    return [[float(miny), float(minx)], [float(maxy), float(maxx)]]


def _stub_from_boundary(region_id: str) -> dict[str, Any] | None:
    rel = resolve_boundary_rel_path(region_id)
    if not rel:
        return None

    stem = boundary_stem_for(region_id)
    manifest_entry = load_regions_manifest().get("regions", {}).get(stem, {})
    title = manifest_entry.get("title") or region_id.replace("_", " ").title()
    stub: dict[str, Any] = {
        "title": title,
        "boundary": rel,
        "layers": {},
    }
    bounds = bounds_from_boundary(REPO_ROOT / rel)
    if bounds:
        stub["bounds"] = bounds
    return stub


def get_region(region_id: str) -> dict[str, Any]:
    catalog = load_catalog()
    regions = catalog.get("regions", {})
    if region_id in regions:
        return regions[region_id]
    stub = _stub_from_boundary(region_id)
    if stub:
        return stub
    raise KeyError(f"Unknown region: {region_id!r}")


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


def raw_path(region_id: str, layer: str) -> Path:
    stem = RAW_STEMS[layer]
    return raw_dir(region_id) / f"{stem}.geojson"


def raw_csv_path(region_id: str, layer: str) -> Path:
    stem = RAW_STEMS[layer]
    return raw_dir(region_id) / f"{stem}.csv"


def map_path(region_id: str, layer: str, *, legacy_uk: bool = True) -> Path:
    web = map_dir(region_id)
    if region_id == "uk" and legacy_uk:
        legacy_names = {
            "lines": "uk_powerlines_transmission.geojson",
            "plants": "uk_plants_web.geojson",
            "substations": "uk_substations_web.geojson",
            "turbines": "uk_wind_turbines_web.geojson",
            "dno": "uk_dno_areas_web.geojson",
            "gsp": "uk_gsp_areas_web.geojson",
        }
        if layer in legacy_names:
            return web / legacy_names[layer]
    if layer in MAP_STEMS:
        return web / f"{MAP_STEMS[layer]}.geojson"
    if layer in ZONE_WEB_STEMS:
        return web / f"{ZONE_WEB_STEMS[layer]}.geojson"
    raise KeyError(layer)


def zone_raw_path(region_id: str, zone_kind: str) -> Path:
    flat = DATA_ZONES_DIR / f"{region_id}_{ZONE_STEMS[zone_kind]}.geojson"
    nested = zones_dir(region_id) / f"{ZONE_STEMS[zone_kind]}.geojson"
    if flat.exists():
        return flat
    return nested


def catalog_data_path(rel_path: str) -> Path:
    """Resolve a catalog path (relative to data/) to an absolute path."""
    return REPO_ROOT / "data" / rel_path


def catalog_layer_path(region_id: str, layer_id: str) -> Path | None:
    region = get_region(region_id)
    layer = region.get("layers", {}).get(layer_id)
    if not layer:
        return None
    return catalog_data_path(layer["path"])


def region_country(region_id: str) -> str:
    region = get_region(region_id)
    if "country" in region:
        return region["country"]
    return region["title"]


def region_boundary_path(region_id: str) -> Path | None:
    rel = resolve_boundary_rel_path(region_id)
    if not rel:
        return None
    return REPO_ROOT / rel
