"""UK BMU reference data and OSM plant ↔ BMU mapping table."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests

from common import FILE_ENCODING, REPO_ROOT

ELEXON_BMUNITS_URL = "https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all?format=json"
BMU_REFERENCE_PATH = REPO_ROOT / "data" / "reference" / "uk_bmunits.json"
PLANT_BMU_MAP_PATH = REPO_ROOT / "data" / "reference" / "uk_plant_bmu_map.csv"
PLANT_BMU_MAP_JSON_PATH = REPO_ROOT / "data" / "reference" / "uk_plant_bmu_map.json"
# Legacy alias; migrated into uk_plant_bmu_map.csv on first propose run
BMU_OVERRIDES_PATH = REPO_ROOT / "data" / "reference" / "uk_bmu_overrides.csv"

MAP_COLUMNS = ("osm_id", "plant_name", "bmu_id", "ngc_bmu_id", "bmu_type", "source", "notes")
BMU_FIELDS = ("bmu_id", "ngc_bmu_id", "bmu_type")

NAME_SUFFIXES = (
    " power station",
    " wind farm",
    " solar farm",
    " solar park",
    " solar power plant",
    " energy storage system",
    " battery storage",
    " power plant",
    " bess",
)


def normalize_site_name(name: str | None) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", str(name)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    for suffix in NAME_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def fetch_bmunits(*, timeout: int = 120) -> list[dict[str, Any]]:
    response = requests.get(ELEXON_BMUNITS_URL, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Unexpected Elexon BMU response shape")
    return payload


def save_bmunits(records: list[dict[str, Any]], path: Path = BMU_REFERENCE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=FILE_ENCODING) as handle:
        json.dump(records, handle, indent=2)
    return path


def load_bmunits(path: Path = BMU_REFERENCE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"BMU reference not found: {path}\nRun: python scripts/fetch_bmu_reference.py",
        )
    with path.open(encoding=FILE_ENCODING) as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected BMU reference format in {path}")
    return payload


def match_bmunits_for_plant(plant_name: str | None, bmunits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_site_name(plant_name)
    if not normalized:
        return []

    exact = [row for row in bmunits if normalize_site_name(row.get("bmUnitName")) == normalized]
    if exact:
        return exact

    words = normalized.split()
    if len(words) >= 2:
        phrase = " ".join(words[:2])
        if len(phrase) >= 5:
            phrase_hits = [row for row in bmunits if phrase in normalize_site_name(row.get("bmUnitName"))]
            if phrase_hits:
                return phrase_hits

    if not words:
        return []

    token = words[0]
    if len(token) < 4:
        return []

    pattern = re.compile(rf"\b{re.escape(token)}\b")
    token_hits = [
        row for row in bmunits if pattern.search(normalize_site_name(row.get("bmUnitName")))
    ]
    if token_hits and len(token_hits) <= 30:
        return token_hits
    return []


def _index_bmunits(bmunits: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_elexon: dict[str, dict[str, Any]] = {}
    by_ngc: dict[str, dict[str, Any]] = {}
    for row in bmunits:
        elexon = str(row.get("elexonBmUnit") or "").strip()
        ngc = str(row.get("nationalGridBmUnit") or "").strip()
        if elexon:
            by_elexon[elexon.upper()] = row
        if ngc:
            by_ngc[ngc.upper()] = row
    return by_elexon, by_ngc


def bmu_row_to_map_fields(bmu: dict[str, Any]) -> dict[str, str | None]:
    return {
        "bmu_id": str(bmu.get("elexonBmUnit") or "").strip() or None,
        "ngc_bmu_id": str(bmu.get("nationalGridBmUnit") or "").strip() or None,
        "bmu_type": str(bmu.get("bmUnitType") or "").strip() or None,
    }


def _split_ids(value: str | None) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _empty_map_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(MAP_COLUMNS))


def load_plant_bmu_map(path: Path = PLANT_BMU_MAP_PATH) -> pd.DataFrame:
    if not path.exists():
        return _empty_map_frame()
    frame = pd.read_csv(path, comment="#")
    for col in MAP_COLUMNS:
        if col not in frame.columns:
            frame[col] = None
    return frame[list(MAP_COLUMNS)].copy()


def save_plant_bmu_map(frame: pd.DataFrame, path: Path = PLANT_BMU_MAP_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame[list(MAP_COLUMNS)].copy()
    out.to_csv(path, index=False)
    return path


def export_plant_bmu_map_json(
    frame: pd.DataFrame | None = None,
    *,
    csv_path: Path = PLANT_BMU_MAP_PATH,
    json_path: Path = PLANT_BMU_MAP_JSON_PATH,
) -> Path:
    if frame is None:
        frame = load_plant_bmu_map(csv_path)
    entries = []
    for _, row in frame.iterrows():
        entry = {col: (None if is_empty(row.get(col)) else str(row[col]).strip()) for col in MAP_COLUMNS}
        if not entry.get("osm_id") and not entry.get("plant_name"):
            continue
        entries.append(entry)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding=FILE_ENCODING) as handle:
        json.dump(entries, handle, indent=2)
    return json_path


def _map_row_key(osm_id: str | None, bmu_id: str | None, ngc_bmu_id: str | None) -> tuple[str, str, str]:
    return (
        str(osm_id or "").strip(),
        str(bmu_id or "").strip().upper(),
        str(ngc_bmu_id or "").strip().upper(),
    )


def map_contains(frame: pd.DataFrame, osm_id: str | None, bmu_id: str | None, ngc_bmu_id: str | None) -> bool:
    key = _map_row_key(osm_id, bmu_id, ngc_bmu_id)
    for _, row in frame.iterrows():
        if _map_row_key(row.get("osm_id"), row.get("bmu_id"), row.get("ngc_bmu_id")) == key:
            return True
    return False


def append_map_row(
    frame: pd.DataFrame,
    *,
    osm_id: str | None,
    plant_name: str | None,
    bmu_id: str | None,
    ngc_bmu_id: str | None,
    bmu_type: str | None,
    source: str,
    notes: str | None = None,
) -> pd.DataFrame:
    if map_contains(frame, osm_id, bmu_id, ngc_bmu_id):
        return frame
    row = {col: None for col in MAP_COLUMNS}
    row["osm_id"] = osm_id
    row["plant_name"] = plant_name
    row["bmu_id"] = bmu_id
    row["ngc_bmu_id"] = ngc_bmu_id
    row["bmu_type"] = bmu_type
    row["source"] = source
    row["notes"] = notes
    return pd.concat([frame, pd.DataFrame([row])], ignore_index=True)


def migrate_embedded_bmu_from_plants(plants: gpd.GeoDataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Move legacy bmu_* properties from plant GeoJSON into the map table."""
    if not any(col in plants.columns for col in BMU_FIELDS):
        return frame

    added = 0
    for _, plant in plants.iterrows():
        if all(is_empty(plant.get(field)) for field in BMU_FIELDS):
            continue
        osm_id = None if is_empty(plant.get("osm_id")) else str(plant["osm_id"])
        plant_name = None if is_empty(plant.get("name")) else str(plant["name"])
        bmu_ids = _split_ids(plant.get("bmu_id"))
        ngc_ids = _split_ids(plant.get("ngc_bmu_id"))
        types = _split_ids(plant.get("bmu_type"))
        count = max(len(bmu_ids), len(ngc_ids), len(types), 1)
        for index in range(count):
            bmu_id = bmu_ids[index] if index < len(bmu_ids) else (bmu_ids[0] if bmu_ids else None)
            ngc_id = ngc_ids[index] if index < len(ngc_ids) else (ngc_ids[0] if ngc_ids else None)
            bmu_type = types[index] if index < len(types) else (types[0] if types else None)
            before = len(frame)
            frame = append_map_row(
                frame,
                osm_id=osm_id,
                plant_name=plant_name,
                bmu_id=bmu_id,
                ngc_bmu_id=ngc_id,
                bmu_type=bmu_type,
                source="migrated",
            )
            if len(frame) > before:
                added += 1
    if added:
        print(f"Migrated {added:,} embedded BMU rows from plants GeoJSON into map table")
    return frame


