#!/usr/bin/env python3
"""Replay compiler invocations from an extracted HEROLTE CI build tree."""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import subprocess
import sys


def main():
    tree = Path(sys.argv[1]).resolve()
    build = tree / "build/xnu.obj"
    config = build / "DEVELOPMENT_ARM64_HEROLTE"
    env = os.environ.copy()
    env.update(
        PATH=f"{tree}/compat/host/bin:{tree}/toolcache/usr/bin:{env['PATH']}",
        XNU_SDK_PATH=str(tree / "sdk-kernel-platform"),
        XNU_SDK_VERSION="15.0",
        XNU_PLATFORM_PATH=str(tree / "MacOSX.platform"),
    )
    make_args = [
        "make", "-n", "-k", f"SRCROOT={tree}/xnu", f"SOURCE_DIR={tree}/xnu",
        f"OBJROOT={build}", f"FAKEROOT_DIR={tree}/fakeroot", "XCRUN=xcrun",
        "CC=xnu-clang", "CXX=xnu-clang++", "CURRENT_MACHINE_CONFIG=HEROLTE",
        "CURRENT_ARCH_CONFIG=ARM64", "CURRENT_KERNEL_CONFIG=DEVELOPMENT",
        "ARCH_STRING_FOR_CURRENT_MACHINE_CONFIG=arm64", "BUILD_WERROR=0",
        "BUILD_LTO=0",
    ]
    targets = defaultdict(list)
    entries = (config / "link.filelist").read_text().splitlines()
    ci_root = entries[0].split("/build/xnu.obj/", 1)[0]
    for entry in entries:
        path = config / entry.split(config.name + "/", 1)[1]
        if not path.exists():
            targets[path.parent].append(path.name)

    logs = tree / "replay-logs"
    logs.mkdir(exist_ok=True)
    tasks = []
    for folder, objects in targets.items():
        component = folder.parent.name
        for makefile in [folder / "Makefile", *folder.glob("*.d"), *folder.glob("*.cpd")]:
            original = makefile.read_text()
            localized = original.replace(ci_root, str(tree))
            if localized != original:
                makefile.write_text(localized)
        result = subprocess.run(
            [*make_args, f"RELATIVE_SOURCE_PATH={component}",
             f"SOURCE={tree}/xnu/{component}/", f"TARGET={folder}/",
             f"INCFLAGS_EXTERN=-I{tree}/xnu/EXTERNAL_HEADERS -I{tree}/xnu", *objects],
            cwd=folder, env=env, capture_output=True, text=True,
        )
        (logs / (folder.parent.name + ".make.txt")).write_text(result.stdout + result.stderr)
        commands = [
            line for line in result.stdout.splitlines()
            if line.startswith(("xnu-clang -c ", "xnu-clang++ -o "))
        ]
        print(f"{folder.parent.name}: {len(commands)}/{len(objects)} recipes", flush=True)
        tasks.extend((folder, cmd) for cmd in commands)

    def compile_object(task):
        folder, command = task
        result = subprocess.run(
            ["bash", "-c", command], cwd=folder, env=env,
            capture_output=True, text=True,
        )
        return command, result

    failures = 0
    with ThreadPoolExecutor(max_workers=int(os.environ.get("JOBS", "8"))) as pool:
        futures = [pool.submit(compile_object, task) for task in tasks]
        with (logs / "compiler-errors.txt").open("w") as errors:
            for future in as_completed(futures):
                command, result = future.result()
                if result.returncode:
                    failures += 1
                    errors.write(command + "\n" + result.stderr + "\n")
    missing = [
        str(folder / name) for folder, objects in targets.items()
        for name in objects if not (folder / name).exists()
    ]
    (logs / "missing-objects.txt").write_text("\n".join(missing))
    print(f"{len(tasks) - failures}/{len(tasks)} recipes succeeded, {len(missing)} objects missing")
    return int(bool(missing))


if __name__ == "__main__":
    sys.exit(main())
