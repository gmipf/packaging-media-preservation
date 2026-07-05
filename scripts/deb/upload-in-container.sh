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

VER=$(dpkg-parsechangelog -l "$RECIPE/debian/changelog" -SVersion | sed -e 's/-[^-]*$//')
SRC="$WORK/${TOOL}-${VER}"

echo ":: building SIGNED source package (key $KEYID)"
( cd "$SRC" && dpkg-buildpackage -S -sa -k"$KEYID" )

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
