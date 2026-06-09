# Deploying the power map

The map is a static site: `map/` (HTML/JS) plus `data/catalog.json`, `data/shared/`, and the per-region `data/regions/{id}/map/` (and optional `zones/`). No application server is required.

## Recommended layout on server

```
/var/www/power-map/
  map/                          # index.html, js/
  data/catalog.json
  data/shared/                  # fuel_types.json
  data/regions/uk/map/          # small GeoJSON + generated *.pmtiles
  data/regions/uk/zones/        # optional zone overlays
  data/regions/uk/reference/generated/  # plant_bmu_links.json (UK popups)
```

Serve from the repo root so catalog paths (`../data/regions/uk/map/...`) resolve correctly:

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
| `data/shared/` | Yes (fuel taxonomy) |
| `data/regions/{id}/map/` | Yes |
| `data/regions/uk/reference/generated/plant_bmu_links.json` | Yes (UK plant ↔ BMU join for popups) |
| `data/regions/{id}/zones/` | If used (e.g. UK NESO) |
| `data/regions/{id}/raw/` | **No** — multi-GB OSM exports (prepare `map/` locally first) |
| `data/regions/{id}/source/` | **No** — local `.osm.pbf` extracts |
| `cache/` | **No** |

Sync app code via git; sync generated data with rsync or object storage. Because
each region is self-contained, you can rsync one region folder at a time:

```bash
rsync -avz map/ user@server:/var/www/power-map/map/
rsync -avz data/catalog.json user@server:/var/www/power-map/data/
rsync -avz data/shared/ user@server:/var/www/power-map/data/shared/
rsync -avz --exclude raw/ --exclude source/ \
  data/regions/uk/ user@server:/var/www/power-map/data/regions/uk/
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

Same rules: `data/catalog.json` + `data/shared/` + each `data/regions/{id}/` (excluding `raw/` and `source/`). Never rsync the multi-GB `raw/` or `source/` folders.

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

`turbines_web.geojson` (~250 MB) is only a tile-build source. The deployed map should serve `turbines.pmtiles` instead so users stream only the tiles they need. Alternatives:

- **FlatGeobuf** for range-request access
- **PostGIS + pg_tileserv / Martin** for server-side vector tiles

## Attribution

Display NESO and OpenStreetMap attribution in the map UI (included in `index.html`) and in your site README or about page.
