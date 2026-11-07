#!/usr/bin/env python3
"""Decode an opt-in HEROCAP panel snapshot from a recovered boot log."""

import argparse
import re
import struct
import zlib
from pathlib import Path


def decode(log):
    starts = list(re.finditer(r"^HEROCAP BEGIN (\d+) (\d+)$", log, re.M))
    if not starts:
        raise ValueError("no screen capture in the log")
    start = starts[-1]
    width, height = map(int, start.groups())
    if not (1 <= width <= 480 and 1 <= height <= 854):
        raise ValueError("invalid capture dimensions")
    rows = []
    for line in log[start.end():].splitlines():
        if line.endswith("HEROCAP END"):
            if len(rows) == height:
                return width, height, b"".join(rows)
            break
        _, marker, payload = line.partition("HEROCAP ROW ")
        if not marker:
            continue
        index, pixels = payload.split(maxsplit=1)
        if int(index) != len(rows) or len(rows) >= height or len(pixels) != width * 4:
            raise ValueError("unexpected capture row")
        row = bytearray()
        for pos in range(0, len(pixels), 4):
            pixel = int(pixels[pos:pos + 4], 16)
            row.extend(((pixel >> 11) * 255 // 31,
                        ((pixel >> 5) & 63) * 255 // 63,
                        (pixel & 31) * 255 // 31))
        rows.append(bytes(row))
    raise ValueError("incomplete screen capture")


def png(width, height, pixels):
    def chunk(kind, payload):
        data = kind + payload
        return struct.pack(">I", len(payload)) + data + struct.pack(">I", zlib.crc32(data))

    stride = width * 3
    scanlines = b"".join(b"\0" + pixels[y:y + stride] for y in range(0, len(pixels), stride))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines))
            + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        width, height, pixels = decode(args.log.read_text(encoding="utf-8", errors="replace"))
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    args.output.write_bytes(png(width, height, pixels))
    print(f"{width}x{height} -> {args.output}")


if __name__ == "__main__":
    main()
