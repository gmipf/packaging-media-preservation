#!/bin/bash
#
# assemble.sh <tool> <series> <recipe-dir> <work-dir>
#
# Fetch the upstream release artifacts for <tool> (the same URLs the RPM spec's
# spectool pulls), build the .orig tarball, unpack the source tree, stage
# debian/ into it and retarget the top changelog line to <series>. Shared by
# build-in-container.sh (local test build) and upload-in-container.sh (signed
# PPA upload) so each tool's fetch recipe lives in exactly ONE place.
#
# The resulting layout under <work-dir>:
#   <tool>_<ver>.orig.tar.xz     the upstream payload
#   <tool>-<ver>/                unpacked tree + staged debian/
#
# <ver> is the Debian upstream version, derived from the committed changelog
# (version minus the -revision) — this is what dpkg-buildpackage expects the
# .orig tarball to be named after, so the caller can recompute it the same way
# to locate <tool>-<ver>/ without us having to echo anything back.
set -euo pipefail

TOOL=${1:?tool}
SERIES=${2:?series}
RECIPE=${3:?recipe-dir}
WORK=${4:?work-dir}

TAG=$(cat "$RECIPE/.upstream-tag")
VER=$(dpkg-parsechangelog -l "$RECIPE/debian/changelog" -SVersion | sed -e 's/-[^-]*$//')
SRC="$WORK/${TOOL}-${VER}"
mkdir -p "$SRC"

echo ":: fetching upstream $TOOL $TAG (version $VER)"
case "$TOOL" in
  redumper)
    mkdir -p "$SRC/bin"
    curl -fsSL -o "$WORK/up.zip" \
      "https://github.com/superg/redumper/releases/download/${TAG}/redumper-${TAG}-linux-x64.zip"
    unzip -q "$WORK/up.zip" -d "$WORK"
    install -m0755 "$WORK/redumper-${TAG}-linux-x64/bin/redumper" "$SRC/bin/redumper"
    curl -fsSL -o "$SRC/LICENSE"   "https://raw.githubusercontent.com/superg/redumper/${TAG}/LICENSE"
    curl -fsSL -o "$SRC/README.md" "https://raw.githubusercontent.com/superg/redumper/${TAG}/README.md"
    ;;
  aaru5)
    # Single-tarball repackage: the prebuilt linux_amd64 NativeAOT release
    # drops `aaru`, its libe_sqlite3.so sidecar and the LICENSE/README/
    # Changelog/CONTRIBUTING docs directly into the extraction dir (rootless).
    curl -fsSL -o "$WORK/aaru5.tar.xz" \
      "https://github.com/aaru-dps/Aaru/releases/download/${TAG}/aaru-${VER}_linux_amd64.tar.xz"
    tar -xJf "$WORK/aaru5.tar.xz" -C "$SRC"
    ;;
  *)
    echo "no fetch recipe for tool '$TOOL' yet" >&2; exit 1 ;;
esac

echo ":: assembling orig tarball ${TOOL}_${VER}.orig.tar.xz"
( cd "$WORK" && tar --sort=name --owner=0 --group=0 --numeric-owner \
    -caf "${TOOL}_${VER}.orig.tar.xz" "${TOOL}-${VER}" )

echo ":: staging debian/ and targeting series $SERIES"
cp -a "$RECIPE/debian" "$SRC/debian"
# Rewrite the top changelog line: (5.4.2-1) UNRELEASED -> (5.4.2-1~noble1) noble
sed -i "1s/(\([^)]*\)) [A-Za-z][A-Za-z]*/(\1~${SERIES}1) ${SERIES}/" "$SRC/debian/changelog"
head -1 "$SRC/debian/changelog"
