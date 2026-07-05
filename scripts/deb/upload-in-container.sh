#!/bin/bash
#
# upload-in-container.sh — build a SIGNED *source* package for one tool+series
# and (unless DRYRUN=1) dput it to the Launchpad PPA. Executed INSIDE the
# mp-deb-builder:<series> container by scripts/deb-upload.sh; not for host use.
#
#   $1 = tool (redumper|...)     $2 = series (noble|jammy)
#
# Env in:
#   KEYID   signing key id (imported from the bind-mounted /keys/signing-key.gpg)
#   PPA     dput target, e.g. ppa:dreunion61/media-preservation
#   DRYRUN  1 = build + sign only (verify), do not upload
#
# Launchpad builds the .deb itself from this signed source package, hermetically
# (no network at build time) — which is fine because our orig tarball already
# contains the upstream prebuilt binary; debian/rules only stamps the manpage.
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

echo ":: assembling orig tarball"
( cd "$WORK" && tar --sort=name --owner=0 --group=0 --numeric-owner \
    -caf "${TOOL}_${VER}.orig.tar.xz" "${TOOL}-${VER}" )

echo ":: staging debian/ and targeting series $SERIES"
cp -a "$RECIPE/debian" "$SRC/debian"
rm -f "$SRC/debian/${TOOL}.1"
sed -i "1s/(\([^)]*\)) [A-Za-z][A-Za-z]*/(\1~${SERIES}1) ${SERIES}/" "$SRC/debian/changelog"
head -1 "$SRC/debian/changelog"

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
