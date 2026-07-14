#!/usr/bin/env bash
# Build the vendored source tarball for a Rust tool and (optionally) publish it
# as a release asset on this packaging repo.
#
# WHY THIS EXISTS
# ---------------
# Rust needs every dependency crate present at build time, and none of our three
# build systems can fetch them:
#
#   * COPR's mock chroot has no network at all (enable_net does not help --
#     cargo/npm/pip all fail there),
#   * no OBS build root has network either,
#   * OBS source services can download a URL but cannot run cargo.
#
# So the crates have to be inside the source archive. Rather than solving that
# three times with three different mechanisms, we solve it once: this script
# produces ONE tarball -- upstream source + a pinned Cargo.lock + the vendored
# crates -- and all three lanes consume the same file by URL. That also means
# COPR and OBS build from byte-identical sources, which is a property
# worth having on its own.
#
# The crates are filtered to x86_64-linux with cargo-vendor-filterer, which
# drops the windows-* and apple crate trees we would otherwise ship and never
# compile (measured on redumper-gui 1.0.1: 546 MB -> 178 MB unpacked,
# 37 MB -> 15 MB compressed).
#
# UPSTREAM SHIPS NO Cargo.lock
# ----------------------------
# Redumper-GUI does not commit a lockfile, so a plain `cargo build` resolves the
# dependency tree afresh every time: "builds today" is no guarantee of "builds
# next month", and two builds of the same tag can differ. We therefore generate
# a lockfile here and freeze it INSIDE the tarball. The published tarball is the
# artifact of record: every lane, and every rebuild, uses that exact tree.
# (Asking upstream to commit a Cargo.lock is part of the packaging PR.)
#
# Needs network and a Rust toolchain; run it outside the command sandbox.
#
# Usage:
#   scripts/rust-vendor-tarball.sh redumper-gui 1.0.1
#   scripts/rust-vendor-tarball.sh redumper-gui 1.0.1 --publish
set -euo pipefail

TOOL=${1:?usage: rust-vendor-tarball.sh <tool> <version> [--publish]}
VERSION=${2:?usage: rust-vendor-tarball.sh <tool> <version> [--publish]}
PUBLISH=${3:-}

# Upstream coordinates per tool, plus the MSRV the lockfile must resolve for.
#
# MSRV = the LOWEST rustc among the targets this tool actually ships to. It is a
# floor, not a wish: upstream ships no Cargo.lock and declares no rust-version,
# so `cargo generate-lockfile` on a modern toolchain resolves to the newest
# semver-compatible crates -- several of which have since raised their own MSRV.
# Measured on redumper-gui 1.0.1: a lockfile generated with rustc 1.96 pulled in
# zip 8.6, time-core 0.1.9 and vello_* 0.0.9 (all needing 1.88), and the build
# then failed on an older toolchain. Injecting rust-version makes cargo's
# MSRV-aware resolver (default under edition 2024 / resolver 3) hold the line.
#
# For redumper-gui that floor is 1.92, and it is NOT ours to choose: eframe/egui
# 0.35 -- a direct dependency, pinned in upstream's Cargo.toml -- itself requires
# rustc 1.92. No resolver can go below a direct dependency's own MSRV.
#
# Which targets that leaves, re-measured 2026-07-13 in clean containers (an
# earlier note here claimed trixie-backports had no newer rustc -- that was
# WRONG, and it was wrong in a public upstream issue too; see #2 there):
#   Fedora 43+              1.96                       builds
#   EL 8 / 9 / 10           1.92                       builds, at EXACTLY the floor
#   Leap 16 / Tumbleweed    1.96                       builds
#   Debian 13 (trixie)      1.85, backports 1.94       builds, via backports only
#   Ubuntu 26.04            1.93                       builds
#   Debian 12 (bookworm)    1.63, no rustc in bpo      OUT
#   Ubuntu 22.04 / 24.04    1.75, rustc-1.91 at best   OUT
#
# Raise this only when the lowest SHIPPING target's rustc actually rises.
case "$TOOL" in
    redumper-gui) UPSTREAM_REPO="Deterous/Redumper-GUI"; TAG="v${VERSION}"; MSRV="1.92" ;;
    *) echo "unknown tool: $TOOL" >&2; exit 1 ;;
esac

PKG_REPO="gmipf/packaging-media-preservation"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

SRCDIR="${TOOL}-${VERSION}"
TARBALL="${TOOL}-${VERSION}-vendored.tar.xz"

command -v cargo-vendor-filterer >/dev/null || {
    echo "cargo-vendor-filterer is missing (dnf install cargo-vendor-filterer)" >&2
    exit 1
}

