#!/bin/bash
#
# upload-in-container.sh — build a SIGNED *source* package for one tool+series
# and (unless DRYRUN=1) dput it to the Launchpad PPA. Executed INSIDE the
# mp-deb-builder:<series> container by scripts/deb-upload.sh; not for host use.
#
#   $1 = tool (redumper|aaru5|...)   $2 = series (noble|jammy)
#
# Env in:
#   KEYID   signing key id (imported from the bind-mounted /keys/signing-key.gpg)
#   PPA     dput target, e.g. ppa:dreunion61/media-preservation
#   DRYRUN  1 = build + sign only (verify), do not upload
#
# The upstream fetch + orig assembly + debian/ staging + changelog retarget is
# shared with the test-build path via scripts/deb/assemble.sh. Launchpad builds
# the .deb itself from this signed source package, hermetically (no network at
# build time) — which is fine because our orig tarball already contains the
# upstream prebuilt binary; debian/rules only stamps the manpage.
set -euo pipefail

TOOL=${1:?tool}
SERIES=${2:?series}
KEYID=${KEYID:?KEYID}
PPA=${PPA:?PPA}
REPO=/repo
OUT=/out
RECIPE="$REPO/ubuntu/$TOOL"

[ -d "$RECIPE/debian" ] || { echo "no recipe at $RECIPE/debian" >&2; exit 1; }

# Import the signing key into a throwaway keyring (passphrase-less dedicated key).
export GNUPGHOME
GNUPGHOME=$(mktemp -d)
chmod 700 "$GNUPGHOME"
gpg --batch --import /keys/signing-key.gpg
echo ":: imported signing key $KEYID"

WORK=$(mktemp -d)
bash "$REPO/scripts/deb/assemble.sh" "$TOOL" "$SERIES" "$RECIPE" "$WORK"

FULLVER=$(dpkg-parsechangelog -l "$RECIPE/debian/changelog" -SVersion)
VER=${FULLVER%-*}
SRC="$WORK/${TOOL}-${VER}"

# Launchpad stores ONE immutable <src>_<upstream>.orig.tar.xz forever and
# rejects an upload carrying different bytes under that name. A -1 revision is
# a new upstream version, so send the orig (-sa). A -2+ revision is
# packaging-only: the orig is already stored and may predate our
# byte-reproducible assembly, so it generally cannot be rebuilt byte-for-byte.
# Never re-send it (-sd); Launchpad reuses what it has.
if [ "${FULLVER##*-}" = "1" ]; then SRCOPT=-sa; else SRCOPT=-sd; fi

echo ":: building SIGNED source package (key $KEYID, $SRCOPT)"
( cd "$SRC" && dpkg-buildpackage -S "$SRCOPT" -k"$KEYID" )

CHANGES=$(ls -1 "$WORK"/${TOOL}_*_source.changes | head -1)
mkdir -p "$OUT"
cp -v "$WORK"/${TOOL}_* "$OUT/" 2>/dev/null || true

echo ":: verifying signature on $(basename "$CHANGES")"
gpg --verify "$CHANGES" 2>&1 | sed -n '1,4p' || true

if [ "${DRYRUN:-0}" = "1" ]; then
  echo ":: DRYRUN — signed source package built, NOT uploaded."
  echo ":: would run: dput $PPA $(basename "$CHANGES")"
else
  echo ":: uploading → dput $PPA"
  dput "$PPA" "$CHANGES"
  echo ":: upload submitted — Launchpad will email the result and build the .debs."
fi

echo ":: artifacts in $OUT"
ls -1 "$OUT"
