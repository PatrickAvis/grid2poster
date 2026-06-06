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

LINE_PROPS = "power,voltage,voltage_kv,name,operator,circuits,cables"
TURBINE_PROPS = "name,capacity_mw,operator,manufacturer,model,generator:output:electricity"


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
) -> None:
    tippecanoe = find_tool("tippecanoe")
    if not tippecanoe:
        raise RuntimeError("tippecanoe not found on PATH — install from https://github.com/felt/tippecanoe")

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
        "--drop-densest-as-needed",
        "--extend-zooms-if-still-dropping",
        "--force",
    ]
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
    parser.add_argument("--layer", choices=["lines", "turbines"], help="Single layer (default: all pmtiles in catalog)")
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

    for layer_id, layer in targets:
        geojson_rel = layer.get("geojsonSource") or layer["path"].replace(".pmtiles", ".geojson")
        if layer["path"].endswith(".pmtiles"):
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
        attrs = LINE_PROPS if layer_id == "lines" else TURBINE_PROPS
        source_layer = layer.get("sourceLayer", layer_id)
        try:
            geojson_to_pmtiles(
                source,
                output,
                layer_name=source_layer,
                min_zoom=args.min_zoom,
                max_zoom=args.max_zoom,
                attribute_flags=attrs,
            )
        except subprocess.CalledProcessError as exc:
            print(f"Failed to build {layer_id}: {exc}", file=sys.stderr)
            return exc.returncode or 1
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
