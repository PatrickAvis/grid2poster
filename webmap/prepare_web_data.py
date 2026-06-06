#!/usr/bin/env python3
"""Deprecated: use scripts/prepare_map_data.py instead."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "prepare_map_data.py"


def main() -> int:
    print("webmap/prepare_web_data.py is deprecated. Running scripts/prepare_map_data.py…")
    result = subprocess.run([sys.executable, str(SCRIPT), *sys.argv[1:]], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
