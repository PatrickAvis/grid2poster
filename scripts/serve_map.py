#!/usr/bin/env python3
"""Serve the static map locally with HTTP Range support for PMTiles."""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import os
from pathlib import Path
import re
import socketserver

REPO_ROOT = Path(__file__).resolve().parents[1]
RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class RangeRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Simple static handler that supports single byte ranges."""

    range: tuple[int, int] | None = None

    def send_head(self):
        self.range = None
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if not os.path.exists(path):
            self.send_error(404, "File not found")
            return None

        file_size = os.path.getsize(path)
        start, end = 0, file_size - 1
        range_header = self.headers.get("Range")
        if range_header:
            match = RANGE_RE.match(range_header.strip())
            if not match:
                self.send_error(416, "Invalid Range header")
                return None
            raw_start, raw_end = match.groups()
            if raw_start:
                start = int(raw_start)
                end = int(raw_end) if raw_end else file_size - 1
            elif raw_end:
                suffix = int(raw_end)
                start = max(file_size - suffix, 0)
            if start >= file_size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return None
            end = min(end, file_size - 1)
            self.range = (start, end)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            content_length = end - start + 1
        else:
            self.send_response(200)
            content_length = file_size

        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        file_obj = open(path, "rb")
        if self.range:
            file_obj.seek(start)
        return file_obj

    def copyfile(self, source, outputfile):
        if not self.range:
            return super().copyfile(source, outputfile)

        remaining = self.range[1] - self.range[0] + 1
        while remaining > 0:
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the map locally with PMTiles range support")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    handler = functools.partial(RangeRequestHandler, directory=str(REPO_ROOT))
    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as httpd:
        with contextlib.suppress(AttributeError):
            httpd.allow_reuse_address = True
        print(f"Serving {REPO_ROOT} at http://localhost:{args.port}/map/")
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
