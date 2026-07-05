#!/bin/bash
#
# build-in-container.sh — assemble the source package for one tool and run a
# local test build. Executed INSIDE the mp-deb-builder:<series> container by
# scripts/deb-build.sh; not meant to be run on the host.
#
#   $1 = tool (redumper|...)      $2 = series (noble|jammy)
#
# It fetches the upstream release artifacts (the same URLs the RPM spec's
# spectool pulls), builds the .orig tarball, injects the ~<series> version into
# the changelog, then runs dpkg-buildpackage (full: source + binary, unsigned)
# and lintian. Artifacts land in /out (bind-mounted from the host).
set -euo pipefail

TOOL=${1:?tool}
SERIES=${2:?series}
REPO=/repo
OUT=/out
RECIPE="$REPO/ubuntu/$TOOL"

[ -d "$RECIPE/debian" ] || { echo "no recipe at $RECIPE/debian" >&2; exit 1; }

TAG=$(cat "$RECIPE/.upstream-tag")   # e.g. b726
VER=${TAG#b}                          # 726

WORK=$(mktemp -d)
SRC="$WORK/${TOOL}-${VER}"
mkdir -p "$SRC/bin"

echo ":: fetching upstream $TOOL $TAG"
case "$TOOL" in
  redumper)
    curl -fsSL -o "$WORK/up.zip" \
      "https://github.com/superg/redumper/releases/download/${TAG}/redumper-${TAG}-linux-x64.zip"
    unzip -q "$WORK/up.zip" -d "$WORK"
    install -m0755 "$WORK/redumper-${TAG}-linux-x64/bin/redumper" "$SRC/bin/redumper"
    curl -fsSL -o "$SRC/LICENSE"   "https://raw.githubusercontent.com/superg/redumper/${TAG}/LICENSE"
    curl -fsSL -o "$SRC/README.md" "https://raw.githubusercontent.com/superg/redumper/${TAG}/README.md"
    ;;
  *)
    echo "no fetch recipe for tool '$TOOL' yet" >&2; exit 1 ;;
esac

echo ":: assembling orig tarball ${TOOL}_${VER}.orig.tar.xz"
( cd "$WORK" && tar --sort=name --owner=0 --group=0 --numeric-owner \
    -caf "${TOOL}_${VER}.orig.tar.xz" "${TOOL}-${VER}" )

echo ":: staging debian/ and targeting series $SERIES"
cp -a "$RECIPE/debian" "$SRC/debian"
# Drop any stray generated manpage so dpkg-source sees a clean tree.
rm -f "$SRC/debian/${TOOL}.1"
# Rewrite the top changelog line: (726-1) UNRELEASED -> (726-1~noble1) noble
sed -i "1s/(\([^)]*\)) [A-Za-z][A-Za-z]*/(\1~${SERIES}1) ${SERIES}/" "$SRC/debian/changelog"
head -1 "$SRC/debian/changelog"

echo ":: dpkg-buildpackage (source + binary, unsigned)"
( cd "$SRC" && dpkg-buildpackage -us -uc )

echo ":: collecting artifacts into /out"
mkdir -p "$OUT"
cp -v "$WORK"/${TOOL}_*.deb "$WORK"/${TOOL}_*.dsc "$WORK"/${TOOL}_*.orig.tar.* \
      "$WORK"/${TOOL}_*.debian.tar.* "$WORK"/${TOOL}_*.changes "$WORK"/${TOOL}_*.buildinfo \
      "$OUT/" 2>/dev/null || true

echo ":: lintian"
lintian --no-tag-display-limit "$WORK"/${TOOL}_*.changes || true

echo ":: done — artifacts in $OUT"
ls -1 "$OUT"
