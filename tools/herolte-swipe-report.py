#!/usr/bin/env python3
"""Compare framebuffer presentation during repeatable HEROLTE Home swipes."""

import argparse
import re
import statistics
from pathlib import Path


WINDOW = re.compile(r"HEROSWIPE BEGIN (\d+)\b(.*?)HEROSWIPE END", re.S)
SAMPLE = re.compile(
    r"A5XELTE FB: frames=(\d+) elapsed_ms=(\d+) fps=\d+\.\d+ "
    r"bytes=\d+ avg_copy_us=(\d+) max_copy_us=(\d+) missed=\d+ "
    r"gaps=(\d+)/(\d+)/(\d+)/(\d+) swaps=(\d+) overwritten=(\d+)"
)


def summarize(log):
    windows = list(WINDOW.finditer(log))
    if len(windows) != 1:
        raise ValueError("expected one complete gesture window")
    gestures, body = windows[0].groups()
    samples = [tuple(map(int, match)) for match in SAMPLE.findall(body)]
    # The first report includes frames from before the start marker.
    samples = samples[1:]
    if len(samples) < 2 or any(sample[1] <= 0 for sample in samples):
        raise ValueError("expected at least two complete framebuffer intervals")
    frames, elapsed = (sum(sample[index] for sample in samples) for index in (0, 1))
    measured_gaps = sum(sum(sample[4:8]) for sample in samples)
    one_tick = sum(sample[4] for sample in samples)
    return {
        "gestures": int(gestures),
        "intervals": len(samples),
        "display_fps": frames * 1000 / elapsed,
        "slowest_fps": min(sample[0] * 1000 / sample[1] for sample in samples),
        "median_copy_ms": statistics.median(sample[2] for sample in samples) / 1000,
        "worst_copy_ms": max(sample[3] for sample in samples) / 1000,
        "one_tick_percent": 100 * one_tick / measured_gaps if measured_gaps else 0,
        "submitted": sum(sample[8] for sample in samples),
        "overwritten": sum(sample[9] for sample in samples),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.logs:
        try:
            data = summarize(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ValueError) as error:
            parser.exit(1, f"{path}: {error}\n")
        print(f"{path}: {data['gestures']} swipes, {data['intervals']} complete intervals, "
              f"{data['display_fps']:.1f} fps ({data['slowest_fps']:.1f} slowest interval), "
              f"{data['one_tick_percent']:.1f}% one-tick gaps, "
              f"{data['overwritten']}/{data['submitted']} frames overwritten, "
              f"copy {data['median_copy_ms']:.2f} ms median / {data['worst_copy_ms']:.2f} ms worst")


if __name__ == "__main__":
    main()
