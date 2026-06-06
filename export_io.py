"""Shared GeoJSON/CSV export helpers for poster and map ingest CLIs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def geojson_property_value(value: Any) -> Any:
    """Convert OSMnx property values to types the GeoJSON writer can serialize."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set, dict)):
        return json.dumps(value, ensure_ascii=True, default=str)
    return str(value)


def save_geojson(frame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    export = frame.to_crs("EPSG:4326").copy()
    geometry_col = export.geometry.name
    for col in export.columns:
        if col != geometry_col:
            export[col] = export[col].map(geojson_property_value)
    export.to_file(path, driver="GeoJSON")


def save_csv(frame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    export = frame.to_crs("EPSG:4326").copy()
    geometry_col = export.geometry.name
    representative_points = export.geometry.representative_point()
    export["latitude"] = representative_points.y
    export["longitude"] = representative_points.x
    export["geometry_wkt"] = export.geometry.to_wkt()
    for col in export.columns:
        if col not in {geometry_col, "geometry_wkt"}:
            export[col] = export[col].map(geojson_property_value)
    export.drop(columns=[geometry_col]).to_csv(path, index=False)
