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
    catalog_data_path,
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

WEB_GENERATOR_COLS = [
    "osm_id",
    "power",
    "name",
    "operator",
    "generator:source",
    "generator:method",
    "generator:type",
    "generator:output:electricity",
]

WEB_CONVERTER_COLS = [
    "power",
    "name",
    "operator",
    "converter",
    "voltage",
    "frequency",
    "rating",
]

WEB_EQUIPMENT_COLS = [
    "power",
    "name",
    "operator",
    "voltage",
    "location",
    "ref",
]

WEB_TOWER_COLS = [
    "power",
    "ref",
    "operator",
    "name",
    "height",
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

ZONE_KEEP_COLS = [
    "name",
    "operator",
    "gsp_id",
    "gsp_name",
    "dno",
    "zone_id",
    "zone_name",
    "tariff_zone",
    "id",
    "dno_zone_id",
    "dno_name",
    "dno_operator",
    "boundary_id",
]

def resolve_raw_source(region_id: str, layer: str) -> Path:
    return raw_path(region_id, layer)


def resolve_turbine_csv(region_id: str) -> Path:
    return raw_csv_path(region_id, "turbines")


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


def build_generators_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    frame = trim_columns(frame, WEB_GENERATOR_COLS)
    frame = add_lat_lon_columns(frame)
    capacity_raw = frame.get("generator:output:electricity")
    if capacity_raw is not None:
        frame["capacity_mw"] = capacity_raw.apply(parse_capacity_to_mw)
    source_raw = frame.get("generator:source")
    if source_raw is not None:
        frame["source_bucket"] = source_raw.apply(bucket_plant_source)
    write_geojson(frame, output)
    return frame


def build_converters_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    frame = trim_columns(frame, WEB_CONVERTER_COLS)
    frame = add_lat_lon_columns(frame)
    write_geojson(frame, output)
    return frame


def build_equipment_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    frame = trim_columns(frame, WEB_EQUIPMENT_COLS)
    frame = add_lat_lon_columns(frame)
    write_geojson(frame, output)
    return frame


def build_towers_web(source: Path, output: Path) -> gpd.GeoDataFrame:
    print(f"Reading {source.name}…")
    frame = gpd.read_file(source)
    points = frame[frame.geometry.type == "Point"].copy()
    print(f"Keeping {len(points):,}/{len(frame):,} tower points")
    points = trim_columns(points, WEB_TOWER_COLS)
    write_geojson(points, output)
    return points


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


def assign_gsp_parent_dno(gsp: gpd.GeoDataFrame, dno: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Annotate each GSP region with the DNO area it overlaps most."""
    if gsp.empty or dno.empty:
        return gsp

    gsp_projected = gsp.to_crs("EPSG:27700")
    dno_projected = dno.to_crs("EPSG:27700")
    assignments = []

    for _, gsp_row in gsp_projected.iterrows():
        best_area = 0.0
        best_dno = None
        for _, dno_row in dno_projected.iterrows():
            if not gsp_row.geometry.intersects(dno_row.geometry):
                continue
            area = gsp_row.geometry.intersection(dno_row.geometry).area
            if area > best_area:
                best_area = area
                best_dno = dno_row
        assignments.append(best_dno)

    result = gsp.copy()
    result["dno_zone_id"] = [row.get("zone_id") if row is not None else None for row in assignments]
    result["dno_name"] = [row.get("name") if row is not None else None for row in assignments]
    result["dno_operator"] = [row.get("operator") if row is not None else None for row in assignments]
    return result


def default_output(region_id: str, layer: str) -> Path:
    # PMTiles layers carry a separate GeoJSON source that tippecanoe tiles from;
    # the prep step must write that GeoJSON, not the .pmtiles archive path.
    region = get_region(region_id)
    layer_cfg = region.get("layers", {}).get(layer)
    if layer_cfg and layer_cfg.get("type") == "pmtiles" and layer_cfg.get("geojsonSource"):
        return catalog_data_path(layer_cfg["geojsonSource"])
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
    parser.add_argument("--generators-source", type=Path, default=None)
    parser.add_argument("--generators-output", type=Path, default=None)
    parser.add_argument("--converters-source", type=Path, default=None)
    parser.add_argument("--converters-output", type=Path, default=None)
    parser.add_argument("--equipment-source", type=Path, default=None)
    parser.add_argument("--equipment-output", type=Path, default=None)
    parser.add_argument("--towers-source", type=Path, default=None)
    parser.add_argument("--towers-output", type=Path, default=None)
    parser.add_argument("--dno-source", type=Path, default=None)
    parser.add_argument("--dno-output", type=Path, default=None)
    parser.add_argument("--gsp-source", type=Path, default=None)
    parser.add_argument("--gsp-output", type=Path, default=None)
    parser.add_argument("--generation-zones-source", type=Path, default=None)
    parser.add_argument("--generation-zones-output", type=Path, default=None)
    parser.add_argument("--etys-boundaries-source", type=Path, default=None)
    parser.add_argument("--etys-boundaries-output", type=Path, default=None)
    parser.add_argument("--skip-lines", action="store_true")
    parser.add_argument("--skip-plants", action="store_true")
    parser.add_argument("--skip-substations", action="store_true")
    parser.add_argument("--skip-turbines", action="store_true")
    parser.add_argument("--skip-generators", action="store_true")
    parser.add_argument("--skip-converters", action="store_true")
    parser.add_argument("--skip-equipment", action="store_true")
    parser.add_argument("--skip-towers", action="store_true")
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
    if args.generators_source is None:
        args.generators_source = resolve_raw_source(args.region, "generators")
    if args.converters_source is None:
        args.converters_source = resolve_raw_source(args.region, "converters")
    if args.equipment_source is None:
        args.equipment_source = resolve_raw_source(args.region, "equipment")
    if args.towers_source is None:
        args.towers_source = resolve_raw_source(args.region, "towers")

    if args.lines_output is None and "lines" in layers:
        args.lines_output = default_output(args.region, "lines")
    if args.plants_output is None and "plants" in layers:
        args.plants_output = default_output(args.region, "plants")
    if args.substations_output is None and "substations" in layers:
        args.substations_output = default_output(args.region, "substations")
    if args.turbines_output is None and "turbines" in layers:
        args.turbines_output = default_output(args.region, "turbines")
    if args.generators_output is None and "generators" in layers:
        args.generators_output = default_output(args.region, "generators")
    if args.converters_output is None and "converters" in layers:
        args.converters_output = default_output(args.region, "converters")
    if args.equipment_output is None and "equipment" in layers:
        args.equipment_output = default_output(args.region, "equipment")
    if args.towers_output is None and "towers" in layers:
        args.towers_output = default_output(args.region, "towers")
    if args.dno_output is None and "dno" in layers:
        args.dno_output = default_output(args.region, "dno")
    if args.gsp_output is None and "gsp" in layers:
        args.gsp_output = default_output(args.region, "gsp")
    if args.generation_zones_output is None and "generation_zones" in layers:
        args.generation_zones_output = default_output(args.region, "generation_zones")
    if args.etys_boundaries_output is None and "etys_boundaries" in layers:
        args.etys_boundaries_output = default_output(args.region, "etys_boundaries")

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

    if not args.skip_generators and "generators" in layers:
        if args.generators_source.exists():
            build_generators_web(args.generators_source, args.generators_output)
        else:
            print(f"Skipping generators: {args.generators_source} not found")

    if not args.skip_converters and "converters" in layers:
        if args.converters_source.exists():
            build_converters_web(args.converters_source, args.converters_output)
        else:
            print(f"Skipping converters: {args.converters_source} not found")

    if not args.skip_equipment and "equipment" in layers:
        if args.equipment_source.exists():
            build_equipment_web(args.equipment_source, args.equipment_output)
        else:
            print(f"Skipping equipment: {args.equipment_source} not found")

    if not args.skip_towers and "towers" in layers:
        if args.towers_source.exists():
            build_towers_web(args.towers_source, args.towers_output)
        else:
            print(f"Skipping towers: {args.towers_source} not found")

    if not args.skip_zones:
        dno_frame = None
        gsp_frame = None
        if args.dno_source is None:
            args.dno_source = zone_raw_path(args.region, "dno")
        if args.gsp_source is None:
            args.gsp_source = zone_raw_path(args.region, "gsp")
        if args.generation_zones_source is None:
            args.generation_zones_source = zone_raw_path(args.region, "generation")
        if args.etys_boundaries_source is None:
            args.etys_boundaries_source = zone_raw_path(args.region, "etys")
        if "dno" in layers:
            if args.dno_source.exists():
                dno_frame = build_zones_web(args.dno_source, args.dno_output)
            else:
                print(f"Skipping DNO zones: {args.dno_source} not found")
        if "gsp" in layers:
            if args.gsp_source.exists():
                gsp_frame = build_zones_web(args.gsp_source, args.gsp_output)
            else:
                print(f"Skipping GSP zones: {args.gsp_source} not found")
        if "generation_zones" in layers:
            if args.generation_zones_source.exists():
                build_zones_web(args.generation_zones_source, args.generation_zones_output)
            else:
                print(f"Skipping generation zones: {args.generation_zones_source} not found")
        if "etys_boundaries" in layers:
            if args.etys_boundaries_source.exists():
                build_zones_web(args.etys_boundaries_source, args.etys_boundaries_output)
            else:
                print(f"Skipping ETYS boundaries: {args.etys_boundaries_source} not found")
        if args.region == "uk" and dno_frame is not None and gsp_frame is not None:
            gsp_frame = assign_gsp_parent_dno(gsp_frame, dno_frame)
            write_geojson(gsp_frame, args.gsp_output)

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
