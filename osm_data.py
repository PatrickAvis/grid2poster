"""Boundary resolution and Overpass downloads of OSM power features."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.ops import unary_union

from common import CACHE_DIR, cache_get, cache_key, cache_set

NATURAL_EARTH_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_50m_admin_0_countries.geojson"
)
NATURAL_EARTH_PATH = CACHE_DIR / "ne_50m_admin_0_countries.geojson"
CONTINENT_NAMES = {
    "africa",
    "antarctica",
    "asia",
    "europe",
    "north america",
    "oceania",
    "south america",
}

# Aggregate region names that combine multiple Natural Earth continents.
CONTINENT_AGGREGATES: dict[str, frozenset[str]] = {
    "global": frozenset({"africa", "asia", "europe", "north america", "south america"}),
}


def _load_natural_earth_countries() -> gpd.GeoDataFrame:
    if not NATURAL_EARTH_PATH.exists():
        import urllib.request

        print(f"Downloading Natural Earth admin-0 dataset → {NATURAL_EARTH_PATH}")
        urllib.request.urlretrieve(NATURAL_EARTH_URL, NATURAL_EARTH_PATH)
    return gpd.read_file(NATURAL_EARTH_PATH)


def _continent_boundary(continent: str) -> gpd.GeoDataFrame:
    countries = _load_natural_earth_countries()
    key = continent.lower()
    aggregate = CONTINENT_AGGREGATES.get(key)
    if aggregate is not None:
        match = countries["CONTINENT"].str.lower().isin(aggregate)
    else:
        match = countries["CONTINENT"].str.lower() == key

    if key == "global":
        # Oceania is excluded from the aggregate above; pull in Australia, Papua
        # New Guinea, and New Zealand explicitly so the export covers them
        # without dragging in the wider Pacific.
        match = match | countries["ISO_A3"].isin(["AUS", "PNG", "NZL"])

    subset = countries[match]
    if subset.empty:
        raise RuntimeError(f"No countries found for continent '{continent}' in Natural Earth")
    merged = unary_union(subset.geometry)

    if key == "global":
        # Clip the global aggregate to a tight bounding box:
        #   • north - Alaska's northernmost point (~71.4°N), to drop the empty
        #     Canadian Arctic, Greenland's interior, and Svalbard.
        #   • west - the Alaska mainland's western edge (~168.1°W), to drop the
        #     Aleutian chain and the empty Bering Sea that otherwise stretch out
        #     to the antimeridian.
        #   • east - New Zealand's easternmost main-island longitude (~178.5°E),
        #     to drop Russia's far-eastern Chukotka sliver that otherwise pushes
        #     the viewport out to the antimeridian.
        us = countries[countries["ISO_A3"] == "USA"]
        nz = countries[countries["ISO_A3"] == "NZL"]
        if us.empty or nz.empty:
            raise RuntimeError(
                "Natural Earth dataset is missing USA or NZL - cannot build global clip"
            )
        # The Alaska mainland is the USA polygon reaching the northernmost
        # latitude; it anchors both the north and west bounds of the clip.
        us_geom = unary_union(us.geometry)
        us_polys = list(us_geom.geoms) if isinstance(us_geom, MultiPolygon) else [us_geom]
        alaska = max(us_polys, key=lambda poly: poly.bounds[3])
        west_lon = float(alaska.bounds[0])
        north_lat = float(alaska.bounds[3])
        east_lon = float(nz.total_bounds[2])
        merged = merged.intersection(box(west_lon, -90, east_lon, north_lat))

    return gpd.GeoDataFrame({"name": [continent]}, geometry=[merged], crs=countries.crs)


def keep_main_landmass(geometry: Any) -> Any:
    """Drop disjoint polygons that are far from the main landmass.

    Geocoded country boundaries include overseas territories - e.g. Aruba and
    Curaçao for the Netherlands, French Guiana and Réunion for France. We keep
    the largest polygon plus any polygon whose envelope intersects a 3×-inflated
    bounding box of the largest one. This preserves close-by islands such as
    Northern Ireland, Corsica, or Japan's main islands.
    """
    if not isinstance(geometry, MultiPolygon):
        return geometry

    polygons = list(geometry.geoms)
    if len(polygons) <= 1:
        return geometry

    largest = max(polygons, key=lambda p: p.area)
    minx, miny, maxx, maxy = largest.bounds
    width = max(maxx - minx, 0.01)
    height = max(maxy - miny, 0.01)
    region = box(minx - width, miny - height, maxx + width, maxy + height)

    kept = [p for p in polygons if region.intersects(p)]
    if len(kept) == 1:
        return kept[0]
    return MultiPolygon(kept)


def load_boundary_from_geojson(path: Path, name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path)
    if gdf.empty:
        raise RuntimeError(f"Boundary file '{path}' contains no features")
    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])]
    if gdf.empty:
        raise RuntimeError(f"Boundary file '{path}' contains no polygonal geometry")
    if gdf.crs is None:
        print(f"Boundary file '{path}' has no CRS - assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    merged = unary_union(gdf.geometry)
    return gpd.GeoDataFrame({"name": [name]}, geometry=[merged], crs="EPSG:4326")


def get_country_boundary(country: str, mainland_only: bool = True, use_cache: bool = True) -> gpd.GeoDataFrame:
    key = cache_key("boundary_v3", country, mainland_only)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached boundary for {country}")
            return cached

    if country.lower() in CONTINENT_NAMES or country.lower() in CONTINENT_AGGREGATES:
        print(f"Building continent boundary from Natural Earth: {country}")
        boundary = _continent_boundary(country)
    else:
        print(f"Geocoding country boundary: {country}")
        boundary = ox.geocode_to_gdf(country)
        boundary = boundary[boundary.geometry.type.isin(["Polygon", "MultiPolygon"])]
        if boundary.empty:
            raise RuntimeError(f"Could not resolve a country boundary for '{country}'")
        if mainland_only:
            merged = unary_union(boundary.geometry)
            filtered = keep_main_landmass(merged)
            before = len(merged.geoms) if isinstance(merged, MultiPolygon) else 1
            after = len(filtered.geoms) if isinstance(filtered, MultiPolygon) else 1
            if after < before:
                print(
                    f"Mainland-only: dropped {before - after} outlying polygon(s); "
                    "pass --include-outlying to keep them"
                )
            boundary = gpd.GeoDataFrame(
                {"name": [country]}, geometry=[filtered], crs=boundary.crs
            )

    cache_set(key, boundary)
    return boundary


def _polygon_to_overpass_poly(polygon: Polygon, precision: int = 6) -> str:
    """Convert a Shapely Polygon exterior ring to Overpass poly: coordinate string."""
    parts = []
    for lon, lat in polygon.exterior.coords:
        parts.append(f"{lat:.{precision}f} {lon:.{precision}f}")
    return " ".join(parts)


def _simplify_boundary_for_overpass(
    geometry: Polygon | MultiPolygon,
    max_coords: int = 2000,
) -> list[Polygon]:
    """Progressively simplify a boundary so the total coordinate count fits Overpass."""
    if isinstance(geometry, Polygon):
        polygons = [geometry]
    else:
        polygons = list(geometry.geoms)

    for tolerance in (0.005, 0.01, 0.02, 0.05, 0.1):
        total_coords = sum(len(p.exterior.coords) for p in polygons)
        if total_coords <= max_coords:
            break
        simplified = []
        for p in polygons:
            s = p.simplify(tolerance, preserve_topology=True)
            if not s.is_empty and isinstance(s, Polygon):
                simplified.append(s)
            elif not s.is_empty and isinstance(s, MultiPolygon):
                simplified.extend(s.geoms)
        polygons = simplified

    return [p for p in polygons if not p.is_empty]


def fetch_power_features_single(
    country: str,
    boundary: gpd.GeoDataFrame,
    include_minor_lines: bool = False,
    include_cables: bool = False,
    sea_buffer_km: float = 0.0,
    render_crs: str = "EPSG:3857",
    use_cache: bool = True,
    timeout: int = 300,
) -> gpd.GeoDataFrame:
    """Fetch all power features in one Overpass query using poly: filter."""
    import requests as http_requests

    values = power_tag_values(include_minor_lines, include_cables)
    key = cache_key("power_single_v2", country, values, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached power features for {country}")
            return cached

    boundary_geom = unary_union(boundary.geometry)

    if sea_buffer_km > 0:
        boundary_proj = boundary.to_crs(render_crs)
        buffered = unary_union(boundary_proj.geometry).buffer(sea_buffer_km * 1000)
        boundary_geom = gpd.GeoDataFrame(
            geometry=[buffered], crs=render_crs
        ).to_crs("EPSG:4326").geometry.iloc[0]

    polygons = _simplify_boundary_for_overpass(boundary_geom)
    total_coords = sum(len(p.exterior.coords) for p in polygons)
    print(
        f"Single Overpass query: {len(polygons)} polygon(s), "
        f"{total_coords:,} coordinate pairs"
    )

    power_regex = "^(" + "|".join(values) + ")$"
    way_clauses = []
    for poly in polygons:
        ps = _polygon_to_overpass_poly(poly)
        way_clauses.append(f'  way["power"~"{power_regex}"](poly:"{ps}");')

    query = (
        f"[out:json][timeout:{timeout}];\n"
        "(\n"
        + "\n".join(way_clauses) + "\n"
        ");\n"
        "out geom;\n"
    )

    overpass_url = ox.settings.overpass_url.rstrip("/")
    if not overpass_url.endswith("/interpreter"):
        overpass_url += "/interpreter"

    print(f"Sending Overpass query ({len(query):,} bytes) to {overpass_url}")
    response = http_requests.post(
        overpass_url,
        data={"data": query},
        timeout=timeout + 30,
        headers={"User-Agent": "UKPowerMap/1.0"},
    )
    response.raise_for_status()
    data = response.json()

    elements = data.get("elements", [])
    print(f"Received {len(elements):,} elements from Overpass")

    rows = []
    for elem in elements:
        if elem.get("type") != "way":
            continue
        geom_coords = elem.get("geometry", [])
        if len(geom_coords) < 2:
            continue
        coords = [(pt["lon"], pt["lat"]) for pt in geom_coords]
        tags = elem.get("tags", {}).copy()
        tags.update({
            "element_type": elem.get("type"),
            "osmid": elem.get("id"),
            "geometry": LineString(coords),
        })
        rows.append(tags)

    if not rows:
        raise RuntimeError(
            f"No line geometries found for power={values} in {country}. "
            "The region may be too large for a single query — try without --single-query."
        )

    result = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    for col in ["power", "voltage", "name", "operator", "geometry"]:
        if col not in result.columns:
            result[col] = None
    cache_set(key, result)
    return result


def power_tag_values(include_minor_lines: bool, include_cables: bool) -> list[str]:
    values = ["line"]
    if include_minor_lines:
        values.append("minor_line")
    if include_cables:
        values.append("cable")
    return values


def effective_tile_size_km(tile_size_km: float, sea_buffer_km: float) -> float:
    """Shrink Overpass grid cells when querying a sea-buffered extent.

    A 400 km nominal tile over a 600 km offshore margin often intersects an
    area many times larger than Overpass allows, causing read timeouts.
    """
    if sea_buffer_km <= 0:
        return tile_size_km
    if sea_buffer_km >= 500:
        return min(tile_size_km, 80.0)
    if sea_buffer_km >= 300:
        return min(tile_size_km, 100.0)
    if sea_buffer_km >= 150:
        return min(tile_size_km, 150.0)
    return min(tile_size_km, 200.0)


def make_query_tiles(
    boundary: gpd.GeoDataFrame,
    tile_size_km: float,
    render_crs: str,
    sea_buffer_km: float = 0.0,
) -> gpd.GeoDataFrame:
    """Split a large country boundary into smaller projected tiles for Overpass."""
    if tile_size_km <= 0:
        raise ValueError("tile_size_km must be greater than zero")

    effective_size = effective_tile_size_km(tile_size_km, sea_buffer_km)
    if effective_size < tile_size_km:
        print(
            f"  Sea buffer {sea_buffer_km:g} km: using {effective_size:g} km Overpass tiles "
            f"(requested {tile_size_km:g} km) to avoid timeouts",
        )
        tile_size_km = effective_size

    boundary_projected = boundary.to_crs(render_crs)
    country_geom = unary_union(boundary_projected.geometry)
    if not isinstance(country_geom, (Polygon, MultiPolygon)):
        raise RuntimeError("Boundary geometry is not polygonal")

    if sea_buffer_km > 0:
        # Inflate the land polygon by a sea margin so tiles cover water between
        # islands and short stretches of coast. Without this, power=cable ways
        # on the seabed (inter-island and cross-border interconnectors) are
        # never fetched from Overpass.
        country_geom = country_geom.buffer(sea_buffer_km * 1000)

    minx, miny, maxx, maxy = country_geom.bounds
    tile_size_m = tile_size_km * 1000
    tiles = []

    x_steps = np.arange(minx, maxx, tile_size_m)
    y_steps = np.arange(miny, maxy, tile_size_m)

    for x0 in x_steps:
        for y0 in y_steps:
            candidate = box(x0, y0, min(x0 + tile_size_m, maxx), min(y0 + tile_size_m, maxy))
            if not candidate.intersects(country_geom):
                continue
            clipped = candidate.intersection(country_geom)
            if not clipped.is_empty:
                tiles.append(clipped)

    if not tiles:
        raise RuntimeError("Could not create query tiles from the country boundary")

    return gpd.GeoDataFrame(geometry=tiles, crs=render_crs).to_crs("EPSG:4326")


# OSM element-identity columns kept per tile so cross-tile duplicates (ways
# spanning a tile border are returned by both tiles) can be dropped on merge.
_TILE_ID_COLS = ["element", "element_type", "osmid", "id"]

_REQUIRED_LINE_COLS = ["power", "voltage", "name", "operator", "geometry"]
_REQUIRED_PLANT_COLS = ["power", "plant:source", "plant:output:electricity", "name", "operator", "geometry"]
_REQUIRED_SUBSTATION_COLS = ["power", "substation", "voltage", "name", "operator", "geometry"]
_REQUIRED_WIND_TURBINE_COLS = [
    "power",
    "generator:source",
    "generator:method",
    "generator:type",
    "generator:output:electricity",
    "name",
    "operator",
    "manufacturer",
    "model",
    "height",
    "rotor:diameter",
    "ref",
    "geometry",
]

_WIND_TURBINE_TAG_QUERIES = (
    {"power": "generator", "generator:source": "wind"},
    {"power": "generator", "generator:method": "wind_turbine"},
)

# Schemas for the additional power layers (generators excluding wind, HVDC
# converters, discrete equipment, and transmission towers). Each mirrors the
# Overpass fetchers' "required columns" contract so downstream prep is stable.
_REQUIRED_GENERATOR_COLS = [
    "power",
    "generator:source",
    "generator:method",
    "generator:type",
    "generator:output:electricity",
    "name",
    "operator",
    "geometry",
]
_REQUIRED_CONVERTER_COLS = [
    "power",
    "converter",
    "voltage",
    "frequency",
    "rating",
    "name",
    "operator",
    "geometry",
]
_REQUIRED_EQUIPMENT_COLS = [
    "power",
    "voltage",
    "location",
    "name",
    "operator",
    "ref",
    "geometry",
]
_REQUIRED_TOWER_COLS = [
    "power",
    "ref",
    "operator",
    "name",
    "height",
    "geometry",
]

# power=* values rolled into the single "equipment" layer (converters get their
# own layer, so they are intentionally excluded here).
EQUIPMENT_POWER_VALUES = [
    "transformer",
    "switch",
    "switchgear",
    "busbar",
    "terminal",
    "portal",
    "bay",
    "connection",
    "compensator",
    "insulator",
]


def _generator_is_wind(frame: gpd.GeoDataFrame) -> pd.Series:
    """Boolean mask of generators that represent wind (source or method)."""
    source = frame.get("generator:source")
    method = frame.get("generator:method")
    is_wind = pd.Series(False, index=frame.index)
    if source is not None:
        is_wind = is_wind | source.astype("string").str.contains("wind", case=False, na=False)
    if method is not None:
        is_wind = is_wind | method.astype("string").str.contains("wind_turbine", case=False, na=False)
    return is_wind


def drop_wind_generators(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return only non-wind generators (wind is covered by the turbine layer)."""
    if frame.empty:
        return frame
    keep = ~_generator_is_wind(frame)
    return gpd.GeoDataFrame(frame[keep], geometry="geometry", crs="EPSG:4326").reset_index(drop=True)


