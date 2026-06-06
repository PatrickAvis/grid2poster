#!/usr/bin/env python3
"""Build lightweight GeoJSON (and optional PMTiles) layers for the interactive map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from prepare import bucket_plant_source, parse_capacity_to_mw
from plants_sync import sync_uk_plants
from region_catalog import (
    catalog_layer_path,
    get_region,
    list_region_ids,
    map_path,
    raw_csv_path,
    raw_path,
    zone_raw_path,
)

WEB_LINE_COLS = [
    "power",
    "voltage",
    "voltage_kv",
    "name",
    "operator",
    "circuits",
    "cables",
    "frequency",
    "location",
]

WEB_PLANT_COLS = [
    "osm_id",
    "power",
    "name",
    "operator",
    "plant:source",
    "plant:output:electricity",
    "generator:source",
    "generator:output:electricity",
]

WEB_SUBSTATION_COLS = [
    "power",
    "name",
    "substation",
    "voltage",
    "operator",
    "ref",
    "frequency",
]

WEB_TURBINE_COLS = [
    "power",
    "name",
    "operator",
    "manufacturer",
    "model",
    "ref",
    "generator:source",
    "generator:method",
    "generator:output:electricity",
    "capacity_mw",
    "height_m",
    "rotor_diameter_m",
    "latitude",
    "longitude",
]

ZONE_KEEP_COLS = ["name", "operator", "gsp_id", "gsp_name", "dno", "zone_id", "zone_name", "id"]

LEGACY_POSTERS = REPO_ROOT / "posters"


def resolve_raw_source(region_id: str, layer: str) -> Path:
    path = raw_path(region_id, layer)
    if path.exists():
        return path
    if region_id == "uk":
        legacy = {
            "lines": "uk_powerlines.geojson",
            "plants": "uk_plants.geojson",
            "substations": "uk_substations.geojson",
            "turbines": "uk_wind_turbines.geojson",
        }
        legacy_path = LEGACY_POSTERS / legacy[layer]
        if legacy_path.exists():
            return legacy_path
    return path


def resolve_turbine_csv(region_id: str) -> Path:
    path = raw_csv_path(region_id, "turbines")
    if path.exists():
        return path
    if region_id == "uk":
        legacy = LEGACY_POSTERS / "uk_wind_turbines.csv"
        if legacy.exists():
            return legacy
    return path


def trim_columns(frame: gpd.GeoDataFrame, keep: list[str]) -> gpd.GeoDataFrame:
    cols = [col for col in keep if col in frame.columns]
    if not cols:
        return frame
    return frame[cols + ["geometry"]]


def write_geojson(frame: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_crs("EPSG:4326").to_file(path, driver="GeoJSON")
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Wrote {path.relative_to(REPO_ROOT)}: {len(frame):,} features, {size_mb:.1f} MB")


def build_transmission_lines(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    lines = gpd.read_file(source)
    transmission = lines[lines["power"] != "minor_line"].copy()
    print(f"Keeping {len(transmission):,}/{len(lines):,} features (dropped minor_line)")
    transmission = trim_columns(transmission, WEB_LINE_COLS)
    write_geojson(transmission, output)
    return transmission


def add_lat_lon_columns(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    reps = frame.geometry.representative_point()
    frame["longitude"] = reps.x
    frame["latitude"] = reps.y
    return frame


def build_plants_web(source: Path, output: Path, *, region_id: str = "uk") -> gpd.GeoDataFrame:
    if region_id == "uk":
        return sync_uk_plants(output, raw_source=source)

    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    frame = trim_columns(frame, WEB_PLANT_COLS)
    frame = add_lat_lon_columns(frame)
    capacity_raw = frame.get("plant:output:electricity")
    if capacity_raw is not None:
        frame["capacity_mw"] = capacity_raw.apply(parse_capacity_to_mw)
    source_raw = frame.get("plant:source")
    if source_raw is not None:
        frame["source_bucket"] = source_raw.apply(bucket_plant_source)
    write_geojson(frame, output)
    return frame


def build_substations_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    frame = trim_columns(frame, WEB_SUBSTATION_COLS)
    frame = add_lat_lon_columns(frame)
    write_geojson(frame, output)
    return frame


def build_turbines_web(source_csv: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source_csv.name}…")
    available = pd.read_csv(source_csv, nrows=0).columns.tolist()
    keep = [col for col in WEB_TURBINE_COLS if col in available]
    if "latitude" not in keep or "longitude" not in keep:
        raise ValueError(f"{source_csv} must include latitude and longitude columns")

    frame = pd.read_csv(source_csv, usecols=keep, low_memory=False)
    frame = frame.dropna(subset=["latitude", "longitude"])
    frame["latitude"] = frame["latitude"].round(5)
    frame["longitude"] = frame["longitude"].round(5)
    geometry = gpd.points_from_xy(frame["longitude"], frame["latitude"])
    turbines = gpd.GeoDataFrame(frame, geometry=geometry, crs="EPSG:4326")
    write_geojson(turbines, output)
    return turbines


def build_zones_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    keep = [col for col in ZONE_KEEP_COLS if col in frame.columns]
    if not keep:
        keep = [col for col in frame.columns if col != frame.geometry.name and not col.startswith("bbox")]
    frame = trim_columns(frame, keep)
    write_geojson(frame, output)
    return frame


def default_output(region_id: str, layer: str) -> Path:
    catalog_path = catalog_layer_path(region_id, layer)
    if catalog_path is not None:
        return catalog_path
    return map_path(region_id, layer)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare lightweight map layers from data/catalog.json")
    parser.add_argument(
        "--region",
        "-r",
        default="uk",
        choices=list_region_ids(),
        help="Region id from data/catalog.json",
    )
    parser.add_argument("--lines-source", type=Path, default=None)
    parser.add_argument("--lines-output", type=Path, default=None)
    parser.add_argument("--plants-source", type=Path, default=None)
    parser.add_argument("--plants-output", type=Path, default=None)
    parser.add_argument("--substations-source", type=Path, default=None)
    parser.add_argument("--substations-output", type=Path, default=None)
    parser.add_argument("--turbines-source", type=Path, default=None)
    parser.add_argument("--turbines-output", type=Path, default=None)
    parser.add_argument("--dno-source", type=Path, default=None)
    parser.add_argument("--dno-output", type=Path, default=None)
    parser.add_argument("--gsp-source", type=Path, default=None)
    parser.add_argument("--gsp-output", type=Path, default=None)
    parser.add_argument("--skip-lines", action="store_true")
    parser.add_argument("--skip-plants", action="store_true")
    parser.add_argument("--skip-substations", action="store_true")
    parser.add_argument("--skip-turbines", action="store_true")
    parser.add_argument("--skip-zones", action="store_true")
    parser.add_argument(
        "--emit-pmtiles",
        action="store_true",
        help="After GeoJSON prep, run scripts/build_tiles.py for pmtiles layers in catalog",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    region = get_region(args.region)
    layers = region.get("layers", {})

    if args.lines_source is None:
        args.lines_source = resolve_raw_source(args.region, "lines")
    if args.plants_source is None:
        args.plants_source = resolve_raw_source(args.region, "plants")
    if args.substations_source is None:
        args.substations_source = resolve_raw_source(args.region, "substations")
    if args.turbines_source is None:
        args.turbines_source = resolve_turbine_csv(args.region)

    if args.lines_output is None and "lines" in layers:
        args.lines_output = default_output(args.region, "lines")
    if args.plants_output is None and "plants" in layers:
        args.plants_output = default_output(args.region, "plants")
    if args.substations_output is None and "substations" in layers:
        args.substations_output = default_output(args.region, "substations")
    if args.turbines_output is None and "turbines" in layers:
        args.turbines_output = default_output(args.region, "turbines")
    if args.dno_output is None and "dno" in layers:
        args.dno_output = default_output(args.region, "dno")
    if args.gsp_output is None and "gsp" in layers:
        args.gsp_output = default_output(args.region, "gsp")

    if not args.skip_lines and "lines" in layers:
        if not args.lines_source.exists():
            raise FileNotFoundError(f"Missing source file: {args.lines_source}")
        build_transmission_lines(args.lines_source, args.lines_output)

    if not args.skip_plants and "plants" in layers:
        if args.plants_source.exists():
            build_plants_web(args.plants_source, args.plants_output, region_id=args.region)
        else:
            print(f"Skipping plants: {args.plants_source} not found")

    if not args.skip_substations and "substations" in layers:
        if args.substations_source.exists():
            build_substations_web(args.substations_source, args.substations_output)
        else:
            print(f"Skipping substations: {args.substations_source} not found")

    if not args.skip_turbines and "turbines" in layers:
        if args.turbines_source.exists():
            build_turbines_web(args.turbines_source, args.turbines_output)
        else:
            print(f"Skipping turbines: {args.turbines_source} not found")

    if not args.skip_zones:
        if args.dno_source is None:
            args.dno_source = zone_raw_path(args.region, "dno")
        if args.gsp_source is None:
            args.gsp_source = zone_raw_path(args.region, "gsp")
        if "dno" in layers:
            if args.dno_source.exists():
                build_zones_web(args.dno_source, args.dno_output)
            else:
                print(f"Skipping DNO zones: {args.dno_source} not found")
        if "gsp" in layers:
            if args.gsp_source.exists():
                build_zones_web(args.gsp_source, args.gsp_output)
            else:
                print(f"Skipping GSP zones: {args.gsp_source} not found")

    if args.emit_pmtiles:
        import subprocess

        build = REPO_ROOT / "scripts" / "build_tiles.py"
        result = subprocess.run(
            [sys.executable, str(build), "--region", args.region],
            check=False,
        )
        return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