def migrate_legacy_overrides(frame: pd.DataFrame) -> pd.DataFrame:
    if not BMU_OVERRIDES_PATH.exists():
        return frame
    legacy = pd.read_csv(BMU_OVERRIDES_PATH, comment="#")
    if legacy.empty or "plant_name" not in legacy.columns:
        return frame
    added = 0
    for _, row in legacy.iterrows():
        if is_empty(row.get("plant_name")):
            continue
        before = len(frame)
        frame = append_map_row(
            frame,
            osm_id=None,
            plant_name=str(row["plant_name"]),
            bmu_id=None if is_empty(row.get("bmu_id")) else str(row["bmu_id"]),
            ngc_bmu_id=None if is_empty(row.get("ngc_bmu_id")) else str(row["ngc_bmu_id"]),
            bmu_type=None if is_empty(row.get("bmu_type")) else str(row["bmu_type"]),
            source="manual",
            notes=None if is_empty(row.get("notes")) else str(row["notes"]),
        )
        if len(frame) > before:
            added += 1
    if added:
        print(f"Imported {added:,} legacy override rows into map table")
    return frame


def propose_plant_bmu_map(
    plants: gpd.GeoDataFrame,
    *,
    reference_path: Path = BMU_REFERENCE_PATH,
    map_path: Path = PLANT_BMU_MAP_PATH,
    migrate_embedded: bool = True,
) -> pd.DataFrame:
    frame = load_plant_bmu_map(map_path)
    frame = migrate_legacy_overrides(frame)
    if migrate_embedded:
        frame = migrate_embedded_bmu_from_plants(plants, frame)

    if not reference_path.exists():
        print("Skipping auto proposals: BMU reference not found")
        return frame

    bmunits = load_bmunits(reference_path)
    proposed = 0
    for _, plant in plants.iterrows():
        if is_empty(plant.get("name")):
            continue
        osm_id = None if is_empty(plant.get("osm_id")) else str(plant["osm_id"])
        plant_name = str(plant["name"])
        for bmu in match_bmunits_for_plant(plant_name, bmunits):
            fields = bmu_row_to_map_fields(bmu)
            before = len(frame)
            frame = append_map_row(
                frame,
                osm_id=osm_id,
                plant_name=plant_name,
                bmu_id=fields["bmu_id"],
                ngc_bmu_id=fields["ngc_bmu_id"],
                bmu_type=fields["bmu_type"],
                source="auto",
            )
            if len(frame) > before:
                proposed += 1

    print(f"BMU map: {len(frame):,} rows ({proposed:,} new auto proposals)")
    return frame


