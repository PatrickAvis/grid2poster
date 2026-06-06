#!/usr/bin/env python3
"""Download NESO DNO and GSP boundary GeoJSON and normalize to WGS84."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from common import DATA_ZONES_DIR

DNO_URL = (
    "https://api.neso.energy/dataset/0e377f16-95e9-4c15-a1fc-49e06a39cfa0/"
    "resource/1c6a7dc0-1b6c-443a-bc67-5f7125649434/download/"
    "gb-dno-license-areas-20240503-as-geojson.geojson"
)
GSP_URL = (
    "https://api.neso.energy/dataset/2810092e-d4b2-472f-b955-d8bea01f9ec0/"
    "resource/08534dae-5408-4e31-8639-b579c8f1c50b/download/"
    "gsp_regions_20220314.geojson"
)


def download_geojson(url: str, dest: Path) -> gpd.GeoDataFrame:
    print(f"Downloading {url}…")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    print(f"Saved raw download: {dest}")
    return gpd.read_file(dest)


def normalize_dno(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = frame.copy()
    if out.crs is None:
        out = out.set_crs("EPSG:27700")
    out = out.to_crs("EPSG:4326")
    area_col = next((col for col in out.columns if col.lower() == "area"), None)
    dno_full_col = next((col for col in out.columns if col.lower() == "dno_full"), None)
    dno_col = next((col for col in out.columns if col.lower() == "dno"), None)
    id_col = next((col for col in out.columns if col.lower() == "id"), None)
    if area_col and dno_full_col:
        out["name"] = out[dno_full_col].astype(str) + " — " + out[area_col].astype(str)
    elif area_col:
        out["name"] = out[area_col].astype(str)
    elif dno_full_col:
        out["name"] = out[dno_full_col].astype(str)
    else:
        out["name"] = out.index.astype(str)
    if dno_col:
        out["operator"] = out[dno_col]
    if id_col:
        out["zone_id"] = out[id_col]
    keep = [col for col in ["name", "operator", "zone_id"] if col in out.columns]
    return out[keep + ["geometry"]]


def normalize_gsp(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    out = frame.copy()
    if out.crs is None:
        out = out.set_crs("EPSG:27700")
    out = out.to_crs("EPSG:4326")
    gsp_id_col = next((col for col in out.columns if col.lower() in {"gsps", "gsp", "gsp_id", "gspid"}), None)
    group_col = next((col for col in out.columns if col.lower() in {"gspgroup", "gsp_group", "gsp_name", "name"}), None)
    if gsp_id_col:
        out["gsp_id"] = out[gsp_id_col]
    if group_col:
        out["gsp_name"] = out[group_col]
    elif gsp_id_col:
        out["gsp_name"] = out[gsp_id_col]
    else:
        out["gsp_name"] = out.index.astype(str)
    keep = [col for col in ["gsp_id", "gsp_name", "name"] if col in out.columns]
    return out[keep + ["geometry"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch NESO DNO/GSP zone boundaries into data/zones/")
    parser.add_argument("--dno-output", type=Path, default=DATA_ZONES_DIR / "uk_dno_areas.geojson")
    parser.add_argument("--gsp-output", type=Path, default=DATA_ZONES_DIR / "uk_gsp_areas.geojson")
    parser.add_argument("--skip-dno", action="store_true")
    parser.add_argument("--skip-gsp", action="store_true")
    parser.add_argument("--dno-url", default=DNO_URL)
    parser.add_argument("--gsp-url", default=GSP_URL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.skip_dno:
        raw_path = args.dno_output.with_suffix(".raw.geojson")
        raw = download_geojson(args.dno_url, raw_path)
        normalized = normalize_dno(raw)
        normalized.to_file(args.dno_output, driver="GeoJSON")
        print(f"Wrote {args.dno_output} ({len(normalized)} features)")

    if not args.skip_gsp:
        raw_path = args.gsp_output.with_suffix(".raw.geojson")
        raw = download_geojson(args.gsp_url, raw_path)
        normalized = normalize_gsp(raw)
        normalized.to_file(args.gsp_output, driver="GeoJSON")
        print(f"Wrote {args.gsp_output} ({len(normalized)} features)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
