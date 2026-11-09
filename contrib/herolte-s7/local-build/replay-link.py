#!/usr/bin/env python3
"""Build the support library and link the compiled HEROLTE archive inputs."""

from pathlib import Path
import os
import shlex
import struct
import subprocess
import sys


tree = Path(sys.argv[1]).resolve()
build = tree / "build/xnu.obj"
config = build / "DEVELOPMENT_ARM64_HEROLTE"
clang = tree / "compat/host/bin/xnu-clang"
tools = tree / "toolcache/linux/iphone/bin"
src = tree / "xnu"
headers = build / "EXPORT_HDRS"
firehose = tree / "libdispatch-libdispatch-1415.140.2"
archive = tree / "fakeroot/usr/local/lib/kernel/libfirehose_kernel.a"
hakios = Path(__file__).resolve().parents[2] / "s9plus-reference/core"
archive.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, XNU_SDK_VERSION="15.0")


def run(*args):
    subprocess.run(args, cwd=config, env=env, check=True)


run(
    clang, "-arch", "arm64", "-c", "-Os", "-mkernel", "-nostdinc", "-fno-builtin",
    "-mcpu=cortex-a53", "-march=armv8-a+crypto",
    "-DKERNEL=1", "-DKERNEL_PRIVATE=1", "-DXNU_KERNEL_PRIVATE=0", "-DPRIVATE=1",
    "-D__DARWIN_64_BIT_INO_T=1", "-DDISPATCH_USE_DTRACE=0",
    "-DOS_ATOMIC_CONFIG_MEMORY_ORDER_DEPENDENCY=1",
    "-DOS_ATOMIC_CONFIG_STARVATION_FREE_ONLY=0", "-DOS_FIREHOSE_SPI=1",
    "-DARM64_BOARD_CONFIG_A5XELTE", "-DARM64_BOARD_CONFIG_HEROLTE",
    *(f"-I{path}" for path in (
        firehose, firehose / "src", firehose / "src/firehose",
        *(headers / part for part in ("osfmk", "bsd", "libkern", "pexpert", "iokit", "security")),
        src / "libkern/firehose", headers / "libkern/os", src / "EXTERNAL_HEADERS",
        tree / "fakeroot/usr/local/include/kernel",
    )),
    "-o", "firehose_buffer.o", firehose / "src/firehose/firehose_buffer.c",
)
run(tools / "libtool", "-static", "-o", archive, "firehose_buffer.o")

listing_text = (config / "link.filelist").read_text()
ci_root = listing_text.splitlines()[0].split("/build/xnu.obj/", 1)[0]
flags = shlex.split((config / ".CFLAGS").read_text().rstrip("\0").replace(ci_root, str(tree)))[1:]
for name in ("version", "lastkerneldataconst", "lastkernelconstructor", "nonlto"):
    source = config / "version.c" if name == "version" else src / f"libsa/{name}.c"
    run(clang, *flags, "-c", source, "-o", name + ".o")

runtime = (hakios / "xnu/files/osfmk/arm64/generic_arm64_support.c").read_text()
runtime = runtime[runtime.index("/*\n * Stock LLVM"):]
(config / "linux-kernel-runtime.c").write_text("#include <sys/types.h>\n" + runtime)
run(clang, *flags, "-c", "linux-kernel-runtime.c", "-o", "linux-kernel-runtime.o")

def rewrite_sections(obj, rename):
    """Apply XNU's setsegname rules to non-debug sections of an MH_OBJECT."""
    data = bytearray(obj.read_bytes())
    magic, _, _, filetype, command_count = struct.unpack_from("<5I", data)
    assert (magic, filetype) == (0xfeedfacf, 1)
    offset = 32
    for _ in range(command_count):
        cmd, size = struct.unpack_from("<2I", data, offset)
        if cmd == 0x19:
            count, = struct.unpack_from("<I", data, offset + 64)
            for index in range(count):
                section = offset + 72 + index * 80
                attributes, = struct.unpack_from("<I", data, section + 64)
                if not attributes & 0x02000000:  # S_ATTR_DEBUG
                    start = section + 16
                    name = bytes(data[start:start + 16]).rstrip(b"\0")
                    data[start:start + 16] = rename(name).ljust(16, b"\0")
        offset += size
    obj.write_bytes(data)


rewrite_sections(
    config / "lastkernelconstructor.o",
    lambda name: b"__LASTDATA_CONST" if name == b"__DATA" else name,
)
for entry in listing_text.splitlines():
    if "/libsa/" in entry:
        rewrite_sections(
            Path(entry.replace(ci_root, str(tree))),
            lambda name: b"__KLD" if name in (b"__TEXT", b"__KLD") else b"__KLDDATA",
        )

listing = config / "link.local.filelist"
listing.write_text(listing_text.replace(ci_root, str(tree)))
flags = shlex.split((config / ".LDFLAGS").read_text().rstrip("\0").replace(ci_root, str(tree)))[1:]
ld_flags = []
for flag in flags:
    if flag in ("-nostdlib", "-fapple-kext", "-DXNU_TARGET_OS_OSX", "-Wl,-new_linker", "-lcc_kext"):
        continue
    if flag.startswith("-mmacosx-version-min="):
        version = flag.split("=", 1)[1]
        ld_flags.extend(("-platform_version", "macos", version, version))
    elif flag.startswith("-Wl,"):
        ld_flags.extend(flag[4:].split(","))
    else:
        ld_flags.append(flag)

run(
    tools / "ld", *ld_flags, "-filelist", listing, "version.o",
    "lastkerneldataconst.o", "lastkernelconstructor.o", "nonlto.o", "linux-kernel-runtime.o",
    "-o", "kernel.development.herolte.unstripped",
)