echo ":: fetching ${UPSTREAM_REPO} @ ${TAG}"
curl -fsSL "https://github.com/${UPSTREAM_REPO}/archive/refs/tags/${TAG}.tar.gz" \
    -o "${WORK}/upstream.tar.gz"

# Record what we started from, so anyone can verify this tarball is upstream's
# tag plus vendored crates and nothing else.
UPSTREAM_SHA=$(sha256sum "${WORK}/upstream.tar.gz" | cut -d' ' -f1)

mkdir -p "${WORK}/${SRCDIR}"
tar xzf "${WORK}/upstream.tar.gz" -C "${WORK}/${SRCDIR}" --strip-components=1

pushd "${WORK}/${SRCDIR}" >/dev/null

# Give cargo's MSRV-aware resolver a floor to aim at. Upstream declares no
# rust-version, so without this it resolves to the newest semver-compatible
# crates and the tree stops building on our lowest target (see the MSRV comment
# above). Injected only if upstream has not declared one itself -- the day they
# do, theirs wins and this becomes a no-op.
if ! grep -q '^rust-version' Cargo.toml; then
    echo ":: injecting rust-version = \"${MSRV}\" (upstream declares none)"
    sed -i "0,/^edition *=/s//rust-version = \"${MSRV}\"\nedition =/" Cargo.toml
    grep -q '^rust-version' Cargo.toml || { echo "rust-version injection failed" >&2; exit 1; }
fi

echo ":: pinning Cargo.lock (resolved for rustc ${MSRV})"
cargo generate-lockfile

echo ":: vendoring crates (filtered to x86_64-unknown-linux-gnu)"
cargo vendor-filterer --platform=x86_64-unknown-linux-gnu vendor >/dev/null

mkdir -p .cargo
cat > .cargo/config.toml <<'EOF'
[source.crates-io]
replace-with = "vendored-sources"

[source.vendored-sources]
directory = "vendor"
EOF

popd >/dev/null

echo ":: packing ${TARBALL}"
# Deterministic: same inputs -> byte-identical tarball, so anyone can rebuild
# this file and compare checksums. Without the pinning below, tar stamps every
# entry with the assembly-time wall clock and each run produces a different
# sha256 -- which quietly guts the whole point of publishing the vendored tree
# (nobody, including us, could verify the artifact is upstream + crates and
# nothing else). Measured 2026-07-13: two consecutive runs differed.
# Epoch = upstream's tag, not "now"; same reasoning as scripts/deb/assemble.sh.
PUBLISHED=$(gh api "repos/${UPSTREAM_REPO}/releases/tags/${TAG}" --jq .published_at)
EPOCH=$(date -u -d "$PUBLISHED" +%s)
echo ":: SOURCE_DATE_EPOCH=${EPOCH} (${PUBLISHED}, upstream release date of ${TAG})"
tar --sort=name --owner=0 --group=0 --numeric-owner \
    --mtime="@${EPOCH}" --format=gnu \
    -caf "${TARBALL}" -C "${WORK}" "${SRCDIR}"

cat <<EOF

  tarball        ${TARBALL}
  size           $(du -h "${TARBALL}" | cut -f1)
  sha256         $(sha256sum "${TARBALL}" | cut -d' ' -f1)
  upstream tag   ${TAG}  (${UPSTREAM_REPO})
  upstream sha256 ${UPSTREAM_SHA}

EOF

if [ "$PUBLISH" = "--publish" ]; then
    REL="${TOOL}-${VERSION}"
    echo ":: publishing as release asset ${REL} on ${PKG_REPO}"
    gh release view "$REL" --repo "$PKG_REPO" >/dev/null 2>&1 || \
        gh release create "$REL" --repo "$PKG_REPO" \
            --title "${TOOL} ${VERSION} (vendored source)" \
            --notes "Vendored source tarball for ${TOOL} ${VERSION}: upstream ${UPSTREAM_REPO} tag ${TAG}, plus a pinned Cargo.lock and its crates vendored (filtered to x86_64-linux).

This is a packaging artifact, not a release of the tool. It exists because no build root has network access -- not COPR's chroot and not OBS's -- so the crates must travel inside the source archive. Both lanes build from this one file.

Upstream tarball sha256: \`${UPSTREAM_SHA}\`"
    gh release upload "$REL" "${TARBALL}" --repo "$PKG_REPO" --clobber
    echo ":: done"
else
    echo "not published (pass --publish to upload it as a release asset)"
fi
