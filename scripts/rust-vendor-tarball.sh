#!/usr/bin/env bash
# Build the vendored source tarball for a Rust tool and (optionally) publish it
# as a release asset on the packaging repo (see the publish block at the bottom
# for why there, and not on a branch of the tool's fork as it used to be).
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
# crates -- and both lanes consume the same file by URL. That also means
# COPR and OBS build from byte-identical sources, which is a property
# worth having on its own.
#
# The crates are filtered to x86_64-linux with cargo-vendor-filterer, which
# drops the windows-* and apple crate trees we would otherwise ship and never
# compile (measured on redumper-gui 1.0.1: 546 MB -> 178 MB unpacked,
# 37 MB -> 15 MB compressed).
#
# THE LOCKFILE
# ------------
# Through 1.0.1 Redumper-GUI committed no lockfile, so a plain `cargo build`
# re-resolved the dependency tree every time: "builds today" was no guarantee of
# "builds next month", and two builds of the same tag could differ. We generated
# one here and froze it inside the tarball.
#
# As of 1.0.2 upstream commits a Cargo.lock -- asked for in the packaging PR and
# granted, along with rust-version and license in Cargo.toml. So we now KEEP
# upstream's lockfile and only generate one when there is none. Either way the
# published tarball stays the artifact of record: every lane, and every rebuild,
# uses that exact tree.
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

# Upstream committed a Cargo.lock as of 1.0.2 -- one of the three things the
# packaging PR asked for, and granted (the others: rust-version and license in
# Cargo.toml). That lockfile IS the pin, and it is upstream's, which is strictly
# better than ours: regenerating it here would throw away the determinism we just
# gained and re-resolve against whatever cargo happens to be on this machine.
# So keep it when it exists, and verify it is actually in sync -- `--locked`
# fails rather than silently updating, which is the whole point.
# name/version of every locked package, one per line. CR is stripped because
# upstream's 1.0.2 lockfile is committed with CRLF endings and cargo rewrites it
# with LF -- compare that raw and EVERY line reads as changed, which is a
# spectacular way to hide the one line that really moved.
lockpairs() { tr -d '\r' < Cargo.lock | awk '/^name = /{n=$3} /^version = /{print n, $3}' | sort; }

if [ -f Cargo.lock ]; then
    # Upstream's lockfile is exactly the pin we want. But the 1.0.2 tag ships one
    # that still names the package itself as 1.0.1 -- generated before the version
    # bump and never regenerated. `--locked` therefore refuses outright, while
    # simply dropping it would let cargo re-resolve all dependencies against
    # whatever cargo happens to sit on this machine.
    #
    # So allow cargo its MINIMAL fixup, then prove that nothing but the root
    # package's own version moved. A dependency shifting here is a real finding
    # and must stop the run -- that is the whole value of upstream having a
    # lockfile at all.
    echo ":: upstream ships Cargo.lock -- keeping its pins, allowing only a self-version fixup"
    lockpairs > "${WORK}/lock.before"
    cargo metadata --format-version 1 >/dev/null
    lockpairs > "${WORK}/lock.after"
    MOVED=$(comm -3 "${WORK}/lock.before" "${WORK}/lock.after" | tr -d '\t ' | grep -v "^\"${TOOL}\"" || true)
    if [ -n "$MOVED" ]; then
        echo "cargo moved dependency pins, not just ${TOOL}'s own version:" >&2
        comm -3 "${WORK}/lock.before" "${WORK}/lock.after" >&2
        exit 1
    fi
    echo ":: verified -- only ${TOOL}'s own version entry changed, every dependency pin held"
else
    echo ":: no upstream Cargo.lock -- generating one (resolved for rustc ${MSRV})"
    cargo generate-lockfile
fi

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
    # Host the tarball as a RELEASE ASSET on the packaging repo itself.
    #
    # It used to live on an orphan `vendored` branch of our FORK of the tool. That
    # cost a cross-repo write credential (the built-in GITHUB_TOKEN reaches only
    # the repo its workflow runs in) and carried two quiet defects:
    #
    #   * raw.githubusercontent serves branch URLs through a ~5 minute CDN cache.
    #     Re-publishing the SAME version with different bytes therefore hands the
    #     build farms the OLD blob under the new file -- a silently wrong build,
    #     not an error. Exactly what a re-vendor of an already-shipped version does.
    #   * the branch grew ~15 MB per release forever; xz does not delta-compress.
    #
    # Release assets fix all three: the built-in token writes them in its own repo
    # (nothing to install, nothing to rotate, nothing that can expire), GitHub
    # documents no bandwidth limit on them, and they live OUTSIDE git, so this repo
    # stays a recipe and never becomes the payload.
    #
    # Safe here specifically, and this was measured rather than assumed: no
    # workflow in this repo triggers on `release`, and obs-trigger.yml's `push` is
    # scoped to branches:[main] -- a tag is not a branch. The 2026-07-13 incident,
    # where one tag made every package lacking get-current-version build as the
    # TAG's version, is closed: all eight pin their version from the spec now.
    # The lesson recorded then as "no GitHub releases" was broader than its
    # evidence; the real rule is "no untracked version inference".
    RELTAG="${TOOL}-vendored-${VERSION}"
    RAW="https://github.com/${PKG_REPO}/releases/download/${RELTAG}/${TARBALL}"
    echo ":: publishing ${TARBALL} as a release asset on ${PKG_REPO} (tag ${RELTAG})"
    if gh release view "$RELTAG" --repo "$PKG_REPO" >/dev/null 2>&1; then
        gh release upload "$RELTAG" "$TARBALL" --repo "$PKG_REPO" --clobber
    else
        gh release create "$RELTAG" "$TARBALL" --repo "$PKG_REPO" \
            --title "${TOOL} ${VERSION} — vendored crates" \
            --notes "Build input, not a download for users. Upstream ${UPSTREAM_REPO} at ${TAG} plus its vendored Cargo dependencies, so COPR and OBS can build offline from byte-identical sources. Consumed by Source0 in fedora/${TOOL}/ and opensuse/${TOOL}/. Rebuild and compare with: scripts/rust-vendor-tarball.sh ${TOOL} ${VERSION}"
    fi
    echo ":: Source0 -> ${RAW}"
else
    echo "not published (pass --publish to upload it as a release asset)"
fi
