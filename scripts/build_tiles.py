#!/usr/bin/env python3
"""Build PMTiles archives from map GeoJSON layers (requires tippecanoe + pmtiles CLI)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from region_catalog import catalog_data_path, get_region, list_region_ids

LINE_PROPS = "power,voltage,voltage_kv,name,operator,circuits,cables,frequency,location"
TURBINE_PROPS = "name,capacity_mw,height_m,rotor_diameter_m,operator,manufacturer,model,generator:output:electricity"
TOWER_PROPS = "power,ref,operator,name,height"
GENERATOR_PROPS = "power,name,operator,source_bucket,generator:source,generator:method,generator:type,generator:output:electricity,capacity_mw"

LAYER_PROPS = {
    "lines": LINE_PROPS,
    "turbines": TURBINE_PROPS,
    "towers": TOWER_PROPS,
    "generators": GENERATOR_PROPS,
}

# Per-layer tile tuning. Layers not listed use the defaults below
# (drop-densest enabled for overview performance). Generators must keep every
# feature, so dropping and the tile size/feature caps are disabled; tiles start
# one level below the catalog display gate (z7) so the renderer's level offset
# still has data to draw from.
LAYER_TILE_OPTIONS = {
    "generators": {"min_zoom": 6, "drop_densest": False, "no_limits": True},
    # Few features, so keep every individual turbine at all zoom levels too.
    "turbines": {"drop_densest": False, "no_limits": True},
}


def find_tool(name: str) -> str | None:
    path = shutil.which(name)
    return path


def geojson_to_pmtiles(
    source: Path,
    output: Path,
    *,
    layer_name: str,
    min_zoom: int,
    max_zoom: int,
    attribute_flags: str,
    drop_densest: bool = True,
    no_limits: bool = False,
) -> None:
    tippecanoe = find_tool("tippecanoe")
    if not tippecanoe:
        raise RuntimeError("tippecanoe not found on PATH - install from https://github.com/felt/tippecanoe")

    output.parent.mkdir(parents=True, exist_ok=True)
    mbtiles = output.with_suffix(".mbtiles")
    if mbtiles.exists():
        mbtiles.unlink()

    cmd = [
        tippecanoe,
        "-o",
        str(mbtiles),
        "-l",
        layer_name,
        f"--minimum-zoom={min_zoom}",
        f"--maximum-zoom={max_zoom}",
        "--force",
    ]
    if drop_densest:
        cmd.extend(["--drop-densest-as-needed", "--extend-zooms-if-still-dropping"])
    if no_limits:
        # Keep every feature at every zoom: disable the tile size / per-tile
        # caps, the default below-basezoom thinning (--drop-rate=1), and the
        # tiny-polygon reduction so nothing is dropped or merged away.
        cmd.extend([
            "--no-tile-size-limit",
            "--no-feature-limit",
            "--drop-rate=1",
            "--no-tiny-polygon-reduction",
        ])
    for prop in attribute_flags.split(","):
        prop = prop.strip()
        if prop:
            cmd.extend(["-y", prop])
    cmd.append(str(source))

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    pmtiles_cli = find_tool("pmtiles")
    if pmtiles_cli:
        if output.exists():
            output.unlink()
        subprocess.run([pmtiles_cli, "convert", str(mbtiles), str(output)], check=True)
        mbtiles.unlink()
        print(f"Wrote {output}")
        return

    pmtiles_py = find_tool("pmtiles-py")
    if pmtiles_py:
        subprocess.run([pmtiles_py, "convert", str(mbtiles), str(output)], check=True)
        mbtiles.unlink()
        print(f"Wrote {output}")
        return

    print(
        "tippecanoe wrote MBTiles but pmtiles CLI not found. "
        f"Install pmtiles (go install github.com/protomaps/go-pmtiles/cmd/pmtiles@latest) "
        f"and run: pmtiles convert {mbtiles} {output}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PMTiles from catalog GeoJSON layers")
    parser.add_argument("--region", "-r", required=True, choices=list_region_ids())
    parser.add_argument("--layer", choices=["lines", "turbines", "towers", "generators"], help="Single layer (default: all pmtiles in catalog)")
    parser.add_argument("--min-zoom", type=int, default=0)
    parser.add_argument("--max-zoom", type=int, default=14)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    region = get_region(args.region)
    layers = region.get("layers", {})

    targets = []
    for layer_id, layer in layers.items():
        if layer.get("type") != "pmtiles":
            continue
        if args.layer and layer_id != args.layer:
            continue
        targets.append((layer_id, layer))

    if not targets:
        print(f"No PMTiles layers configured for region {args.region!r}")
        return 0

    built = 0
    for layer_id, layer in targets:
        geojson_rel = layer.get("geojsonSource") or layer["path"].replace(".pmtiles", ".geojson")
        if not layer.get("geojsonSource") and layer["path"].endswith(".pmtiles"):
            stem = Path(layer["path"]).stem
            if stem in {"lines", "lines_transmission"}:
                geojson_rel = layer["path"].replace("lines.pmtiles", "lines_transmission.geojson")
            elif stem == "turbines":
                geojson_rel = layer["path"].replace("turbines.pmtiles", "turbines_web.geojson")

        source = catalog_data_path(geojson_rel)
        if not source.exists():
            print(f"Skipping {layer_id}: source GeoJSON not found at {source}")
            continue

        output = catalog_data_path(layer["path"])
        print(f"Building {layer_id}: {source} -> {output}")
        attrs = LAYER_PROPS.get(layer_id, TURBINE_PROPS)
        source_layer = layer.get("sourceLayer", layer_id)
        opts = LAYER_TILE_OPTIONS.get(layer_id, {})
        try:
            geojson_to_pmtiles(
                source,
                output,
                layer_name=source_layer,
                min_zoom=opts.get("min_zoom", args.min_zoom),
                max_zoom=opts.get("max_zoom", args.max_zoom),
                attribute_flags=attrs,
                drop_densest=opts.get("drop_densest", True),
                no_limits=opts.get("no_limits", False),
            )
        except subprocess.CalledProcessError as exc:
            print(f"Failed to build {layer_id}: {exc}", file=sys.stderr)
            return exc.returncode or 1
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1
        built += 1

    if built == 0:
        print(f"No PMTiles built for region {args.region!r}; check source GeoJSON files.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