def _fetch_tiles(
    tiles: gpd.GeoDataFrame,
    tags: dict[str, Any],
    tile_cache_key: Callable[[Any], str],
    geometry_types: list[str],
    required_cols: list[str],
    use_cache: bool,
    tile_delay: float,
) -> list[gpd.GeoDataFrame]:
    """Download ``tags`` features for every tile, returning one frame per tile.

    Shared engine behind fetch_power_features and fetch_power_plants: per-tile
    caching, adaptive rate-limit backoff, and indefinite retries for failed
    tiles. Only features whose geometry type is in ``geometry_types`` are kept.
    All OSM tag columns are preserved so GeoJSON exports can carry the full
    downloaded feature metadata, while required columns are added as empty when
    absent so downstream rendering code sees a stable schema.
    """
    frames: list[gpd.GeoDataFrame] = []
    empty_tile = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    rate_limit_delay = tile_delay

    def process_tile(tile_number: int, tile_geom, total: int) -> bool:
        """Fetch a tile's features and append to ``frames``. Returns True on success."""
        nonlocal rate_limit_delay
        if rate_limit_delay > 0:
            label = "Tile delay" if rate_limit_delay <= tile_delay else "Rate-limit backoff"
            print(f"  {label}: waiting {rate_limit_delay}s before next request")
            time.sleep(rate_limit_delay)
        try:
            features = ox.features_from_polygon(tile_geom, tags=tags)
        except Exception as exc:
            # OSMnx raises this when Overpass returned a valid response with zero
            # matching features — not a server error, so cache as empty and move on.
            if "No matching features" in str(exc):
                cache_set(tile_cache_key(tile_geom), empty_tile)
                rate_limit_delay = max(tile_delay, rate_limit_delay - 5)
                return True
            is_rate_limit = "111" in str(exc) or "rate" in str(exc).lower() or "too many" in str(exc).lower()
            if is_rate_limit:
                rate_limit_delay = min(120, rate_limit_delay + 10)
            print(f"  Warning: tile {tile_number:,}/{total:,} failed: {exc}")
            return False
        rate_limit_delay = max(tile_delay, rate_limit_delay - 5)

        if features.empty:
            cache_set(tile_cache_key(tile_geom), empty_tile)
            return True

        features = features.reset_index()
        matching = features[features.geometry.type.isin(geometry_types)]
        if matching.empty:
            cache_set(tile_cache_key(tile_geom), empty_tile)
            return True

        tile_gdf = gpd.GeoDataFrame(matching.copy(), geometry="geometry", crs="EPSG:4326")
        for col in required_cols:
            if col not in tile_gdf.columns:
                tile_gdf[col] = None
        cache_set(tile_cache_key(tile_geom), tile_gdf)
        frames.append(tile_gdf)
        return True

    total_tiles = len(tiles)
    uncached: list[tuple[int, Any]] = []
    cached_hits = 0
    for tile_number, tile_geom in enumerate(tiles.geometry, start=1):
        if use_cache:
            cached_tile = cache_get(tile_cache_key(tile_geom))
            if cached_tile is not None:
                if not cached_tile.empty:
                    frames.append(cached_tile)
                cached_hits += 1
                continue
        uncached.append((tile_number, tile_geom))

    if cached_hits:
        print(f"  Reused {cached_hits:,}/{total_tiles:,} tile(s) from per-tile cache")

    pending: list[tuple[int, Any]] = []
    for tile_number, tile_geom in uncached:
        print(f"  Tile {tile_number:,}/{total_tiles:,}")
        if not process_tile(tile_number, tile_geom, total_tiles):
            pending.append((tile_number, tile_geom))

    attempt = 1
    while pending:
        delay = min(300, max(rate_limit_delay, 10 * attempt))
        print(
            f"Retrying {len(pending):,} failed tile(s) in {delay}s "
            f"(attempt {attempt + 1})..."
        )
        time.sleep(delay)
        next_pending: list[tuple[int, Any]] = []
        for tile_number, tile_geom in pending:
            print(f"  Retry tile {tile_number:,}/{total_tiles:,}")
            if not process_tile(tile_number, tile_geom, total_tiles):
                next_pending.append((tile_number, tile_geom))

        if next_pending and len(next_pending) == len(pending):
            print(
                "  No tiles succeeded this round — Overpass may be returning "
                "the same error for these tiles; will keep retrying."
            )

        pending = next_pending
        attempt += 1

    return frames


