#!/bin/bash
#
# bump-pin.sh <redumper-mpf|redumper-rgui|aaru5> <version>
#
# Advance a CONSUMER PIN to the upstream revision its consumer now bundles, in all
# three lanes at once. Every pin has a FIXED package name and a moving version
# driven by one macro, so this is a plain in-place bump -- redumper-mpf 732 -> 733,
# aaru5 5.4.2 -> 5.5.0 -- that `dnf/zypper/apt upgrade` carries across installed
# machines. No new package, no orphan.
#
# Called by .github/workflows/watch-consumer-pins.yml and watch-redumper-gui.yml.
# Split out as a script so it can be run and verified locally before it ever runs
# in CI -- measure the mechanism, do not trust that it works.
#
# aaru5 was HAND-BUMPED until 2026-07-19, on the stated grounds that it is "a
# NativeAOT tree with a static manpage, not a zip". Both halves were wrong: its
# manpage is generated at build time from aaru5-manpage.sh, exactly like the
# rolling aaru package, and the rolling one is a NativeAOT tree too and is bumped
# automatically. What actually differed was one macro name and one line -- `Version:`
# repeated the literal 5.4.2 instead of following %{aaruver}. A reason written down
# once and never re-checked kept a package on manual maintenance for weeks.
#
# Every rewrite is verified; a silent sed no-op fails loudly.
set -euo pipefail

PIN=${1:?usage: bump-pin.sh <redumper-mpf|redumper-rgui|aaru5> <version>}
NEW=${2:?usage: bump-pin.sh <pin> <version>}

# Per pin: which macro drives the version, what an acceptable value looks like,
# how the upstream tag is spelled, and what to say in the changelog.
case "$PIN" in
    redumper-mpf|redumper-rgui)
        MACRO=rdbuild
        PATTERN='^[0-9]+$'
        TAG="b${NEW}"
        WHAT="redumper build b${NEW}" ;;
    aaru5)
        MACRO=aaruver
        PATTERN='^[0-9]+\.[0-9]+\.[0-9]+$'
        TAG="v${NEW}"
        WHAT="Aaru release ${NEW}" ;;
    *)  echo "unknown pin: $PIN" >&2; exit 2 ;;
esac
[[ "$NEW" =~ $PATTERN ]] || { echo "version '$NEW' does not match $PATTERN for $PIN" >&2; exit 2; }

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$REPO"
FSPEC="fedora/$PIN/$PIN.spec"
[ -f "$FSPEC" ] || { echo "no spec: $FSPEC" >&2; exit 1; }

OLD=$(grep -oP "^%global[[:space:]]+${MACRO}[[:space:]]+\K\S+" "$FSPEC")
[ -n "$OLD" ] || { echo "$FSPEC has no '%global $MACRO' line" >&2; exit 1; }
if [ "$OLD" = "$NEW" ]; then echo "$PIN already at $NEW — nothing to do"; exit 0; fi
echo "bumping $PIN: $OLD -> $NEW"

MSG="Automated: consumer moved its bundled ${WHAT}; the pin follows."

# ---- fedora: the macro drives Version + Source; reset Release, prepend changelog ----
# Rewrite only the VALUE, keeping the column alignment the specs use. Same shape as
# opensuse-bump.sh -- replacing the whole line would work and would silently
# reformat every spec it touched.
sed -i -E "s|^(%global[[:space:]]+${MACRO}[[:space:]]+).*|\1${NEW}|" "$FSPEC"
grep -Eq "^%global[[:space:]]+${MACRO}[[:space:]]+${NEW}$" "$FSPEC" \
    || { echo "fedora $MACRO rewrite did not land" >&2; exit 1; }
sed -i "s/^Release:.*/Release:        1%{?dist}/" "$FSPEC"
CL=$(mktemp)
{
  printf '* %s gmipf <gmipf64@gmail.com> - %s-1\n' "$(LC_ALL=C date -u +'%a %b %d %Y')" "$NEW"
  printf -- '- %s Release reset to 1.\n\n' "$MSG"
} > "$CL"
sed -i "/^%changelog/r $CL" "$FSPEC"; rm -f "$CL"

# ---- openSUSE: verified helper, sets the macro + marker (Version follows) ----
bash scripts/opensuse-bump.sh "$PIN" "$NEW" "$TAG" "$MSG" "${MACRO}=${NEW}"

# ---- debian: new UNRELEASED stanza ----
bash scripts/deb/bump-changelog.sh "ubuntu/$PIN" "$NEW" "$MSG"
# ...and its marker. Left out until 2026-07-19, which is why ubuntu/redumper-rgui
# still read b729 while the other two lanes were at b733. Nothing caught it: the
# opensuse/ and ubuntu/ markers are written by every bump path and read by none,
# and state nobody reads cannot go red -- it just drifts. status.sh now compares
# the three lanes against each other, which is what makes this line testable.
printf '%s\n' "$TAG" > "ubuntu/$PIN/.upstream-tag"

# ---- regenerate the openSUSE deb artifacts (the .dsc names the upstream archive) ----
command -v rpmspec >/dev/null || { echo "rpmspec required" >&2; exit 1; }
bash scripts/obs/gen-deb.sh "$PIN"

echo "bumped $PIN to $NEW in fedora/opensuse/ubuntu."
