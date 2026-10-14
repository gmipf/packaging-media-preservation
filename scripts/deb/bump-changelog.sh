#!/bin/bash
#
# bump-changelog.sh <recipe-dir> <debian-upstream-version> <message> [<revision>]
#
# Prepend a fresh UNRELEASED changelog stanza to <recipe-dir>/debian/changelog so
# OBS builds <version>-<revision> for every Debian and Ubuntu target. Pure bash
# (no dch, so it needs nothing beyond coreutils) but produces the exact stanza
# format dch would. <revision> defaults to 1, a new upstream version; a rebuild
# of the same version with other content needs the next one, or apt sees the
# version it already has and never upgrades.
#
# Called by the watch-<tool> workflows in lockstep with the fedora spec bump, so
# both distro lanes advance to the same upstream revision in one commit.
set -euo pipefail

RECIPE=${1:?recipe-dir}
VER=${2:?debian-upstream-version}
MSG=${3:?message}
REV=${4:-1}
[[ $REV =~ ^[1-9][0-9]*$ ]] || { echo "revision must be a positive integer, got '$REV'" >&2; exit 1; }

CL="$RECIPE/debian/changelog"
[ -f "$CL" ] || { echo "no changelog at $CL" >&2; exit 1; }

# Source (package) name = the first token of the existing changelog's top line
# (authoritative — it must match debian/control's Source: field). Reading it
# from the changelog rather than the dir name keeps the stanza correct even if
# the recipe dir is ever renamed or staged elsewhere.
SRC=$(head -1 "$CL" | cut -d' ' -f1)
[ -n "$SRC" ] || { echo "could not read source name from $CL" >&2; exit 1; }
DATE=$(date -uR)

TMP=$(mktemp)
{
  printf '%s (%s-%s) UNRELEASED; urgency=medium\n\n' "$SRC" "$VER" "$REV"
  printf '  * %s\n\n' "$MSG"
  printf ' -- gmipf <gmipf64@gmail.com>  %s\n\n' "$DATE"
  cat "$CL"
} > "$TMP"
mv "$TMP" "$CL"

echo ":: bumped $CL -> ${VER}-${REV} (UNRELEASED)"
head -1 "$CL"
