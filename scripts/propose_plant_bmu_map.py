#!/usr/bin/env python3
"""Maintain uk_plant_bmu_map.csv: migrate embedded BMU, propose auto matches, export JSON for map."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bmu_data import (
    BMU_REFERENCE_PATH,
    PLANT_BMU_MAP_PATH,
    export_plant_bmu_map_json,
    fetch_bmunits,
    load_bmunits,
    plants_missing_bmu_map,
    propose_plant_bmu_map,
    save_bmunits,
    save_plant_bmu_map,
    write_bmu_coverage_reports,
)
from region_catalog import catalog_layer_path, map_path, raw_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the OSM plant ↔ BMU mapping table (uk_plant_bmu_map.csv).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--plants",
        type=Path,
        default=None,
        help="Plants ground-truth GeoJSON (default: data/map/uk/uk_plants_web.geojson)",
    )
    parser.add_argument(
        "--map",
        type=Path,
        default=PLANT_BMU_MAP_PATH,
        help="Editable mapping table CSV",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Download fresh Elexon BMU reference before proposing",
    )
    parser.add_argument(
        "--no-migrate-embedded",
        action="store_true",
        help="Skip one-time migration of bmu_* fields from plants GeoJSON",
    )
    parser.add_argument(
        "--list-unmatched",
        type=Path,
        metavar="CSV",
        help="Write plants with no map entry to this CSV",
    )
    parser.add_argument(
        "--skip-coverage-reports",
        action="store_true",
        help="Skip writing unmapped displayable, candidate match, and reference-only BMU CSVs",
    )
    return parser.parse_args()


def default_plants_path() -> Path:
    catalog_path = catalog_layer_path("uk", "plants")
    if catalog_path is not None:
        return catalog_path
    return map_path("uk", "plants")


def main() -> int:
    args = parse_args()
    plants_path = args.plants or default_plants_path()

    if args.fetch:
        records = fetch_bmunits()
        save_bmunits(records)
        print(f"Fetched {len(records):,} BMUs from Elexon")

    if not plants_path.exists():
        print(f"Plants file not found: {plants_path}", file=sys.stderr)
        print("Run: python scripts/sync_uk_plants.py", file=sys.stderr)
        return 1

    plants = gpd.read_file(plants_path)
    frame = propose_plant_bmu_map(
        plants,
        map_path=args.map,
        migrate_embedded=not args.no_migrate_embedded,
    )
    save_plant_bmu_map(frame, args.map)
    json_path = export_plant_bmu_map_json(frame)
    print(f"Wrote {args.map.relative_to(REPO_ROOT)}")
    print(f"Wrote {json_path.relative_to(REPO_ROOT)}")

    if args.list_unmatched:
        missing = plants_missing_bmu_map(plants, frame)
        args.list_unmatched.parent.mkdir(parents=True, exist_ok=True)
        missing.to_csv(args.list_unmatched, index=False)
        try:
            rel = args.list_unmatched.resolve().relative_to(REPO_ROOT)
        except ValueError:
            rel = args.list_unmatched
        print(f"Unmatched plants: {len(missing):,} -> {rel}")

    if not args.skip_coverage_reports:
        if BMU_REFERENCE_PATH.exists():
            bmunits = load_bmunits(BMU_REFERENCE_PATH)
            write_bmu_coverage_reports(plants, frame, bmunits)
        else:
            print("Skipping coverage reports: BMU reference not found")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
