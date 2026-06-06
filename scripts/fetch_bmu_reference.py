#!/usr/bin/env python3
"""Download UK BMU standing data from the Elexon Insights API."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bmu_data import BMU_REFERENCE_PATH, fetch_bmunits, save_bmunits


def main() -> int:
    records = fetch_bmunits()
    path = save_bmunits(records)
    print(f"Saved {len(records):,} BMUs to {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
