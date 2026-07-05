#!/usr/bin/env bash
#
# deb-build.sh — local test build of a tool's Ubuntu package, in a clean
# series-exact Podman container (the Debian analogue of `mock` on the RPM
# side). Proves the recipe builds BEFORE anything touches Launchpad.
#
# For a Launchpad PPA the published .debs are built by Launchpad itself from a
# signed *source* package; this script builds locally only to catch failures
# without the slow upload round-trip. The signed source upload is a separate
# step (needs the Launchpad account + GPG key) — see ubuntu/README.md.
#
# Usage:  scripts/deb-build.sh <tool> [series]   (series: noble|jammy, default noble)
#
# Needs network (pulls the base image, apt, fetches upstream release assets) —
# run it outside the command sandbox.
set -euo pipefail

TOOL=${1:?usage: deb-build.sh <tool> [series]}
SERIES=${2:-noble}

case "$SERIES" in
  noble) BASE=docker.io/library/ubuntu:24.04 ;;
  jammy) BASE=docker.io/library/ubuntu:22.04 ;;
  *) echo "unknown series '$SERIES' (expected noble|jammy)" >&2; exit 2 ;;
esac

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
IMG="mp-deb-builder:${SERIES}"
OUT="$ROOT/.deb-out/${TOOL}-${SERIES}"

if ! podman image exists "$IMG"; then
  echo ":: building builder image $IMG (from $BASE)"
  podman build --build-arg "BASE=${BASE}" -t "$IMG" \
    -f "$ROOT/scripts/deb/Containerfile" "$ROOT/scripts/deb"
fi

mkdir -p "$OUT"
echo ":: running build for $TOOL ($SERIES)"
podman run --rm \
  --security-opt label=disable \
  -v "$ROOT:/repo:ro" \
  -v "$OUT:/out" \
  "$IMG" /repo/scripts/deb/build-in-container.sh "$TOOL" "$SERIES"

echo ":: artifacts in $OUT"
