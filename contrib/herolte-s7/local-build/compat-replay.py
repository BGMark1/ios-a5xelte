#!/usr/bin/env python3
"""Apply temporary upstream clang adjustments to an extracted HEROLTE build tree."""

from pathlib import Path
import sys


tree = Path(sys.argv[1]).resolve()
for filename in ("xnu/osfmk/kern/kalloc.h", "build/xnu.obj/EXPORT_HDRS/osfmk/kern/kalloc.h"):
    header = tree / filename
    text = header.read_text()
    guard = "#if XNU_NO_TYPE_BUILTINS\n"
    if guard in text:
        continue
    start = text.index("#define KALLOC_TYPE_IS_COMPATIBLE_PTR")
    end = text.index("#define KALLOC_TYPE_ASSERT_COMPATIBLE_POINTER", start)
    text = (
        text[:start] + guard +
        "#define KALLOC_TYPE_IS_COMPATIBLE_PTR(ptr, type) (1)\n#else\n" +
        text[start:end].rstrip() + "\n#endif\n\n" + text[end:]
    )
    header.chmod(header.stat().st_mode | 0o200)
    header.write_text(text)

header = tree / "xnu/osfmk/arm64/corecrypto/arm64_isa_compatibility.h"
text = header.read_text().replace(
    "#if defined(__clang__) && ((defined(__apple_build_version__) && __apple_build_version__ > 5010000))",
    "#if defined(__clang__)",
)
header.write_text(text)

for header in (
    tree / "xnu/libkern/libkern/c++/OSData.h",
    tree / "build/xnu.obj/EXPORT_HDRS/libkern/libkern/c++/OSData.h",
):
    if header.exists():
        text = header.read_text()
        patched = text.replace(
            "static_assert(KALLOC_TYPE_IS_DATA_ONLY(T)",
            "static_assert(XNU_NO_TYPE_BUILTINS || KALLOC_TYPE_IS_DATA_ONLY(T)",
        )
        if patched != text:
            header.chmod(header.stat().st_mode | 0o200)
            header.write_text(patched)

# Apple Clang emits this destructor as a terminator. Upstream clang
# lowers it to an atexit registration, so put it in the same section.
bootstrap = tree / "xnu/libsa/bootstrap.cpp"
text = bootstrap.read_text()
old = "LIBKERN_ALWAYS_DESTROY static KLDBootstrap sBootstrapObject;"
new = """static KLDBootstrap sBootstrapObject;

static void
disposeBootstrapObject(void)
{
	sBootstrapObject.~KLDBootstrap();
}

__attribute__((used, section("__DATA,__mod_term_func,mod_term_funcs")))
static void (*const bootstrapTerminator)(void) = disposeBootstrapObject;"""
if old in text:
    bootstrap.write_text(text.replace(old, new))
