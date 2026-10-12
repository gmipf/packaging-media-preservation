#!/bin/bash
#
# dreamdump-precheck.sh [spec]          (default: fedora/dreamdump/dreamdump.spec)
#
# Fetch exactly the files the dreamdump spec names and run the build's own
# guards on them: provenance for BOTH binaries, the no-capability opcode check,
# and the manpage generator.
#
# Every build runs these again (fedora/dreamdump/dreamdump-build.sh), so this is
# not a second line of defence -- it is the same check moved to where a failure
# is HEARD. watch-consumer-pins.yml runs it right after bumping the version and
# before committing: a bad upstream release (re-uploaded asset, a new SCSI
# opcode, an option the manpage table does not know) then fails that workflow,
# whose exit code is the one channel that reaches a human, instead of a COPR or
# OBS build log nobody opens. Nothing is pushed when it fails.
#
# The URLs come out of the spec (rpmspec -P), never written down a second time.
set -euo pipefail

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
SPEC=${1:-$REPO/fedora/dreamdump/dreamdump.spec}
HELPER=$REPO/fedora/dreamdump/dreamdump-build.sh

VERSION=$(rpmspec -q --queryformat '%{version}\n' "$SPEC" 2>/dev/null | head -1)
[ -n "$VERSION" ] || { echo "cannot read Version from $SPEC" >&2; exit 1; }

W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT

# Source0 = source tarball, Source1/Source2 = binaries; only remote ones.
urls=$(rpmspec -P "$SPEC" 2>/dev/null | sed -n 's/^Source[0-9]*:[[:space:]]*//p' | grep -E '^https?://')
[ -n "$urls" ] || { echo "no remote Source: URLs in $SPEC" >&2; exit 1; }
tarball="" bins=()
while read -r url; do
    case $url in *'#/'*) name=${url##*#/}; url=${url%%#*} ;; *) name=${url##*/} ;; esac
    curl -fsSL --retry 3 -o "$W/$name" "$url" || { echo "download failed: $url" >&2; exit 1; }
    case $name in
        *.tar.gz) tarball=$W/$name ;;
        *)        bins+=("$W/$name") ;;
    esac
    echo "fetched $name"
done <<< "$urls"
[ -n "$tarball" ] || { echo "no source tarball among the spec's Sources" >&2; exit 1; }
[ "${#bins[@]}" -ge 1 ] || { echo "no binary among the spec's Sources" >&2; exit 1; }

mkdir "$W/src"
tar -xzf "$tarball" -C "$W/src" --strip-components=1

for b in "${bins[@]}"; do
    sh "$HELPER" verify "$W/src" "$tarball" "$b"
done
sh "$HELPER" manpage "$W/src" "$VERSION" > "$W/dreamdump.1"
[ -s "$W/dreamdump.1" ] || { echo "manpage came out empty" >&2; exit 1; }
echo "dreamdump $VERSION: provenance, opcodes and manpage all pass (${#bins[@]} binaries)"