def plants_missing_bmu_map(
    plants: gpd.GeoDataFrame,
    map_frame: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if map_frame is None:
        map_frame = load_plant_bmu_map()

    mapped_osm = {
        str(value).strip()
        for value in map_frame["osm_id"].dropna()
        if str(value).strip()
    }
    mapped_names = {
        normalize_site_name(str(value))
        for value in map_frame["plant_name"].dropna()
        if normalize_site_name(str(value))
    }

    rows = []
    for _, plant in plants.iterrows():
        if is_empty(plant.get("name")):
            continue
        osm_id = None if is_empty(plant.get("osm_id")) else str(plant["osm_id"])
        if osm_id and osm_id in mapped_osm:
            continue
        name_key = normalize_site_name(str(plant["name"]))
        if name_key and name_key in mapped_names:
            continue
        rows.append({
            "osm_id": osm_id,
            "name": plant.get("name"),
            "operator": plant.get("operator"),
            "capacity_mw": plant.get("capacity_mw"),
            "source_bucket": plant.get("source_bucket"),
            "latitude": plant.get("latitude"),
            "longitude": plant.get("longitude"),
        })

    missing = pd.DataFrame(rows)
    if not missing.empty and "name" in missing.columns:
        missing = missing.sort_values("name")
    return missing.reset_index(drop=True)


def strip_bmu_from_plants(plants: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    frame = plants.copy()
    for field in BMU_FIELDS:
        if field in frame.columns:
            frame = frame.drop(columns=[field])
    return frame