def _combine_tile_frames(frames: list[gpd.GeoDataFrame], required_cols: list[str]) -> gpd.GeoDataFrame:
    """Merge per-tile frames, drop cross-tile duplicates, and ensure required columns exist."""
    combined = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326")
    id_cols = [col for col in _TILE_ID_COLS if col in combined.columns]
    if id_cols:
        combined = combined.drop_duplicates(subset=id_cols)
    else:
        combined = combined.drop_duplicates(subset=["geometry"])
    for col in required_cols:
        if col not in combined.columns:
            combined[col] = None
    return combined


def fetch_power_features(
    country: str,
    boundary: gpd.GeoDataFrame,
    include_minor_lines: bool = False,
    include_cables: bool = False,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    sea_buffer_km: float = 0.0,
    use_cache: bool = True,
    tile_delay: float = 0,
) -> gpd.GeoDataFrame:
    values = power_tag_values(include_minor_lines, include_cables)
    key = cache_key("power_features_v2", country, values, tile_size_km, render_crs, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached power features for {country}")
            return cached

    tiles = make_query_tiles(
        boundary,
        tile_size_km=tile_size_km,
        render_crs=render_crs,
        sea_buffer_km=sea_buffer_km,
    )
    print(f"Downloading OSM power features: power={values} across {len(tiles):,} tiles")

    def tile_cache_key(tile_geom: Any) -> str:
        # Per-tile key so partial progress survives a crash or Overpass outage:
        # geometry WKB folds in tile_size_km / render_crs / sea_buffer_km, since
        # those parameters fully determine the tile polygon.
        return cache_key("power_tile_v2", country, values, tile_geom.wkb_hex)

    frames = _fetch_tiles(
        tiles,
        tags={"power": values},
        tile_cache_key=tile_cache_key,
        geometry_types=["LineString", "MultiLineString"],
        required_cols=_TILE_ID_COLS + _REQUIRED_LINE_COLS,
        use_cache=use_cache,
        tile_delay=tile_delay,
    )

    if not frames:
        raise RuntimeError(
            f"No line geometries found for power={values} in {country}. "
            "Try a smaller --tile-size-km or rerun later if Overpass is busy."
        )

    combined = _combine_tile_frames(frames, _REQUIRED_LINE_COLS)
    cache_set(key, combined)
    return combined


def fetch_power_plants(
    country: str,
    boundary: gpd.GeoDataFrame,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    sea_buffer_km: float = 0.0,
    use_cache: bool = True,
    tile_delay: float = 0,
) -> gpd.GeoDataFrame:
    """Fetch power=plant features inside the boundary, tiled like the lines.

    Plants are nodes or areas, so point and polygon geometries are kept. An
    empty result is returned (not raised) when a region has no mapped plants —
    the overlay simply stays empty.
    """
    # Distinct cache namespaces ("power_plants_v1"/"power_plant_tile_v1") keep
    # plant tiles from ever colliding with the line tile cache.
    key = cache_key("power_plants_v4", country, tile_size_km, render_crs, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached power plants for {country}")
            return cached

    tiles = make_query_tiles(
        boundary,
        tile_size_km=tile_size_km,
        render_crs=render_crs,
        sea_buffer_km=sea_buffer_km,
    )
    buffer_note = f" (including {sea_buffer_km:g} km sea buffer)" if sea_buffer_km > 0 else ""
    print(f"Downloading OSM power plants: power=plant across {len(tiles):,} tiles{buffer_note}")

    def tile_cache_key(tile_geom: Any) -> str:
        return cache_key("power_plant_tile_v4", country, sea_buffer_km, tile_geom.wkb_hex)

    frames = _fetch_tiles(
        tiles,
        tags={"power": "plant"},
        tile_cache_key=tile_cache_key,
        geometry_types=["Point", "Polygon", "MultiPolygon"],
        required_cols=_TILE_ID_COLS + _REQUIRED_PLANT_COLS,
        use_cache=use_cache,
        tile_delay=tile_delay,
    )

    if not frames:
        # Unlike lines, a region without mapped plants is a valid export.
        combined = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        cache_set(key, combined)
        return combined

    combined = _combine_tile_frames(frames, _REQUIRED_PLANT_COLS)
    cache_set(key, combined)
    return combined


def fetch_power_substations(
    country: str,
    boundary: gpd.GeoDataFrame,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    use_cache: bool = True,
    tile_delay: float = 0,
) -> gpd.GeoDataFrame:
    """Fetch power=substation features inside the boundary, tiled like the lines."""
    key = cache_key("power_substations_v2", country, tile_size_km, render_crs)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached power substations for {country}")
            return cached

    tiles = make_query_tiles(boundary, tile_size_km=tile_size_km, render_crs=render_crs)
    print(f"Downloading OSM power substations: power=substation across {len(tiles):,} tiles")

    def tile_cache_key(tile_geom: Any) -> str:
        return cache_key("power_substation_tile_v2", country, tile_geom.wkb_hex)

    frames = _fetch_tiles(
        tiles,
        tags={"power": "substation"},
        tile_cache_key=tile_cache_key,
        geometry_types=["Point", "Polygon", "MultiPolygon"],
        required_cols=_TILE_ID_COLS + _REQUIRED_SUBSTATION_COLS,
        use_cache=use_cache,
        tile_delay=tile_delay,
    )

    if not frames:
        combined = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        cache_set(key, combined)
        return combined

    combined = _combine_tile_frames(frames, _REQUIRED_SUBSTATION_COLS)
    cache_set(key, combined)
    return combined


def fetch_wind_turbines(
    country: str,
    boundary: gpd.GeoDataFrame,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    sea_buffer_km: float = 0.0,
    use_cache: bool = True,
    tile_delay: float = 0,
) -> gpd.GeoDataFrame:
    """Fetch individual wind turbines mapped as ``power=generator`` in OSM.

    Queries both ``generator:source=wind`` and ``generator:method=wind_turbine``
    so turbines tagged either way are included, then deduplicates on OSM identity.
    All downloaded OSM tag columns are preserved for export.
    """
    key = cache_key("wind_turbines_v2", country, tile_size_km, render_crs, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached wind turbines for {country}")
            return cached

    tiles = make_query_tiles(
        boundary,
        tile_size_km=tile_size_km,
        render_crs=render_crs,
        sea_buffer_km=sea_buffer_km,
    )
    buffer_note = f" (including {sea_buffer_km:g} km sea buffer)" if sea_buffer_km > 0 else ""
    print(
        "Downloading OSM wind turbines: power=generator with "
        "generator:source=wind or generator:method=wind_turbine "
        f"across {len(tiles):,} tiles{buffer_note}"
    )

    frames: list[gpd.GeoDataFrame] = []
    for query_index, tags in enumerate(_WIND_TURBINE_TAG_QUERIES, start=1):
        tag_label = ",".join(f"{k}={v}" for k, v in tags.items())
        tile_label = f"q{query_index}_{tag_label}"

        def tile_cache_key(tile_geom: Any, _tile_label: str = tile_label) -> str:
            return cache_key(
                "wind_turbine_tile_v2",
                country,
                _tile_label,
                sea_buffer_km,
                tile_geom.wkb_hex,
            )

        tile_frames = _fetch_tiles(
            tiles,
            tags=tags,
            tile_cache_key=tile_cache_key,
            geometry_types=["Point", "Polygon", "MultiPolygon"],
            required_cols=_TILE_ID_COLS + _REQUIRED_WIND_TURBINE_COLS,
            use_cache=use_cache,
            tile_delay=tile_delay,
        )
        frames.extend(tile_frames)

    if not frames:
        combined = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        cache_set(key, combined)
        return combined

    combined = _combine_tile_frames(frames, _REQUIRED_WIND_TURBINE_COLS)
    cache_set(key, combined)
    return combined


def fetch_power_values(
    country: str,
    boundary: gpd.GeoDataFrame,
    values: list[str],
    geometry_types: list[str],
    required_cols: list[str],
    *,
    cache_tag: str,
    tile_size_km: float = 200,
    render_crs: str = "EPSG:8857",
    sea_buffer_km: float = 0.0,
    use_cache: bool = True,
    tile_delay: float = 0,
) -> gpd.GeoDataFrame:
    """Generic tiled Overpass fetch for arbitrary ``power=*`` values.

    Backs the additional layers (generators, converters, equipment, towers)
    when ``--osm-pbf`` is not used. An empty result is returned, not raised, so
    a region without a given feature class simply yields an empty overlay.
    """
    key = cache_key(cache_tag, country, values, tile_size_km, render_crs, sea_buffer_km)
    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            print(f"Using cached {cache_tag} for {country}")
            return cached

    tiles = make_query_tiles(
        boundary,
        tile_size_km=tile_size_km,
        render_crs=render_crs,
        sea_buffer_km=sea_buffer_km,
    )
    print(f"Downloading OSM power={values} across {len(tiles):,} tiles")

    def tile_cache_key(tile_geom: Any) -> str:
        return cache_key(f"{cache_tag}_tile", country, values, sea_buffer_km, tile_geom.wkb_hex)

    frames = _fetch_tiles(
        tiles,
        tags={"power": values},
        tile_cache_key=tile_cache_key,
        geometry_types=geometry_types,
        required_cols=_TILE_ID_COLS + required_cols,
        use_cache=use_cache,
        tile_delay=tile_delay,
    )

    if not frames:
        combined = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        cache_set(key, combined)
        return combined

    combined = _combine_tile_frames(frames, required_cols)
    cache_set(key, combined)
    return combined


# ---------------------------------------------------------------------------
# Local .osm.pbf fast path (GDAL OSM driver via pyogrio)
#
# Reading power features from a local country extract avoids Overpass entirely,
# which is dramatically faster and immune to rate limits / read timeouts. We use
# GDAL's built-in OSM driver (already shipped with geopandas/pyogrio) rather than
# an extra dependency. A small osmconf.ini promotes the ``power`` tag to a real
# field so GDAL can push the attribute filter down, while ``other_tags=yes``
# preserves every remaining tag. Output mirrors the Overpass fetchers' schema
# (all OSM tags as columns, required columns present, EPSG:4326) so the rest of
# the export/prepare pipeline is unchanged.
# ---------------------------------------------------------------------------

PBF_LAYERS = (
    "lines",
    "plants",
    "substations",
    "turbines",
    "generators",
    "converters",
    "equipment",
    "towers",
)

# GDAL OSM driver layers that hold each geometry kind. Power lines are ways
# (lines layer); plants/substations/turbines are nodes (points) or areas
# (multipolygons, built from closed ways and multipolygon relations).
# ``power`` is appended to closed_ways_are_polygons so that power=plant /
# power=substation closed ways are emitted as polygons (multipolygons layer)
# rather than closed lines; the rest of the list is GDAL's default.
_OSM_CONFIG_INI = """[general]
attribute_name_laundering=no
closed_ways_are_polygons=aeroway,amenity,boundary,building,craft,geological,historic,landuse,leisure,military,natural,office,place,shop,sport,tourism,power

[points]
osm_id=yes
report_all_nodes=no
attributes=power
other_tags=yes

[lines]
osm_id=yes
attributes=power
other_tags=yes

[multipolygons]
osm_id=yes
osm_way_id=yes
attributes=power
other_tags=yes

[multilinestrings]
osm_id=yes
other_tags=yes

[other_relations]
osm_id=yes
other_tags=yes
"""

# GDAL serializes unpromoted tags as an HSTORE-like string:
#   "voltage"=>"400000","cables"=>"3"
_HSTORE_RE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*=>\s*"((?:[^"\\]|\\.)*)"')


