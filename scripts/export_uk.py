#!/usr/bin/env python3
"""Export UK power infrastructure — alias for export_region.py --region uk."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "export_region.py"


def main() -> int:
    argv = [sys.executable, str(SCRIPT), "--region", "uk", *sys.argv[1:]]
    result = subprocess.run(argv, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
