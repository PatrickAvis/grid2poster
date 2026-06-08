# Interactive power map

Leaflet map of transmission, generation, substations, wind turbines, and region-specific zone boundaries.

- **Map regions** (layer URLs, bounds, switcher): [`data/catalog.json`](../data/catalog.json)
- **Predefined boundaries** (multi-country export extents): [`regions/`](../regions/) + [`regions/manifest.json`](../regions/manifest.json)

UK and Europe catalog entries already point at `regions/uk_no_shetland.geojson` and `regions/europe.geojson`. Any manifest region can be exported without a catalog entry; add one when map layers are prepared.

## Quick start

```powershell
python -m http.server 8000
```

Open [http://localhost:8000/map/](http://localhost:8000/map/) or deep-link a region: [http://localhost:8000/map/?region=uk](http://localhost:8000/map/?region=uk).

Use the **region** dropdown to switch between countries (UK, France, …) or the continent view (Europe, when PMTiles are built).

## Data layout

```
data/
  catalog.json          # region registry, bounds, layer URLs and types
  raw/{region_id}/      # full OSM exports (gitignored)
  map/{region_id}/      # web GeoJSON and PMTiles
  zones/                # optional zone overlays (UK DNO/GSP/TNUoS generation zones today)
```

Paths in the catalog are relative to `data/` (e.g. `map/uk/uk_plants_web.geojson`).

## Export and prepare (per region)

```powershell
# UK (alias)
python scripts/export_uk.py --all
python scripts/fetch_neso_zones.py              # all registered NESO boundary datasets
python scripts/fetch_neso_zones.py --only generation
python scripts/prepare_map_data.py --region uk
# zones only (after fetch):
python scripts/prepare_map_data.py --region uk --skip-lines --skip-plants --skip-substations --skip-turbines

Offshore plants/turbines use a **250 km** sea buffer for UK (cables still use 600 km). Tile size auto-shrinks for buffered exports. If Overpass times out, abort and retry with `--tile-size-km 80 --tile-delay 45`, or raise `--offshore-sea-buffer-km 300` only if farms are still missing. Then `prepare_map_data.py` and `build_tiles.py --layer turbines`.
```

### UK plants and BMU (separate layers)

| File | Role |
|------|------|
| [`data/map/uk/uk_plants_web.geojson`](../data/map/uk/uk_plants_web.geojson) | **OSM ground truth** — geometry and plant tags. Edit directly; sync fills blanks only. |
| [`data/reference/uk_plant_bmu_map.csv`](../data/reference/uk_plant_bmu_map.csv) | **Your join table** — links `osm_id` → BMU ids. Edit this for BMU corrections. |
| [`data/reference/uk_bmunits.json`](../data/reference/uk_bmunits.json) | Elexon BMU registry (auto-fetched). |
| [`data/reference/uk_plant_bmu_map.json`](../data/reference/uk_plant_bmu_map.json) | Map runtime copy (generated from CSV). |

The map joins plants + BMU map at popup time (`osm_id` first, plant name fallback).

```powershell
# OSM plants (editable ground truth)
python scripts/sync_uk_plants.py

# BMU mapping: migrate embedded data, propose auto matches, export JSON
python scripts/propose_plant_bmu_map.py --fetch

# Plants still without a map row
python scripts/propose_plant_bmu_map.py --list-unmatched data/reference/uk_plants_missing_bmu.csv
```

Add manual BMU links in `uk_plant_bmu_map.csv` (one row per BMU unit; use `source=manual`). Re-run `propose_plant_bmu_map.py` to refresh the JSON. Existing rows are never overwritten.

`prepare_map_data.py --region uk` uses the same OSM merge for plants. To rebuild plants from OSM and discard edits: `python scripts/sync_uk_plants.py --force`.

```powershell
# Any catalog region
python scripts/export_region.py --region fr --all
python scripts/prepare_map_data.py --region fr

# Predefined boundary from regions/ (export-only until added to catalog)
python scripts/export_region.py --region iberia --all
python scripts/export_region.py --region continental_europe --all

# List catalog vs regions/ coverage
python scripts/list_regions.py
```

Per-layer refresh:

```powershell
python scripts/prepare_map_data.py --region uk --skip-lines --skip-substations --skip-turbines
```

### France pilot

```powershell
python scripts/export_region.py --region fr --single-query --skip-lines --skip-substations --skip-turbines
python scripts/prepare_map_data.py --region fr --skip-lines --skip-substations --skip-turbines
```

Full France export (lines/turbines) can take hours — use tiled export without `--single-query` for production.

## UK fast layers (PMTiles)

The UK map uses PMTiles for the heavy visual layers so the browser does not fetch
large raw GeoJSON files:

- `data/map/uk/lines.pmtiles` from `uk_powerlines_transmission.geojson`
- `data/map/uk/turbines.pmtiles` from `uk_wind_turbines_web.geojson`

Build the source web GeoJSON first, then build tiles:

```powershell
python scripts/prepare_map_data.py --region uk
python scripts/build_tiles.py --region uk
```

Requires [tippecanoe](https://github.com/felt/tippecanoe) and the
[pmtiles](https://github.com/protomaps/go-pmtiles) CLI on `PATH`.
On Windows, the simplest local route is usually WSL for Tippecanoe, with the
repo mounted from Windows or cloned inside the WSL filesystem.

`*.pmtiles` files are generated deploy artifacts and are ignored by git. They
should be copied to the static host alongside the smaller GeoJSON layers.
The browser-side PMTiles renderer is vendored at
`map/vendor/protomaps-leaflet.js` so the map does not depend on a runtime module
import from a CDN.

## Europe continent (PMTiles)

Continent-wide lines and turbines use PMTiles (phase 2). After preparing merged GeoJSON under `data/map/europe/`:

```powershell
python scripts/prepare_map_data.py --region europe
python scripts/build_tiles.py --region europe
```

Requires [tippecanoe](https://github.com/felt/tippecanoe) and the [pmtiles](https://github.com/protomaps/go-pmtiles) CLI on `PATH`.

## Layer size budget (UK, approximate)

| Layer | File | Size |
|-------|------|------|
| Transmission lines | `uk_powerlines_transmission.geojson` | ~50 MB |
| Plants | `uk_plants_web.geojson` | ~3 MB |
| Substations | `uk_substations_web.geojson` | ~24 MB |
| Wind turbines | `uk_wind_turbines_web.geojson` | ~250 MB |

## Map architecture

| Module | Role |
|--------|------|
| [`js/catalog.js`](js/catalog.js) | Load catalog, resolve `?region=`, build runtime config |
| [`js/layerDefs.js`](js/layerDefs.js) | Styling and popup behaviour per layer type |
| [`js/sources/geojson.js`](js/sources/geojson.js) | GeoJSON fetch loader |
| [`js/sources/pmtiles.js`](js/sources/pmtiles.js) | PMTiles vector layer loader |
| [`js/layers.js`](js/layers.js) | Dynamic layer manager per region |
| [`js/ui.js`](js/ui.js) | Region selector and layer panel |

## Features

- Region switcher with grouped continents
- Lazy-loaded layers with toggleable legends
- Plants/substations: polygon + marker
- Wind turbines: zoom gate (per catalog `minZoom`)
- UK: DNO/GSP zones with click-to-filter
- URL param and `localStorage` for last region

## Deployment

See [`DEPLOY.md`](DEPLOY.md) for nginx, compression, PMTiles serving, and data sync.
