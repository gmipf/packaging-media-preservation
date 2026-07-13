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
FULLVER=$(dpkg-parsechangelog -l "$RECIPE/debian/changelog" -SVersion)
VER=${FULLVER%-*}
REV=${FULLVER##*-}
SRC="$WORK/${TOOL}-${VER}"
mkdir -p "$SRC"

LP_OWNER=${LP_OWNER:-dreunion61}
LP_PPA=${LP_PPA:-media-preservation}

# A packaging-only revision (-2, -3, ...) must be built against the EXACT
# orig tarball Launchpad already stores for this upstream version, not a
# freshly assembled one.
#
# Launchpad keeps one immutable <src>_<upstream>.orig.tar.xz per upstream
# version. Even with `dpkg-buildpackage -sd` (which omits the file from the
# upload) the .dsc still records its checksum, and Launchpad compares that
# against its stored copy. Our stored origs predate the mtime pinning in
# a1566e2, so re-assembling them yields different bytes and the upload is
# rejected. Fetch the stored file and unpack the source tree from it: the
# checksum then matches by construction, for any orig however it was built.
if [ "$REV" != "1" ]; then
  ORIG="$WORK/${TOOL}_${VER}.orig.tar.xz"
  echo ":: revision $REV -- reusing the orig Launchpad already stores"
  # The stored file is the same whichever series' upload we take it from -- but
  # it exists only under a series this tool was actually uploaded to. Ask for the
  # series being built first: redumper-gui lives ONLY on resolute (jammy and
  # noble top out at rustc-1.91, below eframe's 1.92 floor), so a list naming
  # neither found nothing at all, and its first packaging-only revision died here.
  got=
  for s in "$SERIES" resolute noble jammy; do
    url="https://launchpad.net/~${LP_OWNER}/+archive/ubuntu/${LP_PPA}/+sourcefiles/${TOOL}/${VER}-1~${s}1/${TOOL}_${VER}.orig.tar.xz"
    if curl -fsSL -o "$ORIG" "$url"; then got=$s; break; fi
  done
  [ -n "$got" ] || { echo "no stored orig for ${TOOL} ${VER} in ppa:${LP_OWNER}/${LP_PPA}" >&2; exit 1; }
  echo ":: fetched ${TOOL}_${VER}.orig.tar.xz (via ${VER}-1~${got}1), sha256 $(sha256sum "$ORIG" | cut -d' ' -f1)"
  tar -xf "$ORIG" -C "$WORK"
  [ -d "$SRC" ] || { echo "stored orig did not unpack to ${TOOL}-${VER}/" >&2; exit 1; }

  echo ":: staging debian/ and targeting series $SERIES"
  cp -a "$RECIPE/debian" "$SRC/debian"
  sed -i "1s/(\([^)]*\)) [A-Za-z][A-Za-z]*/(\1~${SERIES}1) ${SERIES}/" "$SRC/debian/changelog"
  head -1 "$SRC/debian/changelog"
  exit 0
fi

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
  aaru)
    # Two upstream tarballs (mirrors fedora/aaru): the binary tarball gives
    # the self-contained `aaru` single-file binary + LICENSE/README/Changelog;
    # the source tarball provides icons, the aaruformat MIME xml and the
    # desktop entry. The upstream ASSET version keeps the hyphen (6.0.0-alpha.19)
    # while the Debian VER uses the tilde (6.0.0~alpha.19) — different strings.
    # We merge both into one .orig tarball: binary files at top, source tree
    # under src/, so no Debian multi-component-orig machinery is needed.
    ASSETVER=${TAG#v}
    curl -fsSL -o "$WORK/bin.tar.xz" \
      "https://github.com/aaru-dps/Aaru/releases/download/${TAG}/aaru-${ASSETVER}_linux_amd64.tar.xz"
    curl -fsSL -o "$WORK/src.tar.xz" \
      "https://github.com/aaru-dps/Aaru/releases/download/${TAG}/aaru-src-${ASSETVER}.tar.xz"
    tar -xJf "$WORK/bin.tar.xz" -C "$SRC"
    mkdir -p "$SRC/src"
    tar -xJf "$WORK/src.tar.xz" -C "$SRC/src"
    ;;
  mpf)
    # Three self-contained .NET binaries from one rolling release (mirrors
    # fedora/mpf): MPF.Check at the top, MPF.CLI under cli/, MPF.Avalonia
    # under gui/. Each of cli/ and gui/ also carries a bundled Programs/
    # dumper tree (~tens of MB) that we drop — the package resolves the
    # system-installed redumper / aaru5 / discimagecreator via PATH instead.
    B="https://github.com/SabreTools/MPF/releases/download/${TAG}"
    curl -fsSL -o "$WORK/check.zip" "$B/MPF.Check_net10.0_linux-x64_release.zip"
    curl -fsSL -o "$WORK/cli.zip"   "$B/MPF.CLI_net10.0_linux-x64_release.zip"
    curl -fsSL -o "$WORK/gui.zip"   "$B/MPF.Avalonia_net10.0_linux-x64_release.zip"
    unzip -q "$WORK/check.zip" -d "$SRC"
    mkdir -p "$SRC/cli" "$SRC/gui"
    unzip -q "$WORK/cli.zip" -d "$SRC/cli"
    unzip -q "$WORK/gui.zip" -d "$SRC/gui"
    rm -rf "$SRC/cli/Programs" "$SRC/gui/Programs"
    # upstream names the GUI binary "MPF"; install it as MPF.Avalonia so the
    # role is obvious on disk (parity with the RPM).
    mv "$SRC/gui/MPF" "$SRC/gui/MPF.Avalonia"
    chmod 0755 "$SRC/MPF.Check" "$SRC/cli/MPF.CLI" "$SRC/gui/MPF.Avalonia"
    ;;
  redumper-gui)
    # The .orig tarball IS the vendored tarball published as a release asset on
    # the PACKAGING repo — not an upstream archive. Rust needs every crate present
    # at build time and the Launchpad farm has no network, so the crates have to
    # travel inside the source package. scripts/rust-vendor-tarball.sh builds it
    # (upstream tag + pinned Cargo.lock + crates filtered to x86_64-linux); COPR
    # and OBS consume the very same file, so all three lanes build byte-identical
    # sources. It already unpacks to redumper-gui-<ver>/, which is exactly $SRC.
    curl -fsSL -o "$WORK/vendored.tar.xz" \
      "https://github.com/gmipf/packaging-media-preservation/releases/download/${TOOL}-${VER}/${TOOL}-${VER}-vendored.tar.xz"
    tar -xJf "$WORK/vendored.tar.xz" -C "$WORK"
    [ -f "$SRC/Cargo.toml" ] || {
      echo "vendored tarball did not unpack to ${TOOL}-${VER}/" >&2; exit 1; }
    ;;
  discimagecreator)
    # Source build (NOT a repackage — the one tool we compile): four GitHub
    # archive tarballs merged into one tree, exactly as fedora's %setup -a 1/2/3.
    #   .upstream-tag = the pinned DiscImageCreator commit SHA (Source0)
    #   the three helper tools ride along at their own frozen tags (Source1/2/3).
    # These helper versions are hardcoded here (they change ~never) and mirrored
    # in debian/rules, which references the extracted <name>-<ver>/ dirs by path.
    ECCEDCVER=20240901
    DVDAUTHVER=1.4
    UNSCRAMBLVER=0.5.5
    curl -fsSL -o "$WORK/dic.tar.gz" \
      "https://github.com/saramibreak/DiscImageCreator/archive/${TAG}.tar.gz"
    curl -fsSL -o "$WORK/eccedc.tar.gz" \
      "https://github.com/saramibreak/EccEdc/archive/refs/tags/${ECCEDCVER}.tar.gz"
    curl -fsSL -o "$WORK/dvdauth.tar.gz" \
      "https://github.com/saramibreak/DVDAuth/archive/refs/tags/v${DVDAUTHVER}.tar.gz"
    curl -fsSL -o "$WORK/unscrambler.tar.gz" \
      "https://github.com/saramibreak/unscrambler/archive/refs/tags/${UNSCRAMBLVER}.tar.gz"
    # main source: strip the DiscImageCreator-<sha>/ wrapper straight into $SRC
    tar -xzf "$WORK/dic.tar.gz" -C "$SRC" --strip-components=1
    # helpers: keep their <name>-<ver>/ wrapper dir — debian/rules builds each
    # via `make -C <name>-<ver>/...`, matching the RPM's paths.
    tar -xzf "$WORK/eccedc.tar.gz"      -C "$SRC"
    tar -xzf "$WORK/dvdauth.tar.gz"     -C "$SRC"
    tar -xzf "$WORK/unscrambler.tar.gz" -C "$SRC"
    ;;
  *)
    echo "no fetch recipe for tool '$TOOL' yet" >&2; exit 1 ;;
