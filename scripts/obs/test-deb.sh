#!/bin/bash
#
# test-deb.sh <debian:12|debian:13|ubuntu:24.04|...> <tool> [<tool> ...]
#
# Replay locally, exactly, what OBS does to build a .deb -- before pushing:
#
#   1. download the spec's remote Source: URLs   (OBS: the download_files service)
#   2. take <tool>.dsc, debian.tar.gz, debian.changelog from git
#                                                (OBS: the download_url services)
#   3. run debtransform over that directory      (OBS: the build script does this)
#   4. dpkg-buildpackage the source package it produced, in the target's container
#
# Step 3 is the one worth having: debtransform is where a .dsc that names a source
# wrongly, or a debian/ that lost a mode bit, turns into a package that is broken
# but still builds. Finding that out from a red OBS build costs a push and ten
# minutes; finding it here costs neither.
#
# The container is NOT a substitute for a VM when the question is whether the
# packaged tool RUNS: a binary carrying cap_sys_rawio cannot even be exec'd in a
# default container (CAP_SYS_RAWIO is absent from the bounding set, so the kernel
# refuses the execve outright). That is a property of the container, not a bug in
# the package -- see the drive-access-verification skill.
set -euo pipefail

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
IMAGE=${1:?image, e.g. debian:13}
shift
[ $# -gt 0 ] || { echo "usage: test-deb.sh <image> <tool>..." >&2; exit 1; }

WORK=$(mktemp -d)
# The container writes into $WORK as root, so a plain rm cannot remove what it
# left behind -- and a test harness that litters /tmp with root-owned trees is a
# harness people stop running. podman unshare enters the user namespace where
# those files are ours.
cleanup() { rm -rf "$WORK" 2>/dev/null || podman unshare rm -rf "$WORK"; }
trap cleanup EXIT

cat > "$WORK/build.sh" <<'EOF'
set -e
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq build-essential debhelper devscripts equivs >/dev/null 2>&1
cd /work
dsc=$(ls out/*.dsc)
dpkg-source -x "$dsc" tree >/dev/null 2>&1
cd tree
echo "   debian/rules: $(stat -c %A debian/rules)"
mk-build-deps -i -r -t "apt-get -y -qq --no-install-recommends" debian/control >/dev/null 2>&1
if dpkg-buildpackage -b -us -uc > /work/log 2>&1; then
    echo "   BUILD OK"
    for d in /work/*.deb; do
        printf '     %-34s %s\n' "$(basename "$d")" "$(du -h "$d" | cut -f1)"
    done
else
    echo "   BUILD FAILED"
    tail -15 /work/log | sed 's/^/     /'
    exit 1
fi
EOF

rc=0
for tool in "$@"; do
    echo "== $tool  ($IMAGE)"
    d="$WORK/$tool"; mkdir -p "$d/pkg" "$d/out"

    # 1. the upstream artefacts, straight from the spec -- what download_files does
    rpmspec -P "$REPO/fedora/$tool/$tool.spec" 2>/dev/null \
      | sed -n 's/^Source[0-9]*:[[:space:]]*//p' | grep -E '^[a-z]+://' \
      | while read -r url; do
            name=${url##*#/}; [ "$name" = "$url" ] && name=${url##*/}
            curl -fsSL -o "$d/pkg/$name" "${url%%#*}"
        done

    # 2. our three files -- what the download_url services fetch from git
    cp "$REPO/opensuse/$tool/$tool.dsc"      "$d/pkg/"
    cp "$REPO/opensuse/$tool/debian.tar.gz"  "$d/pkg/"
    cp "$REPO/ubuntu/$tool/debian/changelog" "$d/pkg/debian.changelog"

    # 3. debtransform (its helpers live next to it and are not in PATH)
    PATH="/usr/lib/build:$PATH" /usr/lib/build/debtransform \
        "$d/pkg" "$d/pkg/$tool.dsc" "$d/out" > "$d/debtransform.log" 2>&1 || {
            echo "   DEBTRANSFORM FAILED"; tail -5 "$d/debtransform.log" | sed 's/^/     /'
            rc=1; continue; }

    # 4. the real oracle
    podman run --rm -v "$d:/work:z" "$IMAGE" bash /work/../build.sh 2>/dev/null \
      || podman run --rm -v "$d:/work:z" -v "$WORK/build.sh:/build.sh:z" "$IMAGE" \
             bash /build.sh || rc=1
done
exit $rc
