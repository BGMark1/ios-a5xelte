#!/bin/bash
set -euo pipefail

here=$(cd -- "$(dirname -- "$0")" && pwd)
repo=$(cd -- "$here/../.." && pwd)
artifact=$(realpath -- "${1:?usage: bash build.sh /path/to/buildtree.tgz}")
toolcache=${HEROLTE_TOOLCACHE:-}
if [[ -n "$toolcache" ]]; then
    toolcache=$(realpath -- "$toolcache")
fi
source_patch=${HEROLTE_SOURCE_PATCH:-}
if [[ -n "$source_patch" ]]; then
    source_patch=$(realpath -- "$source_patch")
fi
work=$(mktemp -d /tmp/herolte-xnu.XXXXXX)
echo "Work tree: $work"
cd "$work"
tar xzf "$artifact"
if [[ -n "$source_patch" ]]; then
    git -C xnu apply --whitespace=nowarn "$source_patch"
fi

if [[ -n "$toolcache" ]]; then
    ln -s "$toolcache" toolcache
else
    mkdir toolcache
    (
        cd toolcache
        apt-get download make llvm-21
        for deb in *.deb; do
            dpkg-deb -x "$deb" .
        done
        curl -fsSL --retry 2 -o theos-linux.tar.xz \
            https://github.com/L1ghtmann/llvm-project/releases/download/test-210562a/iOSToolchain-x86_64.tar.xz
        echo 'a72a7a577e2fbe2838b6b5e9c72034fa7d114af96f0e1d4b016f18730ce4056e  theos-linux.tar.xz' | sha256sum -c -
        tar xJf theos-linux.tar.xz
    )
fi

mkdir compat
cp -a "$repo/s9plus-reference/core/xnu-deps/"{host,hostinc} compat/
chmod +x compat/host/bin/*
ln -s xnu-clang compat/host/bin/xnu-clang++
ln -s "$work/toolcache/linux/iphone/bin/ld" compat/host/bin/ld64
sed -i 's/arm64-apple-ios/arm64-apple-macos/; s/^  -w /  -w -gdwarf-4 /' compat/host/bin/xnu-clang
curl -fsSL --retry 2 https://codeload.github.com/apple-oss-distributions/libdispatch/tar.gz/refs/tags/libdispatch-1415.140.2 | tar xz

python3 "$here/compat-replay.py" "$work"
python3 "$here/replay-objects.py" "$work"
python3 "$here/replay-link.py" "$work" 2>&1 | tee replay-logs/link.txt
kernel="$work/build/xnu.obj/DEVELOPMENT_ARM64_HEROLTE/kernel.development.herolte.unstripped"
file "$kernel"
sha256sum "$kernel"