def _osm_config_path() -> Path:
    path = CACHE_DIR / "osmconf_power.ini"
    if not path.exists():
        path.write_text(_OSM_CONFIG_INI, encoding="utf-8")
    return path


def _unescape_hstore(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _parse_other_tags(value: Any) -> dict[str, str]:
    if not isinstance(value, str) or not value:
        return {}
    return {
        _unescape_hstore(key): _unescape_hstore(val)
        for key, val in _HSTORE_RE.findall(value)
    }


def _pbf_boundary_geom(boundary: gpd.GeoDataFrame, sea_buffer_km: float):
    """Return a WGS84 (multi)polygon mask, optionally inflated by a sea margin."""
    if sea_buffer_km > 0:
        projected = boundary.to_crs("EPSG:3857")
        buffered = unary_union(projected.geometry).buffer(sea_buffer_km * 1000)
        return gpd.GeoSeries([buffered], crs="EPSG:3857").to_crs("EPSG:4326").iloc[0]
    return unary_union(boundary.to_crs("EPSG:4326").geometry)


def _read_osm_layer(pbf_path: Path, gdal_layer: str, where: str) -> gpd.GeoDataFrame:
    """Read one GDAL OSM layer, filtering on the promoted ``power`` attribute.

    No spatial (bbox) filter is used: pyogrio's bbox filter does not work with
    the OSM driver, and the ``where`` clause already limits the result to power
    features. Final clipping to the exact boundary happens in pandas.
    """
    import pyogrio

    # GDAL reads OSM_CONFIG_FILE as a config option; set it through pyogrio so
    # its GDAL instance honours it reliably (a plain os.environ change is not
    # always picked up). NOTE: do NOT enable OGR_INTERLEAVED_READING — in that
    # mode the OSM driver yields zero features for a single-layer read.
    config_path = str(_osm_config_path())
    os.environ["OSM_CONFIG_FILE"] = config_path
    pyogrio.set_gdal_config_options(
        {"OSM_CONFIG_FILE": config_path, "OGR_INTERLEAVED_READING": "NO"}
    )
    try:
        frame = pyogrio.read_dataframe(str(pbf_path), layer=gdal_layer, where=where)
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise RuntimeError(
            f"Failed to read layer {gdal_layer!r} from {pbf_path.name}: {exc}"
        ) from exc
    if frame.crs is None:
        frame.set_crs("EPSG:4326", inplace=True)
    return frame


def _expand_other_tags(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Promote GDAL's catch-all ``other_tags`` HSTORE into individual columns."""
    if "other_tags" not in frame.columns:
        return frame
    parsed = frame["other_tags"].apply(_parse_other_tags)
    extra = pd.json_normalize(parsed)
    extra.index = frame.index
    for col in extra.columns:
        if col not in frame.columns:
            frame[col] = extra[col]
    return frame.drop(columns=["other_tags"])


def _normalize_pbf_frame(
    frames: list[gpd.GeoDataFrame],
    *,
    geometry_types: list[str],
    required_cols: list[str],
    mask_geom: Any,
) -> gpd.GeoDataFrame:
    """Coerce raw GDAL OSM frames into the Overpass fetchers' output schema."""
    frames = [f for f in frames if f is not None and len(f) > 0]
    if not frames:
        empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        for col in required_cols:
            empty[col] = None
        return empty

    frame = gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True), geometry="geometry", crs="EPSG:4326"
    )
    frame = _expand_other_tags(frame)

    # Identity columns matching the Overpass schema (used for dedup downstream).
    if "osm_way_id" in frame.columns:
        frame["osmid"] = frame["osm_way_id"].fillna(frame.get("osm_id"))
    elif "osm_id" in frame.columns:
        frame["osmid"] = frame["osm_id"]
    if "osm_id" in frame.columns:
        frame["id"] = frame["osm_id"]

    frame = frame[frame.geometry.notna() & frame.geometry.type.isin(geometry_types)]
    if not frame.empty and mask_geom is not None:
        frame = frame[frame.geometry.intersects(mask_geom)]

    frame = gpd.GeoDataFrame(frame, geometry="geometry", crs="EPSG:4326")
    if "osmid" in frame.columns:
        frame = frame.drop_duplicates(subset=["osmid", *(["power"] if "power" in frame.columns else [])])
    for col in required_cols:
        if col not in frame.columns:
            frame[col] = None
    return frame.reset_index(drop=True)


