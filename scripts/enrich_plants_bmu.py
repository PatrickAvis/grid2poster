#!/usr/bin/env python3
"""Backward-compatible alias for propose_plant_bmu_map.py."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import propose_plant_bmu_map  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(propose_plant_bmu_map.main())
