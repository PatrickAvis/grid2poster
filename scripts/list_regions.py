#!/usr/bin/env python3
"""List map catalog regions and predefined boundaries from regions/."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from region_catalog import (  # noqa: E402
    REGIONS_DIR,
    get_region,
    list_boundary_stems,
    list_exportable_region_ids,
    list_region_ids,
    resolve_boundary_rel_path,
)


def main() -> int:
    catalog_ids = set(list_region_ids())
    print("Map catalog regions (data/catalog.json):")
    for region_id in sorted(catalog_ids):
        region = get_region(region_id)
        layer_count = len(region.get("layers") or {})
        boundary = resolve_boundary_rel_path(region_id) or "—"
        print(f"  {region_id:28} {region['title']:32} layers={layer_count}  boundary={boundary}")

    print()
    print("Predefined boundaries (regions/):")
    for stem in list_boundary_stems():
        path = REGIONS_DIR / f"{stem}.geojson"
        on_disk = "yes" if path.exists() else "missing"
        rel = f"regions/{stem}.geojson"
        in_catalog = stem in catalog_ids or any(
            resolve_boundary_rel_path(rid) == rel for rid in catalog_ids
        )
        note = "in catalog" if in_catalog else "export-only"
        print(f"  {stem:28} file={on_disk:7}  {note}")

    print()
    print(f"Exportable region ids ({len(list_exportable_region_ids())}):")
    print("  " + ", ".join(list_exportable_region_ids()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
