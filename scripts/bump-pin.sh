#!/bin/bash
#
# bump-pin.sh <redumper-mpf|redumper-rgui> <build>
#
# Advance a redumper CONSUMER PIN to the redumper build its consumer now bundles,
# in all three lanes at once. The pin has a FIXED package name and its Version is
# the build number (%global rdbuild drives Version and the Source tag), so this is
# a plain in-place version bump -- redumper-mpf 732 -> 733 -- that `dnf/zypper/apt
# upgrade` carries across installed machines. No new package, no orphan.
#
# Called by .github/workflows/watch-consumer-pins.yml. Split out as a script so it
# can be run and verified locally before it ever runs in CI (the whole point of
# the proof discipline: measure the mechanism, do not trust that it works).
#
# Every rewrite is verified; a silent sed no-op fails loudly.
set -euo pipefail

PIN=${1:?usage: bump-pin.sh <redumper-mpf|redumper-rgui> <build>}
NEW=${2:?usage: bump-pin.sh <pin> <build>}
case "$PIN" in redumper-mpf|redumper-rgui) ;; *) echo "unknown pin: $PIN" >&2; exit 2 ;; esac
[[ "$NEW" =~ ^[0-9]+$ ]] || { echo "build must be numeric: $NEW" >&2; exit 2; }

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$REPO"
FSPEC="fedora/$PIN/$PIN.spec"
[ -f "$FSPEC" ] || { echo "no spec: $FSPEC" >&2; exit 1; }

OLD=$(grep -oP '^%global rdbuild \K[0-9]+' "$FSPEC")
if [ "$OLD" = "$NEW" ]; then echo "$PIN already at b$NEW — nothing to do"; exit 0; fi
echo "bumping $PIN: b$OLD -> b$NEW"

MSG="Automated: consumer moved its bundled redumper to b${NEW}; the pin follows."

# ---- fedora: rdbuild drives Version + Source; reset Release, prepend changelog ----
sed -i "s/^%global rdbuild .*/%global rdbuild ${NEW}/" "$FSPEC"
grep -qx "%global rdbuild ${NEW}" "$FSPEC" || { echo "fedora rdbuild rewrite failed" >&2; exit 1; }
sed -i "s/^Release:.*/Release:        1%{?dist}/" "$FSPEC"
CL=$(mktemp)
{
  printf '* %s gmipf <gmipf64@gmail.com> - %s-1\n' "$(LC_ALL=C date -u +'%a %b %d %Y')" "$NEW"
  printf -- '- %s Release reset to 1.\n\n' "$MSG"
} > "$CL"
sed -i "/^%changelog/r $CL" "$FSPEC"; rm -f "$CL"

# ---- openSUSE: verified helper, sets %global rdbuild + marker (Version follows) ----
bash scripts/opensuse-bump.sh "$PIN" "$NEW" "b${NEW}" "$MSG" rdbuild="$NEW"

# ---- debian: new UNRELEASED stanza at <build>-1 ----
bash scripts/deb/bump-changelog.sh "ubuntu/$PIN" "$NEW" "$MSG"
# ...and its marker. Left out until 2026-07-19, which is why ubuntu/redumper-rgui
# still read b729 while the other two lanes were at b733. Nothing caught it: the
# opensuse/ and ubuntu/ markers are written by every bump path and read by none,
# and state nobody reads cannot go red -- it just drifts. status.sh now compares
# the three lanes against each other, which is what makes this line testable.
printf '%s\n' "b${NEW}" > "ubuntu/$PIN/.upstream-tag"

# ---- regenerate the openSUSE deb artifacts (the .dsc names the b<N> archive) ----
command -v rpmspec >/dev/null || { echo "rpmspec required" >&2; exit 1; }
bash scripts/obs/gen-deb.sh "$PIN"

echo "bumped $PIN to b$NEW in fedora/opensuse/ubuntu."
