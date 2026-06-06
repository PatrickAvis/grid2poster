# Legacy poster rendering

Grid2Poster-style static posters live here. The interactive UK map in [`map/`](../map/) is the primary product; use this package when you want a print-ready PNG, SVG, or PDF.

## Quick start

```bash
python create_grid_poster.py --country "United Kingdom" --theme paper_grid
```

Or invoke the package directly:

```bash
python -m poster.create_grid_poster --country Brazil --theme neon_cyberpunk
```

## Layout

| Path | Role |
|------|------|
| `create_grid_poster.py` | Poster + optional export CLI |
| `render.py` | Matplotlib composition |
| `theming.py` | Theme loading and line/plant styling |
| `themes/` | Theme JSON files |

Themes are loaded from `poster/themes/`. Rendered images are written to `posters/` at the repo root (local only — not deployed with the interactive map; see [`map/DEPLOY.md`](../map/DEPLOY.md)).

## Export from poster CLI

The poster CLI still supports `--export-*-geojson` and `--export-*-csv` flags. For UK map ingest without rendering, prefer [`scripts/export_uk.py`](../scripts/export_uk.py).
