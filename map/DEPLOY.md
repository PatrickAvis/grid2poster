# Deploying the power map

The map is a static site: `map/` (HTML/JS) plus `data/catalog.json` and `data/map/` (and optional `data/zones/`). No application server is required.

**Do not sync `posters/`** — that directory is for legacy print poster renders (PNG/SVG/PDF) only. The map does not read from it; exports live under `data/raw/` and web layers under `data/map/`.

## Recommended layout on server

```
/var/www/power-map/
  map/              # index.html, js/, config.json
  data/map/uk/      # small GeoJSON + generated *.pmtiles
  data/zones/       # optional raw NESO files
```

Serve from the repo root so `map/config.json` paths (`../data/map/uk/...`) resolve correctly:

```nginx
server {
    listen 80;
    server_name power-map.example.com;
    root /var/www/power-map;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~* \.geojson$ {
        gzip on;
        gzip_types application/geo+json application/json;
        add_header Cache-Control "public, max-age=86400";
    }
}
```

Enable **brotli** or **gzip** for `.geojson` — compressed payloads are often 5–10× smaller on the wire.

## What to sync (and what to skip)

| Path | Deploy? |
|------|---------|
| `map/` | Yes |
| `data/catalog.json` | Yes |
| `data/map/` | Yes |
| `data/reference/uk_plant_bmu_map.json` | Yes (UK plant ↔ BMU join for popups) |
| `data/zones/` | If used (e.g. UK NESO) |
| `posters/` | **No** — poster gallery / CLI renders |
| `data/raw/` | **No** — multi-GB OSM exports (prepare `data/map/` locally first) |
| `cache/` | **No** |

Sync app code via git; sync generated data with rsync or object storage:

```bash
rsync -avz map/ user@server:/var/www/power-map/map/
rsync -avz data/catalog.json user@server:/var/www/power-map/data/
rsync -avz data/map/ user@server:/var/www/power-map/data/map/
rsync -avz data/reference/uk_plant_bmu_map.json user@server:/var/www/power-map/data/reference/
rsync -avz data/zones/ user@server:/var/www/power-map/data/zones/
```

After refreshing OSM data locally:

```bash
python scripts/export_uk.py --all
python scripts/prepare_map_data.py --region uk
python scripts/build_tiles.py --region uk
```

## CORS

Serve `map/` and `data/` from the **same origin** so browser fetches do not need CORS headers.

## Multi-region data sync

Same rules: `data/catalog.json` + `data/map/` (+ zones if needed). Never rsync `posters/` or `data/raw/`.

After refreshing a region locally:

```bash
python scripts/export_region.py --region uk --all
python scripts/prepare_map_data.py --region uk
```

## PMTiles (UK and Europe)

Build tiles locally with tippecanoe + pmtiles CLI:

```bash
python scripts/build_tiles.py --region uk
python scripts/build_tiles.py --region europe
```

Serve `.pmtiles` with the same cache and compression rules as GeoJSON. The map loads them via `map/js/sources/pmtiles.js` when the catalog layer `type` is `pmtiles`.

Ensure `Content-Type: application/octet-stream` (or `application/vnd.pmtiles`) and support HTTP range requests — PMTiles depends on them.

## Turbines at scale

`uk_wind_turbines_web.geojson` (~250 MB) is only a tile-build source. The deployed map should serve `turbines.pmtiles` instead so users stream only the tiles they need. Alternatives:

- **FlatGeobuf** for range-request access
- **PostGIS + pg_tileserv / Martin** for server-side vector tiles

## Attribution

Display NESO and OpenStreetMap attribution in the map UI (included in `index.html`) and in your site README or about page.
