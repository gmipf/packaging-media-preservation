#!/usr/bin/env bash
#
# deb-build.sh — local test build of a tool's .deb, in a clean series-exact
# Podman container (the Debian analogue of `mock` on the RPM side). Proves the
# recipe builds BEFORE anything touches Launchpad or OBS.
#
# Two consumers, two publishers:
#   Ubuntu (noble, jammy)      -> Launchpad PPA, which builds the published
#                                 .debs itself from a signed *source* package.
#   Debian (bookworm, trixie)  -> OBS, which Launchpad cannot serve: a PPA only
#                                 ever builds Ubuntu series, and an Ubuntu .deb
#                                 does not install cleanly on Debian anyway (the
#                                 ICU runtime package is soname-versioned:
#                                 libicu70 on jammy vs libicu72 on bookworm).
# Either way this script only builds locally, to catch failures without the slow
# upload round-trip. The signed source upload is a separate step (needs the
# Launchpad account + GPG key) — see ubuntu/README.md.
#
# The recipes under ubuntu/<tool>/debian/ are deliberately series-agnostic and
# are reused for Debian unchanged: the ICU dependency is resolved from what
# libicu-dev pulled into the build root (see each rules file's ${dep:icu}), not
# from a hardcoded per-series table.
#
# Usage:  scripts/deb-build.sh <tool> [series]
#         series: noble|jammy|bookworm|trixie   (default noble)
#
# Needs network (pulls the base image, apt, fetches upstream release assets) —
# run it outside the command sandbox.
set -euo pipefail

TOOL=${1:?usage: deb-build.sh <tool> [series]}
SERIES=${2:-noble}

case "$SERIES" in
  # resolute is the ONLY series that can build redumper-gui: its rustc is 1.93,
  # and eframe/egui 0.35 needs 1.92 (jammy/noble top out at rustc-1.91).
  resolute) BASE=docker.io/library/ubuntu:26.04 ;;
  noble)    BASE=docker.io/library/ubuntu:24.04 ;;
  jammy)    BASE=docker.io/library/ubuntu:22.04 ;;
  bookworm) BASE=docker.io/library/debian:12 ;;
  trixie)   BASE=docker.io/library/debian:13 ;;
  *) echo "unknown series '$SERIES' (expected resolute|noble|jammy|bookworm|trixie)" >&2; exit 2 ;;
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