esac

# Deterministic orig tarball. Launchpad shares ONE immutable
# <src>_<upstream>.orig.tar.xz across every series AND every Debian revision of
# that upstream version, so each upload must ship a byte-identical orig. Without
# a fixed mtime, tar stamps every entry (the top-level <tool>-<ver>/ dir, any
# mkdir'd subdirs, and curl/install'd files) with the assembly-time wall clock —
# and the upload path runs this once per series (resolute, then noble, then
# jammy seconds later), so the runs produced different origs and Launchpad
# rejected every series after the first ("orig already exists, different
# contents"). Pin every mtime and force the gnu format (stable across series).
#
# The epoch must depend on the UPSTREAM version alone. Reading it from the top
# changelog stanza would break the moment a packaging-only revision (-2, -3, ...)
# is added: same upstream payload, same immutable orig name, but a fresh stanza
# date => byte-different orig. So walk the stanzas and keep the OLDEST one
# carrying this upstream version — "when we first packaged this release". It is
# invariant under later revision bumps, and moves only when upstream itself moves.
#
# This makes the orig reproducible going forward; it does NOT make it match an
# orig Launchpad already stores from before the mtime pinning. That is why the
# upload path never re-sends the orig for a -2+ revision (dpkg-buildpackage -sd)
# rather than relying on rebuilding it byte-for-byte.
CL="$RECIPE/debian/changelog"
SOURCE_DATE_EPOCH=""
i=0
while v=$(dpkg-parsechangelog -l "$CL" --offset "$i" --count 1 -S Version 2>/dev/null) && [ -n "$v" ]; do
  [ "${v%-*}" = "$VER" ] && \
    SOURCE_DATE_EPOCH=$(dpkg-parsechangelog -l "$CL" --offset "$i" --count 1 -S Timestamp)
  i=$((i + 1))
done
[ -n "$SOURCE_DATE_EPOCH" ] || { echo "no changelog stanza for upstream version $VER" >&2; exit 1; }
echo ":: assembling orig tarball ${TOOL}_${VER}.orig.tar.xz (SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH)"
( cd "$WORK" && tar --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="@${SOURCE_DATE_EPOCH}" --format=gnu \
    -caf "${TOOL}_${VER}.orig.tar.xz" "${TOOL}-${VER}" )

echo ":: staging debian/ and targeting series $SERIES"
cp -a "$RECIPE/debian" "$SRC/debian"
# Rewrite the top changelog line: (5.4.2-1) UNRELEASED -> (5.4.2-1~noble1) noble
sed -i "1s/(\([^)]*\)) [A-Za-z][A-Za-z]*/(\1~${SERIES}1) ${SERIES}/" "$SRC/debian/changelog"
head -1 "$SRC/debian/changelog"
