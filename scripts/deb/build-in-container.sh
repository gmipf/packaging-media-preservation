#!/bin/bash
#
# build-in-container.sh — assemble the source package for one tool and run a
# local test build. Executed INSIDE the mp-deb-builder:<series> container by
# scripts/deb-build.sh; not meant to be run on the host.
#
#   $1 = tool (redumper|aaru5|...)   $2 = series (noble|jammy)
#
# The upstream fetch + orig assembly + debian/ staging + changelog retarget is
# shared with the signed-upload path via scripts/deb/assemble.sh, so this file
# only adds the test build (full: source + binary, unsigned) and lintian.
set -euo pipefail

TOOL=${1:?tool}
SERIES=${2:?series}
REPO=/repo
OUT=/out
RECIPE="$REPO/ubuntu/$TOOL"

[ -d "$RECIPE/debian" ] || { echo "no recipe at $RECIPE/debian" >&2; exit 1; }

WORK=$(mktemp -d)
bash "$REPO/scripts/deb/assemble.sh" "$TOOL" "$SERIES" "$RECIPE" "$WORK"

VER=$(dpkg-parsechangelog -l "$RECIPE/debian/changelog" -SVersion | sed -e 's/-[^-]*$//')
SRC="$WORK/${TOOL}-${VER}"

echo ":: dpkg-buildpackage (source + binary, unsigned)"
( cd "$SRC" && dpkg-buildpackage -us -uc )

echo ":: collecting artifacts into /out"
mkdir -p "$OUT"
# ${TOOL}*.deb (not ${TOOL}_*.deb) so multi-binary sources also collect their
# sub-package .debs, e.g. mpf -> mpf-check_*, mpf-cli_*, mpf-gui_* (hyphen, not
# the underscore of the source-named artifacts).
cp -v "$WORK"/${TOOL}*.deb "$WORK"/${TOOL}_*.dsc "$WORK"/${TOOL}_*.orig.tar.* \
      "$WORK"/${TOOL}_*.debian.tar.* "$WORK"/${TOOL}_*.changes "$WORK"/${TOOL}_*.buildinfo \
      "$OUT/" 2>/dev/null || true

echo ":: lintian"
lintian --no-tag-display-limit "$WORK"/${TOOL}_*.changes || true

echo ":: done — artifacts in $OUT"
ls -1 "$OUT"
