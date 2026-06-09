#!/usr/bin/env python3
"""Sync UK plants ground-truth GeoJSON (OSM only). Use propose_plant_bmu_map.py for BMU links."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from plants_sync import sync_uk_plants
from region_catalog import catalog_layer_path, map_path, raw_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update data/regions/uk/map/bmu_sites_web.geojson (OSM power=plant site layer). "
            "Existing property values are kept; only blank fields are filled from OSM export."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=None,
        help="Editable BMU-mapped sites GeoJSON (default: data/regions/uk/map/bmu_sites_web.geojson)",
    )
    parser.add_argument(
        "--raw-source",
        type=Path,
        default=None,
        help="OSM plants export used to fill gaps and add new features",
    )
    parser.add_argument(
        "--skip-osm",
        action="store_true",
        help="Reload and rewrite ground-truth file without merging OSM export",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Discard ground-truth edits and rebuild from raw OSM export",
    )
    return parser.parse_args()


def default_ground_truth_path() -> Path:
    catalog_path = catalog_layer_path("uk", "plants")
    if catalog_path is not None:
        return catalog_path
    return map_path("uk", "plants")


def main() -> int:
    args = parse_args()
    ground_truth = args.ground_truth or default_ground_truth_path()
    if args.skip_osm:
        raw_source = None
    else:
        raw_source = args.raw_source or raw_path("uk", "plants")

    try:
        sync_uk_plants(
            ground_truth,
            raw_source=raw_source,
            force_rebuild=args.force,
        )
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    print("BMU links: python scripts/propose_plant_bmu_map.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
