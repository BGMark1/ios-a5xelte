# Local HEROLTE kernel build under WSL

`kernel.development.herolte` was compiled and linked under Ubuntu 26.04 in
WSL from the build tree for CI run `42477676441`, source revision `e929651`.
This is the HEROLTE `DEVELOPMENT` configuration on Apple XNU `8796.141.3`.
The build needs an existing HEROLTE build tree because it reuses generated
Xcode iig and MIG files, configuration headers, symbol aliases, and linker
recipes. It recompiles the kernel and firehose library from source.

Run these commands in Ubuntu from the workspace root
`/mnt/e/Ai models/MacOSX Port`.

```bash
bash s7-setup/local-xnu-work/build.sh \
  s7-setup/night-tests/ci-42477676441-buildtree/buildtree.tgz

# Use the Work tree path printed by build.sh.
python3 s7-setup/local-xnu-work/check-kernel.py /tmp/herolte-xnu.XXXXXX \
  s7-setup/night-tests/ci-42477676441/kernel.development.herolte

(cd s7-setup/local-xnu-work && sha256sum -c SHA256SUMS)
```

The build keeps all generated files in its printed WSL directory, including
`replay-logs` and the unstripped kernel under
`build/xnu.obj/DEVELOPMENT_ARM64_HEROLTE`. Set `JOBS` to adjust compile
parallelism. Ubuntu clang 21, Python 3, and the standard archive tools are
required. The script downloads the GNU make and LLVM 21 packages and extracts
them into the work tree without installing them. It checks the SHA-256 of the
pinned Theos Linux toolchain and downloads Apple's libdispatch `1415.140.2`
sources. Set `HEROLTE_TOOLCACHE` to an earlier work tree's `toolcache`
directory to reuse the downloaded tools. The tools used for the staged build
are in `/tmp/herolte-xnu.mbWQdb/toolcache`.

The local build uses the HakiOS clang wrapper and allocator compatibility
guards. These guards give allocations a conservative mixed pointer/data
signature on upstream Clang. The build also selects upstream-compatible SHA
assembly syntax and explicitly emits the bootstrap destructor as a Mach-O
terminator. The link preserves the XNU section renames for `__KLD`,
`__KLDDATA`, and `__LASTDATA_CONST`. HakiOS's runtime shims cover static
destructor registration and make the compiler profiling hooks report
unavailable data. The DWARF 4 build retains its symbol table for runtime
symbolization. Its addresses and debug records differ from the CI build.

The staged kernel came from `/tmp/herolte-xnu.P8vUPp`. All 1,110 object
recipes compiled and the link emitted an arm64 `MH_EXECUTE` with
`MH_NOUNDEFS` and a valid `LC_UNIXTHREAD` entry. Its loadable segment names
and protections match the CI kernel, and both have a `__TEXT` base of
`0xfffffff007004000`. An LLVM disassembly scan found zero LSE instruction
matches outside the SHA-256 constant table across 2,242,631 instruction lines.
`mkpayload.py` successfully packed it with `s7-setup/herolte-750-2g.adt`.
Device boot and runtime remain unverified.

Set `HEROLTE_SOURCE_PATCH` to an absolute path to a unified Git patch to
compile edits to existing source files. Patch paths are relative to the
archived XNU source root, for example `bsd/dev/herolte_gpu.c`. Changes
to configuration, generated interfaces, exported headers, symbol sets, or
the set of linked files need corresponding regeneration. A clean build
from the Apple release and the patch series alone remains separate work.

A second clean build from the same archive completed in
`/tmp/herolte-xnu.oOU33T`. The output hashes can differ across work trees
because the linker and debug records contain build-specific metadata.