def _sql_in(values: list[str]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"power IN ({quoted})"


def _read_point_and_polygon(
    pbf_path: Path,
    where: str,
    mask_geom: Any,
    required_cols: list[str],
) -> gpd.GeoDataFrame:
    """Read node (points) and area (multipolygons) power features for one filter."""
    frames = [
        _read_osm_layer(pbf_path, "points", where),
        _read_osm_layer(pbf_path, "multipolygons", where),
    ]
    return _normalize_pbf_frame(
        frames,
        geometry_types=["Point", "Polygon", "MultiPolygon"],
        required_cols=required_cols,
        mask_geom=mask_geom,
    )


def fetch_power_layer_from_pbf(
    pbf_path: Path,
    boundary: gpd.GeoDataFrame,
    layer: str,
    *,
    include_minor_lines: bool = False,
    include_cables: bool = False,
    sea_buffer_km: float = 0.0,
) -> gpd.GeoDataFrame:
    """Read a single power layer from a local ``.osm.pbf`` (GDAL OSM driver).

    ``layer`` is one of :data:`PBF_LAYERS`. Output matches the corresponding
    ``fetch_power_*`` Overpass function so downstream preparation is identical.
    """
    if layer not in PBF_LAYERS:
        raise ValueError(f"Unknown PBF layer {layer!r}; expected one of {PBF_LAYERS}")

    pbf_path = Path(pbf_path)
    if not pbf_path.exists():
        raise FileNotFoundError(f"OSM PBF not found: {pbf_path}")

    mask_geom = _pbf_boundary_geom(boundary, sea_buffer_km)

    buffer_note = f" (including {sea_buffer_km:g} km sea buffer)" if sea_buffer_km > 0 else ""
    print(f"Reading power {layer} from local PBF {pbf_path.name}{buffer_note}")

    if layer == "lines":
        values = power_tag_values(include_minor_lines, include_cables)
        frames = [_read_osm_layer(pbf_path, "lines", _sql_in(values))]
        result = _normalize_pbf_frame(
            frames,
            geometry_types=["LineString", "MultiLineString"],
            required_cols=_REQUIRED_LINE_COLS,
            mask_geom=mask_geom,
        )
        if result.empty:
            raise RuntimeError(
                f"No power={values} lines found in {pbf_path.name} within the boundary."
            )
        return result

    if layer == "plants":
        return _read_point_and_polygon(
            pbf_path, "power = 'plant'", mask_geom, _REQUIRED_PLANT_COLS
        )

    if layer == "substations":
        return _read_point_and_polygon(
            pbf_path, "power = 'substation'", mask_geom, _REQUIRED_SUBSTATION_COLS
        )

    if layer == "converters":
        return _read_point_and_polygon(
            pbf_path, "power = 'converter'", mask_geom, _REQUIRED_CONVERTER_COLS
        )

    if layer == "equipment":
        return _read_point_and_polygon(
            pbf_path, _sql_in(EQUIPMENT_POWER_VALUES), mask_geom, _REQUIRED_EQUIPMENT_COLS
        )

    if layer == "towers":
        # Towers are nodes only; reading just the points layer keeps it fast.
        frames = [_read_osm_layer(pbf_path, "points", "power = 'tower'")]
        return _normalize_pbf_frame(
            frames,
            geometry_types=["Point"],
            required_cols=_REQUIRED_TOWER_COLS,
            mask_geom=mask_geom,
        )

    if layer == "generators":
        # All power=generator except wind, which the dedicated turbine layer
        # already renders.
        frame = _read_point_and_polygon(
            pbf_path, "power = 'generator'", mask_geom, _REQUIRED_GENERATOR_COLS
        )
        return drop_wind_generators(frame)

    # turbines: power=generator filtered to wind (source or method)
    frame = _read_point_and_polygon(
        pbf_path, "power = 'generator'", mask_geom, _REQUIRED_WIND_TURBINE_COLS
    )
    if frame.empty:
        return frame
    is_wind = _generator_is_wind(frame)
    return gpd.GeoDataFrame(frame[is_wind], geometry="geometry", crs="EPSG:4326").reset_index(drop=True)
