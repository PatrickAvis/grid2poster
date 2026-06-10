"""Manual UK plant assets absent from OSM exports."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from common import FILE_ENCODING, REPO_ROOT
from prepare import bucket_plant_row

MANUAL_PLANTS_PATH = (
    REPO_ROOT / "data" / "regions" / "uk" / "reference" / "editable" / "manual_plants.csv"
)

MANUAL_PLANT_COLUMNS = (
    "osm_id",
    "name",
    "operator",
    "plant:source",
    "plant:output:electricity",
    "latitude",
    "longitude",
    "capacity_mw",
    "source_bucket",
    "notes",
)


def load_manual_plants(path: Path = MANUAL_PLANTS_PATH) -> gpd.GeoDataFrame:
    if not path.exists():
        return gpd.GeoDataFrame(columns=list(MANUAL_PLANT_COLUMNS) + ["geometry"], crs="EPSG:4326")

    frame = pd.read_csv(path, comment="#")
    for col in MANUAL_PLANT_COLUMNS:
        if col not in frame.columns:
            frame[col] = None

    geometries = [
        Point(float(row["longitude"]), float(row["latitude"]))
        if pd.notna(row.get("longitude")) and pd.notna(row.get("latitude"))
        else None
        for _, row in frame.iterrows()
    ]
    gdf = gpd.GeoDataFrame(frame[list(MANUAL_PLANT_COLUMNS)], geometry=geometries, crs="EPSG:4326")
    gdf["power"] = "plant"
    gdf["generator:source"] = None
    gdf["generator:output:electricity"] = None
    if "source_bucket" not in gdf.columns or gdf["source_bucket"].isna().all():
        gdf["source_bucket"] = gdf.apply(bucket_plant_row, axis=1)
    return gdf


def merge_manual_plants(frame: gpd.GeoDataFrame, path: Path = MANUAL_PLANTS_PATH) -> gpd.GeoDataFrame:
    """Ensure manual plant assets are present in the ground-truth layer."""
    manual = load_manual_plants(path)
    if manual.empty:
        return frame

    if frame is None or frame.empty:
        print(f"Seeding plants layer from {len(manual):,} manual assets")
        return manual

    frame = frame.copy()
    if "osm_id" not in frame.columns:
        frame["osm_id"] = None

    existing_ids = {
        str(value).strip()
        for value in frame["osm_id"].dropna()
        if str(value).strip()
    }
    added = 0
    updated = 0
    manual_rows: list[gpd.GeoDataFrame] = []

    for _, row in manual.iterrows():
        osm_id = str(row.get("osm_id") or "").strip()
        if not osm_id:
            continue
        if osm_id in existing_ids:
            mask = frame["osm_id"].astype(str).str.strip() == osm_id
            for col in manual.columns:
                if col == "geometry":
                    continue
                if col in frame.columns:
                    frame.loc[mask, col] = row[col]
            frame.loc[mask, "geometry"] = row.geometry
            updated += 1
            continue
        manual_rows.append(gpd.GeoDataFrame([row], crs=manual.crs))
        added += 1

    if manual_rows:
        frame = pd.concat([frame, *manual_rows], ignore_index=True)
        frame = gpd.GeoDataFrame(frame, geometry="geometry", crs=frame.crs or manual.crs)

    if added or updated:
        print(f"Manual plants: added {added:,}, refreshed {updated:,} from {path.name}")
    return frame
