#!/usr/bin/env python3
"""Surgical cleanup of plant_bmu_links.csv — removes legacy auto-link pollution."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from bmu_data import (  # noqa: E402
    BMU_REFERENCE_PATH,
    GENERIC_PLANT_NAMES,
    PLANT_BMU_MAP_PATH,
    append_map_row,
    bmu_alias_names,
    bmu_row_to_map_fields,
    classify_bmu,
    dedupe_bare_osm_map_rows,
    load_bmunits,
    load_plant_bmu_map,
    normalize_site_name,
    save_plant_bmu_map,
)

KEEP_VIRTUAL = frozenset({"V__PHABI004", "V__PHABI006"})
AD_PLANT_OSM = "way/921428508"
GENERIC_WIND_FARM_OSM = frozenset({"way/616340682", "way/616339818"})
DRAX_COAL_OCGT = frozenset(
    {"T_DRAXX-5", "T_DRAXX-6", "T_DRAXX-9G", "T_DRAXX-10G", "T_DRAXX-12G"}
)
HORNSEA2_OSM = "11343101"
HORNSEA1_UNITS = frozenset({"T_HOWAO-1", "T_HOWAO-2", "T_HOWAO-3"})


def _bmu_id(row) -> str:
    return str(row.get("bmu_id") or "").strip().upper()


def _osm_id(row) -> str:
    return str(row.get("osm_id") or "").strip()


def match_score(row, by_elexon: dict) -> int:
    bid = _bmu_id(row)
    b = by_elexon.get(bid, {})
    pname = normalize_site_name(str(row.get("plant_name") or ""))
    if pname in GENERIC_PLANT_NAMES:
        return -1
    best = 0
    for _, alias in bmu_alias_names(b):
        an = normalize_site_name(alias)
        if pname == an:
            return 3
        if pname and an and (pname in an or an in pname):
            best = max(best, 2)
        if (
            pname
            and an
            and pname.split()[0] == an.split()[0]
            and len(pname.split()[0]) >= 4
        ):
            best = max(best, 1)
    return best


def should_remove_row(row) -> bool:
    bid = _bmu_id(row)
    oid = _osm_id(row)
    source = str(row.get("source") or "").strip().lower()
    pname = normalize_site_name(str(row.get("plant_name") or ""))

    if bid in DRAX_COAL_OCGT:
        return True

    if bid == "T_BEINW-1" and "baillie" in oid:
        return True

    if bid in HORNSEA1_UNITS and oid == HORNSEA2_OSM:
        return True

    if oid == AD_PLANT_OSM:
        return True

    if oid in GENERIC_WIND_FARM_OSM:
        return True

    if source == "auto":
        if bid.startswith("2__") or bid.startswith("I_"):
            return True
        if bid.startswith("V__") and bid not in KEEP_VIRTUAL:
            return True
        if pname in GENERIC_PLANT_NAMES:
            return True

    return False


def dedupe_osm_prefix(frame):
    before = len(frame)
    frame = dedupe_bare_osm_map_rows(frame)
    return frame, before - len(frame)


def dedupe_multi_site(frame, by_elexon: dict):
    """Keep one site per displayable T/E/G BMU — best name match wins."""
    drop_idx: list = []
    bmu_keys = frame["bmu_id"].astype(str).str.strip().str.upper()
    for bid, group in frame.groupby(bmu_keys):
        if not bid:
            continue
        b = by_elexon.get(bid, {})
        if classify_bmu(b) != "displayable":
            continue
        if str(b.get("bmUnitType") or "") not in {"T", "E", "G"}:
            continue
        if len(group) <= 1:
            continue

        scored = []
        for idx, row in group.iterrows():
            score = match_score(row, by_elexon)
            source = str(row.get("source") or "").strip().lower()
            if source == "manual":
                score += 10
            scored.append((idx, score, source, row))

        viable = [item for item in scored if item[1] >= 2 or item[2] == "manual"]
        if not viable:
            drop_idx.extend(group.index.tolist())
            continue

        def site_rank(item):
            idx, score, source, row = item
            oid = _osm_id(row)
            prefixed = 1 if "/" in oid and not oid.startswith("manual/") else 0
            manual = 1 if source == "manual" else 0
            return (score, manual, prefixed, -len(str(row.get("plant_name") or "")))

        viable.sort(key=site_rank, reverse=True)
        keep_idx = viable[0][0]
        drop_idx.extend(idx for idx in group.index if idx != keep_idx)

    if drop_idx:
        frame = frame.drop(index=drop_idx).reset_index(drop=True)
    return frame, len(drop_idx)


def add_fixes(frame, by_elexon: dict):
    additions = [
        (
            HORNSEA2_OSM,
            "Hornsea 2 Offshore Wind Farm",
            "T_HOWBO-1",
            "manual",
            "Hornsea 2 unit 1 (replaces wrongly linked HORNSEA_1A)",
        ),
        (
            HORNSEA2_OSM,
            "Hornsea 2 Offshore Wind Farm",
            "T_HOWBO-2",
            "manual",
            "Hornsea 2 unit 2",
        ),
        (
            HORNSEA2_OSM,
            "Hornsea 2 Offshore Wind Farm",
            "T_HOWBO-3",
            "manual",
            "Hornsea 2 unit 3",
        ),
        (
            "manual/burn-of-whilk-wind-farm",
            "Burn of Whilk Wind Farm",
            "E_BNWKW-1",
            "manual",
            "Burn of Whilk Wind Farm",
        ),
    ]
    added = 0
    for osm_id, plant_name, bmu_key, source, notes in additions:
        b = by_elexon.get(bmu_key)
        if not b:
            print(f"Warning: BMU {bmu_key} not in reference — skipping")
            continue
        fields = bmu_row_to_map_fields(b)
        before = len(frame)
        frame = append_map_row(
            frame,
            osm_id=osm_id,
            plant_name=plant_name,
            bmu_id=fields["bmu_id"],
            ngc_bmu_id=fields["ngc_bmu_id"],
            bmu_type=fields["bmu_type"],
            source=source,
            notes=notes,
        )
        if len(frame) > before:
            added += 1
    return frame, added


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Clean plant_bmu_links.csv")
    parser.add_argument(
        "--dedupe-only",
        action="store_true",
        help="Only drop bare osm_id duplicates and multi-site rows (post-propose pass)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = load_plant_bmu_map()
    start = len(frame)
    bmunits = load_bmunits(BMU_REFERENCE_PATH)
    by_elexon = {
        str(b.get("elexonBmUnit") or "").strip().upper(): b
        for b in bmunits
        if b.get("elexonBmUnit")
    }

    removed_explicit = 0
    added = 0
    if not args.dedupe_only:
        remove_mask = frame.apply(should_remove_row, axis=1)
        removed_explicit = int(remove_mask.sum())
        frame = frame.loc[~remove_mask].reset_index(drop=True)
        frame, added = add_fixes(frame, by_elexon)

    frame, removed_prefix = dedupe_osm_prefix(frame)
    frame, removed_multi = dedupe_multi_site(frame, by_elexon)

    save_plant_bmu_map(frame, PLANT_BMU_MAP_PATH)

    print(f"Started with {start:,} rows")
    if not args.dedupe_only:
        print(f"Removed {removed_explicit:,} explicit bad rows")
        print(f"Added {added:,} corrected manual links")
    print(f"Removed {removed_prefix:,} bare osm_id duplicates")
    print(f"Removed {removed_multi:,} multi-site duplicate rows")
    print(f"Final: {len(frame):,} rows -> {PLANT_BMU_MAP_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
