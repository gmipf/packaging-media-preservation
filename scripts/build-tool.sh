#!/usr/bin/env bash
#
# build-tool.sh — manually trigger a single tool's COPR build, safely.
#
# Why this exists
# ---------------
# Our COPR builds use `update_release: false` (see .packit.yaml), so the
# published NEVRA is EXACTLY what the spec says — a clean, bare-N Release with
# no build suffix (e.g. redumper-724-2, mpf-3.7.1~<snap>-5). That keeps our
# version convention intact ([[rpm-version-convention]]).
#
# The price of a clean NEVRA: a manual rebuild whose spec NEVRA hasn't changed
# would republish the SAME NEVRA with a fresh checksum and break `dnf` clients
# ([[dnf-cache-rebuild]]). The GitHub watchers never hit this (they bump
# Version / reset Release on every real upstream change). MANUAL builds are the
# only gap — so this script is the one supported way to fire one by hand.
#
# What it guarantees
# ------------------
#  * Same-NEVRA is impossible: before triggering it compares the spec NEVRA
#    against the latest already built in COPR and, if ours wouldn't be strictly
#    newer, AUTO-BUMPS the bare-N Release (e.g. -5 -> -6) and commits that.
#  * Only the requested tool rebuilds: the build is routed through the per-tool
#    trigger branch build-<tool> (branch-scoping, [[packit-yaml-cross-trigger]]).
#
# Usage
# -----
#   scripts/build-tool.sh <redumper|mpf|dic|aaru>
#
# Run it on a clean `main` (commit your spec edits first). It will, if needed,
# add a Release-bump commit, push main (which builds nothing by design), then
# recreate build-<tool> and force-push it to fire the build.

set -euo pipefail

OWNER=gmipf
PROJECT=media-preservation
API=https://copr.fedorainfracloud.org/api_3

TOOL=${1:-}
case "$TOOL" in
  redumper) PKG=redumper;          SPEC=fedora/redumper/redumper.spec;                  BR=build-redumper ;;
  mpf)      PKG=mpf;               SPEC=fedora/mpf/mpf.spec;                             BR=build-mpf ;;
  dic)      PKG=discimagecreator;  SPEC=fedora/discimagecreator/discimagecreator.spec;  BR=build-dic ;;
  aaru)     PKG=aaru;              SPEC=fedora/aaru/aaru.spec;                           BR=build-aaru ;;
  *) echo "usage: $0 <redumper|mpf|dic|aaru>" >&2; exit 2 ;;
esac

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "error: working tree is dirty — commit or stash your changes first." >&2
  exit 1
fi

START_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# --- spec NEVRA (clean, as it will be published) -----------------------------
SPEC_V=$(rpmspec -q --srpm --qf '%{version}\n' "$SPEC" | head -1)
SPEC_R_FULL=$(rpmspec -q --srpm --qf '%{release}\n' "$SPEC" | head -1)
SPEC_RBASE=${SPEC_R_FULL%%.*}   # bare-N, drop %{?dist} (.fcNN)

# --- latest succeeded NEVRA already in COPR ----------------------------------
COPR_VR=$(curl -sg "$API/package?ownername=$OWNER&projectname=$PROJECT&packagename=$PKG&with_latest_succeeded_build=True" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);b=(d.get('builds') or {}).get('latest_succeeded') or {};print(((b.get('source_package') or {}).get('version')) or '')")

echo "spec : $SPEC_V-$SPEC_RBASE"
echo "copr : ${COPR_VR:-<none>}"

# --- decide: ok / bump:<N> / abort -------------------------------------------
if [ -z "$COPR_VR" ]; then
  ACTION=ok   # no prior build, nothing to collide with
else
  COPR_V=${COPR_VR%-*}
  COPR_R=${COPR_VR##*-}
  ACTION=$(python3 - "$SPEC_V" "$SPEC_RBASE" "$COPR_V" "$COPR_R" <<'PY'
import sys, rpm
_, sv, sr, cv, cr = sys.argv
cmp = rpm.labelCompare(("0", sv, sr), ("0", cv, cr))
if cmp > 0:
    print("ok")                         # spec already strictly newer
elif sv == cv:
    print("bump:%d" % (int(cr.split(".")[0]) + 1))   # same version, lift Release
else:
    print("abort")                      # spec version older — needs a human
PY
)
fi

case "$ACTION" in
  ok)
    echo "-> spec NEVRA is already newer than COPR; building as-is." ;;
  bump:*)
    N=${ACTION#bump:}
    echo "-> would collide with COPR; auto-bumping Release to $N."
    sed -i "s/^Release:.*/Release:        ${N}%{?dist}/" "$SPEC"
    git add "$SPEC"
    git commit -q -m "chore: bump $PKG Release to $N (keep clean NEVRA, supersede prior build)"
    SPEC_RBASE=$N ;;
  abort)
    echo "error: spec version ($SPEC_V) is older than COPR's ($COPR_V) — refusing." >&2
    echo "       bump the Version in $SPEC and re-run." >&2
    exit 1 ;;
esac

# --- canonical push (main builds nothing) ------------------------------------
git push origin "HEAD:main"

# --- trigger branch = main's tree + a distinct landing README (cosmetic), ----
#     force-pushed so ONLY this tool's COPR job fires.
git checkout -q -B trigger-build "$START_BRANCH"
case "$TOOL" in
  redumper) printf '# build-redumper — redumper (Fedora/COPR trigger branch)\n\nAuto-managed **trigger branch** for the `redumper` package: a push here\nfires the redumper COPR build via Packit, nothing else rebuilds. Canonical\nsource is `main` (do not edit here). Packaging: `fedora/redumper/`.\n' ;;
  mpf)      printf '# build-mpf — MPF (Fedora/COPR trigger branch)\n\nAuto-managed **trigger branch** for the `mpf` package: a push here fires\nthe mpf COPR build via Packit, nothing else rebuilds. Canonical source is\n`main` (do not edit here). Packaging: `fedora/mpf/`.\n' ;;
  dic)      printf '# build-dic — DiscImageCreator (Fedora/COPR trigger branch)\n\nAuto-managed **trigger branch** for the `discimagecreator` package: a push\nhere fires its COPR build via Packit, nothing else rebuilds. Canonical\nsource is `main` (do not edit here). Packaging: `fedora/discimagecreator/`.\n' ;;
  aaru)     printf '# build-aaru — Aaru (Fedora/COPR trigger branch)\n\nAuto-managed **trigger branch** for the `aaru` package: a push here fires\nthe aaru COPR build via Packit, nothing else rebuilds. Canonical source is\n`main` (do not edit here). Packaging: `fedora/aaru/`.\n' ;;
esac > README.md
git add README.md
git commit -q -m "trigger: $PKG build ($SPEC_V-$SPEC_RBASE)"
git push -f origin "trigger-build:$BR"

git checkout -q "$START_BRANCH"
git branch -D trigger-build >/dev/null 2>&1 || true

echo "done: $PKG $SPEC_V-$SPEC_RBASE -> $BR (COPR build triggered)."
