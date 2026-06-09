<h1 align="center">UK Power Map</h1>

<p align="center">
  Interactive Leaflet map of Great Britain transmission, generation, substations, wind turbines, and NESO zone boundaries — built on OpenStreetMap exports from this repo.
</p>

## UK interactive map

One command refreshes everything — OSM export (from a local `.osm.pbf` if present), Elexon BMU data, NESO zones, web layers, plant↔BMU matching, and PMTiles:

```bash
python scripts/refresh_uk.py
python scripts/serve_map.py
```

`refresh_uk.py` auto-detects an extract under `data/osm/` (or pass `--osm-pbf PATH`); without one it reuses the existing `data/raw/` exports. Any step can be skipped (`--skip-osm`, `--skip-elexon`, `--skip-zones`, `--skip-bmu-match`, `--skip-tiles`). The PMTiles step needs Tippecanoe on `PATH` (use WSL/Linux). To run the stages individually instead:

```powershell
python scripts/export_region.py --region uk --all
python scripts/fetch_neso_zones.py
python scripts/sync_uk_plants.py
python scripts/propose_plant_bmu_map.py --fetch
python scripts/prepare_map_data.py --region uk --skip-plants
python scripts/serve_map.py
```

Open [http://localhost:8000/map/](http://localhost:8000/map/) (or `?region=fr` after exporting another country). Use `serve_map.py` instead of plain `http.server` when testing PMTiles — it supports HTTP range requests. Regions and layers are defined in [`data/catalog.json`](data/catalog.json). See [`map/README.md`](map/README.md) and [`map/DEPLOY.md`](map/DEPLOY.md).

UK plant popups show BMU ids from a separate mapping table ([procedure below](#uk-plant-bmu-mapping)); OSM plant geometry lives in `data/map/uk/uk_plants_web.geojson`.

## Installation

```bash
git clone https://github.com/PatrickAvis/grid2poster
cd grid2poster
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Exporting data

OSM power infrastructure is downloaded with `scripts/export_region.py` and written to `data/raw/{region}/` as WGS84 GeoJSON and CSV. The interactive map loads smaller prepared files from `data/map/{region}/`.

```powershell
# Full UK export (lines, plants, substations, turbines)
python scripts/export_region.py --region uk --all

# France with custom Overpass mirror
python scripts/export_region.py --region fr --all --overpass-endpoint https://overpass.kumi.systems/api/interpreter

# Custom boundary from regions/
python scripts/export_region.py --region europe --all --boundary-geojson ./regions/europe.geojson --tile-size-km 800
```

### Local .osm.pbf fast path (recommended for the UK)

Overpass tiling is slow and prone to read timeouts for large exports. If you have a local country extract (e.g. `great-britain-latest.osm.pbf` from [Geofabrik](https://download.geofabrik.de/)), pass `--osm-pbf` to read every layer directly from it instead of Overpass:

```powershell
python scripts/export_region.py --region uk --all --osm-pbf data/osm/great-britain-latest.osm.pbf
```

This is dramatically faster and immune to Overpass rate limits/timeouts. It uses GDAL's built-in OSM driver (via `pyogrio`, already a dependency) — no extra install. Place extracts under `data/osm/` (gitignored). The output schema is identical to the Overpass path, so `prepare_map_data.py` and the rest of the pipeline are unchanged.

After exporting, prepare web layers and serve the map:

```powershell
python scripts/prepare_map_data.py --region uk
python scripts/build_tiles.py --region uk   # optional PMTiles for lines/turbines
python scripts/serve_map.py
```

### Export options

| Option | Default | Description |
| --- | --- | --- |
| `--region` | — | Region id from `data/catalog.json` or `regions/*.geojson` |
| `--country` | catalog default | Override Nominatim country name |
| `--boundary-geojson` | catalog default | Path to boundary GeoJSON |
| `--all` | off | Export lines, plants, substations, and turbines |
| `--include-minor-lines` | off | Include `power=minor_line` |
| `--include-cables` / `--no-include-cables` | on | Include `power=cable` (submarine/interconnectors) |
| `--cable-sea-buffer-km` | region preset (UK 600) | Sea buffer for submarine cable queries |
| `--offshore-sea-buffer-km` | region preset (UK 250) | Sea buffer for offshore plants and turbines |
| `--tile-size-km` | `400` | Overpass query tile size in kilometres |
| `--tile-delay` | `30` | Seconds between Overpass tile requests |
| `--single-query` | off | Single Overpass query instead of tiling |
| `--overpass-endpoint` | OSMnx default | Overpass API mirror URL |
| `--no-cache` | off | Ignore cached boundaries and OSM features |
| `--skip-lines` / `--skip-plants` / `--skip-substations` / `--skip-turbines` | off | Skip individual layers |

## Data

This project combines region boundaries with OpenStreetMap (OSM) power infrastructure. Coverage and tag quality vary by country; see [Data sources](#data-sources) for where each layer comes from and how exports are produced.

### Contributing to the data

Coverage and quality in your country can be improved by mapping transmission infrastructure directly in OpenStreetMap. [MapYourGrid](https://mapyourgrid.org) coordinates this work. [Open Infrastructure Map](https://openinframap.org/) lets you browse electrical grid data in OSM.

### Predefined regions

The `regions/` directory ships with multi-country boundaries for common power-system groupings. Pass any of them via `--boundary-geojson` when exporting:

```powershell
python scripts/export_region.py --region europe --all --boundary-geojson ./regions/europe.geojson --tile-size-km 300
```

See [`regions/manifest.json`](regions/manifest.json) for the full list and descriptions.

## Data sources

### Region boundaries

These define the area queried from Overpass. All boundary outputs use WGS84 (`EPSG:4326`).

| Source | Used when | What you get | Notes |
| --- | --- | --- | --- |
| [Nominatim](https://nominatim.org/) | Default country lookup | Administrative polygons for countries, states, and provinces | Downloaded via OSMnx and cached in `cache/`. |
| [Natural Earth](https://www.naturalearthdata.com/) admin-0 | Continent names or `Global` | Continent-scale polygons | Cached on first use. |
| Local GeoJSON in `regions/` | `--boundary-geojson ./regions/....geojson` | Custom or multi-country masks | All polygon features are dissolved into one boundary. |
| User-supplied GeoJSON | `--boundary-geojson path/to/file.geojson` | Any custom clipping polygon | Same dissolve behaviour as bundled `regions/` files. |

### Grid infrastructure (OpenStreetMap)

Downloaded from the [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) through OSMnx, tiled for large areas, and cached per tile in `cache/`. GeoJSON and CSV exports preserve **all OSM tag columns** returned for each feature.

| OSM tag query | CLI / behaviour | Geometry | Typical use |
| --- | --- | --- | --- |
| `power=line` | Always fetched (unless `--skip-lines`) | LineString / MultiLineString | Transmission corridors |
| `power=minor_line` | `--include-minor-lines` | Lines | Distribution and lower-voltage lines |
| `power=cable` | `--include-cables` (+ optional `--cable-sea-buffer-km`) | Lines | Underground and submarine cables |
| `power=plant` | Exported unless `--skip-plants` | Point, Polygon, MultiPolygon | Power stations and wind/solar farms |
| `power=substation` | Exported unless `--skip-substations` | Point, Polygon, MultiPolygon | Transmission and distribution substations |
| `power=generator` + wind tags | Exported unless `--skip-turbines` | Point (mostly) | Individual wind turbines |

**Great Britain tagging context:** see the [OSM Power networks/Great Britain](https://wiki.openstreetmap.org/wiki/Power_networks/Great_Britain) wiki page.

**Licence:** OpenStreetMap data is © OpenStreetMap contributors, available under the [ODbL](https://www.openstreetmap.org/copyright).

### UK full exports (`data/raw/uk/`)

Use `python scripts/export_uk.py --all` (alias for `export_region.py --region uk --all`) to write full exports (gitignored under `data/raw/uk/`).

| File | Source | Contents |
| --- | --- | --- |
| `powerlines.geojson` / `.csv` | OSM lines, minor lines, cables | Full UK grid export with all OSM tags |
| `plants.geojson` / `.csv` | OSM `power=plant` | Generation sites with footprints and capacity tags |
| `substations.geojson` / `.csv` | OSM `power=substation` | Substation footprints and attributes |
| `wind_turbines.geojson` / `.csv` | OSM `power=generator` (wind) | Individual turbine points; parsed `capacity_mw`, `height_m`, `rotor_diameter_m` when tags exist |

### Map web layers (`scripts/prepare_map_data.py`)

The [interactive map](map/) does not load multi-gigabyte full exports directly. Regions are listed in [`data/catalog.json`](data/catalog.json). Run `python scripts/prepare_map_data.py --region {id}` after `python scripts/export_region.py --region {id}` to build smaller files under `data/map/{id}/`:

| File | Derived from | What changes |
| --- | --- | --- |
| `uk_powerlines_transmission.geojson` | `powerlines.geojson` | Drops `power=minor_line`; keeps transmission and cables; source for `lines.pmtiles` |
| `uk_plants_web.geojson` | `plants.geojson` | OSM ground truth: geometry and plant tags. BMU fields are joined at popup time — see [UK plant BMU mapping](#uk-plant-bmu-mapping). |
| `uk_substations_web.geojson` | `substations.geojson` | Trims columns; adds `latitude`, `longitude` |
| `uk_wind_turbines_web.geojson` | `wind_turbines.csv` | Point-only tile-build source (~250 MB; ignored by git) |
| `lines.pmtiles` / `turbines.pmtiles` | prepared UK GeoJSON | Fast browser layers from `scripts/build_tiles.py` |
| `uk_dno_areas_web.geojson` | NESO DNO boundaries | WGS84 polygons; click to filter plants/turbines |
| `uk_gsp_areas_web.geojson` | NESO GSP boundaries | WGS84 polygons; click to filter plants/turbines |
| `uk_generation_charging_zones_web.geojson` | NESO TNUoS generation charging zones | WGS84 polygons; click to filter plants/turbines |
| `uk_etys_boundaries_web.geojson` | NESO ETYS transmission boundaries | WGS84 lines (B6, B9, B2, …) |

**Basemap:** the map uses standard [OpenStreetMap raster tiles](https://www.openstreetmap.org/copyright) via Leaflet, with an adjustable **Map backdrop** intensity in the UI.

Build fast UK map tiles after preparing web layers:

```powershell
python scripts/prepare_map_data.py --region uk
python scripts/build_tiles.py --region uk
```

`build_tiles.py` requires Tippecanoe and the PMTiles CLI on `PATH`. On Windows, use WSL for Tippecanoe if it is not available natively.

### Fuel type taxonomy

Plant generation types are defined in [`data/reference/fuel_types.json`](data/reference/fuel_types.json). Each entry controls the map legend order, label, marker colour, and keyword-based classification of OSM `plant:source` tags. Python prep uses the same taxonomy via `fuel_taxonomy.py`, and the browser loads it at startup.

After editing fuel types, refresh the plant web layer:

```powershell
python scripts/prepare_map_data.py --region uk --skip-lines --skip-substations --skip-turbines --skip-zones
```

### UK plant BMU mapping

UK balancing-mechanism unit (BMU) ids are kept **separate** from OSM plant geometry. The map joins them at popup time.

| File | Role |
| --- | --- |
| `data/map/uk/uk_plants_web.geojson` | **OSM ground truth** — edit plant names, geometry, capacity, etc. |
| `data/reference/uk_plant_bmu_map.csv` | **Your join table** — one row per plant↔BMU link (`osm_id` primary key) |
| `data/reference/uk_bmunits.json` | Elexon BMU registry (~3k units; auto-fetched) |
| `data/reference/uk_plant_bmu_map.json` | Generated from the CSV; loaded by the map |

**Mapping table columns:** `osm_id`, `plant_name`, `bmu_id` (Elexon, e.g. `E_ABERDARE`), `ngc_bmu_id` (e.g. `ABERU-1`), `bmu_type` (e.g. `E`), `source` (`auto` / `manual` / `migrated`), `notes`.

Multi-unit stations need **one row per BMU**. Existing CSV rows are never overwritten — scripts only append new **high-confidence** auto matches.

#### Routine update

After refreshing OSM exports or editing plant data:

```powershell
python scripts/sync_uk_plants.py
python scripts/propose_plant_bmu_map.py --fetch
```

`prepare_map_data.py --region uk` runs the same OSM plant merge as `sync_uk_plants.py`. You can skip plants when you have already synced:

```powershell
python scripts/prepare_map_data.py --region uk --skip-plants
```

#### Manual BMU corrections

1. Open `data/reference/uk_plant_bmu_map.csv`.
2. Add or edit rows (set `source` to `manual`).
3. Regenerate: `python scripts/propose_plant_bmu_map.py`

#### Deploy

Sync `data/reference/uk_plant_bmu_map.json` with the map (see [`map/DEPLOY.md`](map/DEPLOY.md)).

**Licence:** BMU standing data is published by [Elexon](https://www.elexon.co.uk/) via the [Insights API](https://data.elexon.co.uk/bmrs/api/v1/reference/bmunits/all).

### NESO zone boundaries (`scripts/fetch_neso_zones.py`)

DNO, GSP, TNUoS generation charging zone, and ETYS boundary data are fetched from NESO into `data/zones/`:

```powershell
python scripts/fetch_neso_zones.py
python scripts/fetch_neso_zones.py --only generation
python scripts/prepare_map_data.py --region uk --skip-lines --skip-plants --skip-substations --skip-turbines
```

| Source | Output | Map layer |
| --- | --- | --- |
| [NESO — GB DNO licence areas](https://www.neso.energy/data-portal/gis-boundaries-gb-dno-license-areas) | `data/zones/uk_dno_areas.geojson` | DNO licence areas |
| [NESO — GB GSP boundaries](https://www.neso.energy/data-portal/gis-boundaries-gb-grid-supply-points) | `data/zones/uk_gsp_areas.geojson` | GSP regions |
| [NESO — GB generation charging zones](https://www.neso.energy/data-portal/gis-boundaries-gb-generation-charging-zones) | `data/zones/uk_generation_charging_zones.geojson` | TNUoS generation zones |
| [NESO — ETYS GB transmission system boundaries](https://www.neso.energy/data-portal/etys-gb-transmission-system-boundaries) | `data/zones/uk_etys_boundaries.geojson` | ETYS transmission boundaries |

### Derived and parsed fields

| Field | Added where | Source logic |
| --- | --- | --- |
| `latitude`, `longitude` | CSV exports; web plant/substation/turbine files | Representative point of each geometry |
| `geometry_wkt` | CSV exports | Full WGS84 geometry as WKT |
| `capacity_mw` | Plant web export; turbine export | Parsed from `plant:output:electricity` or `generator:output:electricity` |
| `source_bucket` | Plant web export; map legend | Buckets `plant:source` into solar, wind, hydro, nuclear, coal, gas, oil, biomass, other |
| `height_m`, `rotor_diameter_m` | Turbine export | Parsed from OSM `height` and `rotor:diameter` tags when present |
| `voltage_kv` | Line preparation | Parsed from raw `voltage` tag |

## Attribution

- Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors (ODbL).
- Country boundaries via [Nominatim](https://nominatim.org/) / OSM; continent boundaries via [Natural Earth](https://www.naturalearthdata.com/).
- DNO/GSP/TNUoS/ETYS boundaries from [NESO](https://www.neso.energy/data-portal).
