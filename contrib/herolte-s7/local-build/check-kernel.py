#!/usr/bin/env python3
"""Compare a local HEROLTE Mach-O with CI and scan the instructions for LSE."""

from pathlib import Path
import re
import struct
import subprocess
import sys


def macho(path):
    with path.open("rb") as stream:
        magic, cpu, subtype, filetype, count, size, flags, _ = struct.unpack("<8I", stream.read(32))
        assert (magic, cpu, subtype & 0xff, filetype) == (0xfeedfacf, 0x0100000c, 0, 2), path
        assert flags & 1, f"{path} lacks MH_NOUNDEFS"
        commands = stream.read(size)
    segments = {}
    entry = None
    fixups = False
    offset = 0
    for _ in range(count):
        kind, length = struct.unpack_from("<II", commands, offset)
        if kind == 0x19:
            name, address, virtual, file_offset, size, _, prot = struct.unpack_from(
                "<16sQQQQII", commands, offset + 8
            )
            name = name.rstrip(b"\0").decode()
            assert (not virtual or size <= virtual) and file_offset + size <= path.stat().st_size, name
            segments[name] = (address, virtual, size, prot)
        elif kind == 5:
            entry, = struct.unpack_from("<Q", commands, offset + 16 + 32 * 8)
        elif kind == 0x80000034:
            fixups = True
        offset += length
    assert next(iter(segments)) == "__TEXT"
    assert segments["__TEXT"][0] == 0xfffffff007004000
    assert entry and any(
        address <= entry < address + virtual and prot & 4
        for address, virtual, _, prot in segments.values()
    )
    ranges = sorted(
        (address, address + virtual, name)
        for name, (address, virtual, _, _) in segments.items() if virtual
    )
    assert all(left[1] <= right[0] for left, right in zip(ranges, ranges[1:])), ranges
    return segments, entry, fixups


def lse_scan(objdump, kernel):
    lse = re.compile(r"\b(?:cas|casp|ldadd|ldclr|ldeor|ldset|ldsmax|ldsmin|ldumax|ldumin|"
                     r"stadd|stclr|steor|stset|stsmax|stsmin|stumax|stumin|swp)[a-z]*\s")
    function = ""
    hits = []
    instructions = 0
    command = [objdump, "-d", "--no-show-raw-insn", "--mattr=+lse", kernel]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as proc:
        for line in proc.stdout:
            match = re.match(r"^[0-9a-f]+ <(.+)>:", line)
            if match:
                function = match[1]
            elif re.match(r"^[0-9a-f]+:\s", line):
                instructions += 1
                if lse.search(line) and function.lstrip("_") != "K256":
                    hits.append((function, line.strip()))
        if proc.wait():
            raise SystemExit("llvm-objdump failed")
    assert instructions > 10000, f"only {instructions} instruction lines"
    print(f"LSE hits outside K256 data: {len(hits)} ({instructions} instruction lines)")
    for function, instruction in hits[:20]:
        print(f"  {function} {instruction}")
    return bool(hits)


work = Path(sys.argv[1]).resolve()
local = work / "build/xnu.obj/DEVELOPMENT_ARM64_HEROLTE/kernel.development.herolte.unstripped"
reference = Path(sys.argv[2]).resolve()
local_segments, entry, fixups = macho(local)
ref_segments, ref_entry, ref_fixups = macho(reference)
local_loaded = {name: seg[3] for name, seg in local_segments.items() if seg[1]}
ref_loaded = {name: seg[3] for name, seg in ref_segments.items() if seg[1]}
assert local_loaded == ref_loaded, "local/CI loadable segments or protections differ"
print(f"Local entry {entry:#018x}, chained fixups {fixups}")
print(f"CI entry    {ref_entry:#018x}, chained fixups {ref_fixups}")
print(f"{'Segment':20} {'Local VM':18} {'CI VM':18} {'Local size':12} {'CI size':12} protections")
for name in dict.fromkeys([*ref_segments, *local_segments]):
    lv, ls, _, lp = local_segments.get(name, (0, 0, 0, 0))
    rv, rs, _, rp = ref_segments.get(name, (0, 0, 0, 0))
    print(f"{name:20} {lv:#018x} {rv:#018x} {ls:#012x} {rs:#012x} {lp}/{rp}")
objdump = work / "toolcache/usr/lib/llvm-21/bin/llvm-objdump"
sys.exit(lse_scan(objdump, local))
