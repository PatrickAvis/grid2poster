#!/usr/bin/env python3
"""Export OSM power infrastructure for any catalog region (no poster render)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import osmnx as ox

from export_io import save_csv, save_geojson
from osm_data import (
    fetch_power_features,
    fetch_power_features_single,
    fetch_power_plants,
    fetch_power_substations,
    fetch_wind_turbines,
    get_country_boundary,
    load_boundary_from_geojson,
)
from prepare import prepare_lines, prepare_wind_turbines
from region_catalog import (
    get_region,
    list_exportable_region_ids,
    raw_dir,
    region_boundary_path,
    region_country,
)

DEFAULT_CABLE_BUFFER = {
    "uk": 600.0,
    "fr": 400.0,
    "europe": 600.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export OSM power layers for a catalog region to data/raw/{region}/.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--region",
        "-r",
        required=True,
        choices=list_exportable_region_ids(),
        help="Region id from data/catalog.json or regions/*.geojson (see regions/manifest.json)",
    )
    parser.add_argument("--country", help="Override Nominatim country name (default: from catalog)")
    parser.add_argument("--boundary-geojson", type=Path, help="Override boundary GeoJSON path")
    parser.add_argument("--all", action="store_true", help="Export lines, plants, substations, and turbines")
    parser.add_argument("--include-minor-lines", action="store_true", help="Include power=minor_line")
    parser.add_argument(
        "--include-cables",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include power=cable (submarine/interconnectors)",
    )
    parser.add_argument("--cable-sea-buffer-km", type=float, default=None)
    parser.add_argument("--tile-size-km", type=float, default=400.0)
    parser.add_argument("--tile-delay", type=float, default=30.0)
    parser.add_argument("--single-query", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--overpass-endpoint", help="Override Overpass API URL")
    parser.add_argument("--verbose-osmnx", action="store_true")
    parser.add_argument("--geojson", action="store_true", default=True)
    parser.add_argument("--no-geojson", action="store_false", dest="geojson")
    parser.add_argument("--csv", action="store_true", default=True)
    parser.add_argument("--no-csv", action="store_false", dest="csv")
    parser.add_argument("--skip-lines", action="store_true")
    parser.add_argument("--skip-plants", action="store_true")
    parser.add_argument("--skip-substations", action="store_true")
    parser.add_argument("--skip-turbines", action="store_true")
    return parser.parse_args()


def write_exports(frame, base: Path, *, geojson: bool, csv: bool) -> None:
    if geojson:
        path = base.with_suffix(".geojson")
        save_geojson(frame, path)
        print(f"Saved GeoJSON: {path}")
    if csv:
        path = base.with_suffix(".csv")
        save_csv(frame, path)
        print(f"Saved CSV: {path}")


def resolve_boundary(region_id: str, country: str, boundary_path: Path | None, use_cache: bool):
    if boundary_path:
        if not boundary_path.exists():
            raise FileNotFoundError(
                f"Boundary GeoJSON not found: {boundary_path}\n"
                f"Predefined boundaries live under regions/ — see regions/manifest.json.",
            )
        print(f"Loading boundary from {boundary_path}")
        return load_boundary_from_geojson(boundary_path, country)
    print(f"Resolving boundary for {country}…")
    return get_country_boundary(country, use_cache=use_cache)


def main() -> int:
    args = parse_args()
    if args.all:
        args.skip_lines = False
        args.skip_plants = False
        args.skip_substations = False
        args.skip_turbines = False

    region = get_region(args.region)
    if region.get("children") and not args.country and not args.boundary_geojson:
        print(
            f"Region {args.region!r} is a parent with children {region.get('children')}. "
            "Set --country or --boundary-geojson, or export a child region.",
            file=sys.stderr,
        )
        return 2

    country = args.country or region_country(args.region)
    boundary_path = args.boundary_geojson or region_boundary_path(args.region)
    cable_buffer_km = (
        args.cable_sea_buffer_km
        if args.cable_sea_buffer_km is not None
        else DEFAULT_CABLE_BUFFER.get(args.region, 400.0)
    )
    if not args.include_cables:
        cable_buffer_km = 0.0

    out = raw_dir(args.region)

    ox.settings.use_cache = not args.no_cache
    ox.settings.log_console = bool(args.verbose_osmnx)
    ox.settings.requests_timeout = 180
    if args.overpass_endpoint:
        ox.settings.overpass_url = args.overpass_endpoint
        print(f"Using Overpass endpoint: {args.overpass_endpoint}")

    boundary_wgs84 = resolve_boundary(args.region, country, boundary_path, use_cache=not args.no_cache)

    if not args.skip_lines:
        print("Fetching power lines…")
        if args.single_query:
            raw_lines = fetch_power_features_single(
                country=country,
                boundary=boundary_wgs84,
                include_minor_lines=args.include_minor_lines,
                include_cables=args.include_cables,
                sea_buffer_km=cable_buffer_km,
                render_crs="EPSG:3857",
                use_cache=not args.no_cache,
            )
        else:
            raw_lines = fetch_power_features(
                country=country,
                boundary=boundary_wgs84,
                include_minor_lines=args.include_minor_lines,
                include_cables=args.include_cables,
                tile_size_km=args.tile_size_km,
                render_crs="EPSG:3857",
                sea_buffer_km=cable_buffer_km,
                use_cache=not args.no_cache,
                tile_delay=args.tile_delay,
            )
        lines = prepare_lines(raw_lines, boundary_wgs84, "EPSG:3857", cable_sea_buffer_km=cable_buffer_km)
        export = lines.to_crs("EPSG:4326").drop(columns=["sort_voltage"], errors="ignore")
        write_exports(export, out / "powerlines", geojson=args.geojson, csv=args.csv)

    if not args.skip_plants:
        print("Fetching power plants…")
        plants = fetch_power_plants(
            country=country,
            boundary=boundary_wgs84,
            tile_size_km=args.tile_size_km,
            render_crs="EPSG:3857",
            use_cache=not args.no_cache,
            tile_delay=args.tile_delay,
        )
        write_exports(plants, out / "plants", geojson=args.geojson, csv=args.csv)

    if not args.skip_substations:
        print("Fetching substations…")
        substations = fetch_power_substations(
            country=country,
            boundary=boundary_wgs84,
            tile_size_km=args.tile_size_km,
            render_crs="EPSG:3857",
            use_cache=not args.no_cache,
            tile_delay=args.tile_delay,
        )
        write_exports(substations, out / "substations", geojson=args.geojson, csv=args.csv)

    if not args.skip_turbines:
        print("Fetching wind turbines…")
        turbines = prepare_wind_turbines(
            fetch_wind_turbines(
                country=country,
                boundary=boundary_wgs84,
                tile_size_km=args.tile_size_km,
                render_crs="EPSG:3857",
                use_cache=not args.no_cache,
                tile_delay=args.tile_delay,
            )
        )
        print(f"Wind turbines fetched: {len(turbines):,}")
        write_exports(turbines, out / "wind_turbines", geojson=args.geojson, csv=args.csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
