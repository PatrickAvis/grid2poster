# Agent Guidance

Guidance for coding agents working on this repository across sessions and machines.

## Project Shape

Interactive electricity infrastructure map. Frontend: static Leaflet under `map/`. Data prep: Python scripts under `scripts/`.

## Region Data Layout

All computed data for a region lives under `data/regions/{id}/` (portable single folder).

```
data/
  catalog.json
  shared/fuel_types.json
  regions/uk/
    boundary.geojson
    source/     # .osm.pbf extracts (gitignored)
    raw/        # full OSM exports (gitignored)
    map/        # web GeoJSON + *.pmtiles
    zones/
    reference/
      source/       # downloaded Elexon/NESO reference
      editable/     # human-edited CSVs
      generated/    # script outputs + map runtime JSON
      operational/  # BM activity etc. (future)
boundaries/         # shared export clip masks (not per-region computed data)
```

## Do Not Commit

- `data/regions/*/raw/`
- `data/regions/*/source/`
- `data/regions/*/map/*.pmtiles`
- `data/regions/*/map/all_generators_web.geojson`
- `data/regions/*/map/generators_web.geojson` (legacy name)
- `data/regions/*/map/turbines_web.geojson`
- `cache/`
- `posters/`

## Layer Naming

| Catalog id | UI label | Meaning |
|------------|----------|---------|
| `plants` | BMU-mapped sites | Grid-scale OSM `power=plant` sites; Elexon BMU popups attach here. |
| `generators` | All generators | Complete OSM `power=generator` inventory, from grid assets down to domestic rooftop solar. |
| `turbines` | Wind turbines | Wind-only generator-unit detail. |

BMUs are units, but this map joins them to site-level `plants` features through `reference/editable/plant_bmu_links.csv`.

## Region Folder Roles

`source/` is local `.osm.pbf`, `raw/` is full OSM export geometry, `map/` is browser-facing output, `zones/` is region-specific zone geometry, and `reference/` is lookup/editable/generated BMU/reference data. Do not move `raw/` under `reference/`.

## Common Commands

```powershell
python scripts/serve_map.py
python scripts/refresh_uk.py
python scripts/export_region.py --region uk --all --osm-pbf data/regions/uk/source/great-britain-latest.osm.pbf
python scripts/prepare_map_data.py --region uk
python scripts/build_tiles.py --region uk   # tippecanoe on WSL/Linux
python scripts/sync_uk_plants.py
python scripts/propose_plant_bmu_map.py
```

Tippecanoe/PMTiles: prefer WSL/Linux if not on PATH in Windows.

## BMU Reference Workflow

1. **Edit** `data/regions/uk/reference/editable/plant_bmu_links.csv`
2. **Run** `python scripts/propose_plant_bmu_map.py`
3. **Map loads** `data/regions/uk/reference/generated/plant_bmu_links.json` (via `data/catalog.json` → `plantBmuMap`)

BMUs appear on **BMU-mapped sites** layer popups only (not all-generators/turbines PMTiles layers).

Candidate matches: review `generated/plant_bmu_link_candidates.csv`, copy accepted rows to `editable/plant_bmu_links.csv`, regenerate JSON.

## Development Docs

See [DEVELOPMENT.md](DEVELOPMENT.md) for roadmap: regional balance, forecasts, constraints, ISPSTACK BM activity, SQLite reference store.

## Rules

- Preserve user edits in editable reference files and `bmu_sites_web.geojson`.
- Do not delete or regenerate multi-GB files unless explicitly requested.
- Catalog layer paths are relative to `data/`.
- `boundaries/` is for export masks; UK runtime boundary is `data/regions/uk/boundary.geojson`.
