#!/usr/bin/env python3
"""Backward-compatible entry point for the legacy poster CLI."""

from poster.create_grid_poster import main

if __name__ == "__main__":
    raise SystemExit(main())
