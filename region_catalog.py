"""Load and resolve paths from data/catalog.json and boundaries/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import geopandas as gpd

from common import (
    FILE_ENCODING,
    REGION_DATA_DIR,
    REPO_ROOT,
    map_dir,
    raw_dir,
    zones_dir,
)

CATALOG_PATH = REPO_ROOT / "data" / "catalog.json"
# Shared export masks (continent/country clipping polygons). These are inputs,
# not computed data, so they live at the repo root rather than under data/.
BOUNDARIES_DIR = REPO_ROOT / "boundaries"
BOUNDARIES_MANIFEST_PATH = BOUNDARIES_DIR / "manifest.json"

# Backwards-compatible aliases (older code/imports referenced these names).
REGIONS_DIR = BOUNDARIES_DIR
REGIONS_MANIFEST_PATH = BOUNDARIES_MANIFEST_PATH

# Catalog region id -> boundary filename stem under boundaries/
BOUNDARY_ALIASES: dict[str, str] = {
    "uk": "uk_no_shetland",
}

RAW_STEMS: dict[str, str] = {
    "lines": "powerlines",
    "plants": "plants",
    "substations": "substations",
    "turbines": "wind_turbines",
    "generators": "generators",
    "converters": "converters",
    "equipment": "power_equipment",
    "towers": "towers",
}

MAP_STEMS: dict[str, str] = {
    "lines": "lines_transmission",
    "plants": "bmu_sites_web",
    "substations": "substations_web",
    "turbines": "turbines_web",
    "generators": "all_generators_web",
    "converters": "converters_web",
    "equipment": "power_equipment_web",
    "towers": "towers_web",
}

ZONE_STEMS: dict[str, str] = {
    "dno": "dno_areas",
    "gsp": "gsp_areas",
    "generation": "generation_charging_zones",
    "etys": "etys_boundaries",
}

ZONE_WEB_STEMS: dict[str, str] = {
    "dno": "dno_areas_web",
    "gsp": "gsp_areas_web",
    "generation": "generation_charging_zones_web",
    "etys": "etys_boundaries_web",
}


def load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open(encoding=FILE_ENCODING) as handle:
        return json.load(handle)


def load_boundaries_manifest() -> dict[str, Any]:
    if not BOUNDARIES_MANIFEST_PATH.exists():
        return {"regions": {}}
    with BOUNDARIES_MANIFEST_PATH.open(encoding=FILE_ENCODING) as handle:
        return json.load(handle)


# Backwards-compatible alias.
load_regions_manifest = load_boundaries_manifest


def boundary_stem_for(region_id: str) -> str:
    return BOUNDARY_ALIASES.get(region_id, region_id)


def boundary_rel_path(stem: str) -> str:
    return f"boundaries/{stem}.geojson"


def list_boundary_stems() -> list[str]:
    """Boundary filename stems from manifest and on-disk GeoJSON."""
    stems: set[str] = set()
    manifest = load_boundaries_manifest().get("regions", {})
    stems.update(manifest.keys())
    for path in BOUNDARIES_DIR.glob("*.geojson"):
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


def raw_path(region_id: str, layer: str) -> Path:
    stem = RAW_STEMS[layer]
    return raw_dir(region_id) / f"{stem}.geojson"


def raw_csv_path(region_id: str, layer: str) -> Path:
    stem = RAW_STEMS[layer]
    return raw_dir(region_id) / f"{stem}.csv"


# Catalog layer ids for boundary/zone web layers that do not appear in MAP_STEMS.
ZONE_LAYER_WEB_STEMS: dict[str, str] = {
    "dno": ZONE_WEB_STEMS["dno"],
    "gsp": ZONE_WEB_STEMS["gsp"],
    "generation_zones": ZONE_WEB_STEMS["generation"],
    "etys_boundaries": ZONE_WEB_STEMS["etys"],
}


def map_path(region_id: str, layer: str) -> Path:
    """Default web-layer path for a region under data/regions/{id}/map/.

    Catalog ``path`` values drive the real filenames; this is the fallback used
    when a layer is not declared in the catalog.
    """
    web = map_dir(region_id)
    if layer in MAP_STEMS:
        return web / f"{MAP_STEMS[layer]}.geojson"
    if layer in ZONE_LAYER_WEB_STEMS:
        return web / f"{ZONE_LAYER_WEB_STEMS[layer]}.geojson"
    if layer in ZONE_WEB_STEMS:
        return web / f"{ZONE_WEB_STEMS[layer]}.geojson"
    raise KeyError(layer)


def zone_raw_path(region_id: str, zone_kind: str) -> Path:
    return zones_dir(region_id) / f"{ZONE_STEMS[zone_kind]}.geojson"


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
    """Absolute boundary path for a region.

    Resolution order:
      1. Explicit catalog ``boundary`` field (resolved relative to repo root).
      2. Per-region copy at data/regions/{id}/boundary.geojson.
      3. Shared export mask at boundaries/{stem}.geojson.
    """
    catalog = load_catalog()
    catalog_region = catalog.get("regions", {}).get(region_id)
    if catalog_region and catalog_region.get("boundary"):
        return REPO_ROOT / catalog_region["boundary"]

    per_region = REGION_DATA_DIR / region_id / "boundary.geojson"
    if per_region.exists():
        return per_region

    rel = resolve_boundary_rel_path(region_id)
    if not rel:
        return None
    return REPO_ROOT / rel
