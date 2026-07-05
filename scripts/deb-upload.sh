#!/usr/bin/env bash
#
# deb-upload.sh — build a SIGNED source package for a tool+series and upload it
# to the Launchpad PPA (ppa:dreunion61/media-preservation). Launchpad then builds
# the .debs on its own farm. This is the "publish" counterpart to deb-build.sh
# (which only test-builds locally).
#
# Usage:  scripts/deb-upload.sh <tool> <series> [--dry-run]
#           series: noble | jammy
#           --dry-run: build + sign only, do NOT upload (verify first)
#
# Signing: the dedicated passphrase-less packaging key is exported from the
# host ~/.gnupg to a private 0600 temp file, bind-mounted read-only into the
# builder container, and shredded on exit. Needs network + ~/.gnupg, so run it
# OUTSIDE the command sandbox.
set -euo pipefail

TOOL=${1:?usage: deb-upload.sh <tool> <series> [--dry-run]}
SERIES=${2:?usage: deb-upload.sh <tool> <series> [--dry-run]}
DRY=0
[ "${3:-}" = "--dry-run" ] && DRY=1

# Full fingerprint (dpkg-buildpackage -k prefers it over the short key id).
KEYID=F95E3A17D02ED2D53C54DA78E2E956CC4B250741
PPA=ppa:dreunion61/media-preservation

case "$SERIES" in
  noble) BASE=docker.io/library/ubuntu:24.04 ;;
  jammy) BASE=docker.io/library/ubuntu:22.04 ;;
  *) echo "unknown series '$SERIES' (expected noble|jammy)" >&2; exit 2 ;;
esac

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
IMG="mp-deb-builder:${SERIES}"
OUT="$ROOT/.deb-out/${TOOL}-${SERIES}-upload"

if ! podman image exists "$IMG"; then
  echo ":: building builder image $IMG (from $BASE)"
  podman build --build-arg "BASE=${BASE}" -t "$IMG" \
    -f "$ROOT/scripts/deb/Containerfile" "$ROOT/scripts/deb"
fi

# Export the signing key to a private, short-lived file; shred it on exit.
KEYDIR=$(mktemp -d)
chmod 700 "$KEYDIR"
cleanup() { shred -u "$KEYDIR/signing-key.gpg" 2>/dev/null || true; rm -rf "$KEYDIR"; }
trap cleanup EXIT
gpg --batch --yes --export-secret-keys "$KEYID" > "$KEYDIR/signing-key.gpg"
chmod 600 "$KEYDIR/signing-key.gpg"

mkdir -p "$OUT"
echo ":: $([ "$DRY" = 1 ] && echo DRY-RUN || echo UPLOAD) — $TOOL ($SERIES) → $PPA"
podman run --rm \
  --security-opt label=disable \
  -e KEYID="$KEYID" -e PPA="$PPA" -e DRYRUN="$DRY" \
  -v "$ROOT:/repo:ro" \
  -v "$KEYDIR:/keys:ro" \
  -v "$OUT:/out" \
  "$IMG" /repo/scripts/deb/upload-in-container.sh "$TOOL" "$SERIES"

echo ":: done ($([ "$DRY" = 1 ] && echo 'dry-run, nothing uploaded' || echo 'uploaded'))."
