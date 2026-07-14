#!/usr/bin/env bash
#
# status.sh — one look at all three delivery lanes, plus the two things that go
# wrong QUIETLY.
#
#   COPR (Fedora/EPEL)  -> copr-cli
#   PPA  (Ubuntu)       -> Launchpad's REST API, read ANONYMOUSLY with curl+jq.
#                          There is no Launchpad CLI, and we do not want one:
#                          the API needs no token for public data, so the PPA's
#                          GPG signing key never has to come anywhere near this.
#   OBS  (openSUSE)     -> osc results
#
# Why this script exists (2026-07-13): redumper sat at 732 on noble and resolute
# and at 731 on jammy for a day, and nothing said so. Launchpad's FTP had
# answered `550 internal server error` three times during the upload; the job
# went red exactly as it should -- and nobody looked at it. A tool can therefore
# fall behind on ONE series and every lane still reports "success". So this
# script does not just print state, it names the silent failures:
#
#   * VERSION DRIFT — one tool, different versions across the PPA series.
#   * RED RUNS      — failed workflow runs nobody acknowledged.
#   * BUNDLE DRIFT  — MPF bundles a specific redumper and Aaru build, and our mpf
#                     package deliberately drops those bundled binaries and points
#                     MPF's config at the system packages instead. If upstream MPF
#                     moves to a different bundled build, an MPF dump silently runs
#                     a dumper version its own upstream never tested. Nothing in
#                     either project says so: MPF has no version check at all, it
#                     only writes whatever version it finds into the submission.
#                     (This is not hypothetical -- it is why redumper726 was never
#                     shipped: it was drafted when MPF bundled b726, and by the
#                     time it would have gone out MPF had moved to b732, which is
#                     exactly what our rolling redumper already carries. Shipping
#                     the pin would have handed users a dumper OLDER than the one
#                     MPF itself ships.)
#
# Usage: scripts/status.sh
# Needs network (copr, launchpad, obs) -- run it outside the command sandbox.
set -uo pipefail

LP_OWNER=${LP_OWNER:-dreunion61}
LP_PPA=${LP_PPA:-media-preservation}
COPR_PROJECT=${COPR_PROJECT:-gmipf/media-preservation}
OBS_PROJECT=${OBS_PROJECT:-home:gmipf:media-preservation}
LP_API="https://api.launchpad.net/1.0/~${LP_OWNER}/+archive/ubuntu/${LP_PPA}"

hr() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

hr "COPR — ${COPR_PROJECT}"
copr-cli monitor "$COPR_PROJECT" \
    --output-format text-row --fields name,chroot,state,build_id 2>/dev/null \
  | awk -F'\t' '{printf "  %-16s %-22s %s\n", $1, $2, $3}' \
  | sort

hr "PPA — ppa:${LP_OWNER}/${LP_PPA}"
# Superseded/Deleted/Obsolete are the archive's history, not its current state.
PPA_JSON=$(curl -fsSL "${LP_API}?ws.op=getPublishedSources") || {
    echo "  (Launchpad nicht erreichbar)"; PPA_JSON='{"entries":[]}'; }

echo "$PPA_JSON" | jq -r '
    .entries[]
    | select(.status | IN("Published","Pending"))
    | "  \(.status)\t\(.source_package_name)\t\(.source_package_version)\t\(.distro_series_link|split("/")|last)"' \
  | sort -k2

# --- silent failure #1: one tool, different versions across series ------------
# The upstream version is everything before the last "-": 732-1~jammy1 -> 732,
# 3.8.3~2026...-2~noble1 -> 3.8.3~2026... The ~series suffix is expected to
# differ; the upstream version is NOT.
DRIFT=$(echo "$PPA_JSON" | jq -r '
    [ .entries[]
      | select(.status == "Published")
      | { tool: .source_package_name,
          ver:  (.source_package_version | sub("-[^-]*$"; "")),
          ser:  (.distro_series_link | split("/") | last) } ]
    | group_by(.tool)[]
    | select((map(.ver) | unique | length) > 1)
    | "  \(.[0].tool): " + (map("\(.ser)=\(.ver)") | join("  "))')

if [ -n "$DRIFT" ]; then
    printf '\n  \033[31mVERSIONS-DRIFT — eine Serie haengt hinterher:\033[0m\n%s\n' "$DRIFT"
    echo "  -> nachladen: gh workflow run ppa-upload.yml -f tool=<tool> -f series=<serie>"
else
    printf '\n  kein Versions-Drift (alle Serien auf derselben Upstream-Version)\n'
fi

hr "OBS — ${OBS_PROJECT}"
osc results "$OBS_PROJECT" 2>&1 | sed -n '1,12p' | sed 's/^/  /'

# --- silent failure #3: MPF's bundled backends drift away from ours ------------
# Our mpf package deletes MPF's bundled Programs/ folder and points its config at
# the system dumpers. That is only honest while the system dumper IS the build MPF
# bundles. Read what MPF bundles TODAY from its own publish script -- never from a
# note someone wrote once.
#
# TWO of the three backends are checked, and that is deliberate:
#
#   redumper  checked. redumper moves fast, and a frontend CAN be coupled to a
#             specific build -- redumper-gui's upstream says so in as many words.
#   Aaru      checked. MPF supports only the latest STABLE Aaru; the rolling `aaru`
#             is a 6.0 alpha with a different command line and does not run in MPF
#             at all. That is why the pinned `aaru5` package exists.
#   DIC       NOT checked, ON PURPOSE. DiscImageCreator is never pinned for a
#             frontend: its command-line surface is effectively frozen -- what still
#             lands upstream is bugfixes and new disc types, not features that could
#             break a frontend. So we ship it as a rolling snapshot and are allowed
#             to be AHEAD of the build MPF bundles. Do not "fix" this by adding DIC
#             to the comparison; its absence is the answer, not an oversight.
#
# The general rule: a pin is justified by what UPSTREAM says, not by what a consumer
# happens to bundle. MPF says nothing and has no version check of any kind -- so it
# gets this watchdog instead of a pinned package.
hr "MPF-Bundle vs. unsere Pins"
REPO=$(cd "$(dirname "$0")/.." && pwd)
NIX=$(curl -fsSL https://raw.githubusercontent.com/SabreTools/MPF/master/publish-nix.sh 2>/dev/null)
if [ -z "$NIX" ]; then
    echo "  publish-nix.sh nicht erreichbar — Bundle-Drift UNGEPRUEFT"
else
    # What MPF bundles today.
    MPF_RD=$(printf '%s' "$NIX" | grep -oE 'redumper/releases/download/b[0-9]+' | head -1 | grep -oE '[0-9]+$')
    MPF_AA=$(printf '%s' "$NIX" | grep -oE 'Aaru/releases/download/v[0-9.]+'    | head -1 | sed 's/.*v//')
    # What our mpf package actually points at (metadata AND the seeded config --
    # both have to agree, or the package recommends one dumper and configures
    # another).
    PTR_META=$(grep -oE '^Recommends: +redumper[0-9]*' "$REPO/fedora/mpf/mpf.spec" | head -1 | grep -oE 'redumper[0-9]*')
    PTR_SEED=$(grep -oE '^red_p=redumper[0-9]*'        "$REPO/fedora/mpf/mpf.spec" | head -1 | sed 's/^red_p=//')
    OUR_AA=$(grep -m1 '^Version:' "$REPO/fedora/aaru5/aaru5.spec" | awk '{print $2}')

    ok()   { printf '  \033[32mok\033[0m    %s\n' "$1"; }
    bad()  { printf '  \033[31mFEHLER\033[0m %s\n' "$1"; }

    # 1. MPF must point at the PIN that carries the build MPF bundles -- never at
    #    the rolling `redumper`, not even while the rolling package happens to
    #    carry that same build.
    WANT="redumper${MPF_RD}"
    if [ "$PTR_META" = "$WANT" ] && [ "$PTR_SEED" = "$WANT" ]; then
        ok "MPF buendelt b${MPF_RD} und zeigt auf ${WANT} (Metadaten + Config-Seed)"
    else
        bad "MPF buendelt b${MPF_RD}, zeigt aber auf Metadaten=${PTR_META:-?} / Seed=${PTR_SEED:-?}"
        echo "     -> ${WANT} erzeugen (fedora/ ubuntu/ opensuse/) und MPF darauf umbiegen."
        echo "        NIEMALS auf das rollende 'redumper' zeigen: es bewegt sich, MPF hat"
        echo "        KEINE Versionspruefung und wuerde still mit einer ungetesteten Build dumpen."
    fi

    # 2. The recipe for that pin has to exist in every lane.
    MISS=""
    for lane in fedora ubuntu opensuse; do
        [ -d "$REPO/$lane/$WANT" ] || MISS="$MISS $lane"
    done
    if [ -z "$MISS" ]; then
        ok "Rezept ${WANT} in allen drei Lanes vorhanden"
    else
        bad "Rezept ${WANT} FEHLT in:${MISS}"
    fi

    # 3. Aaru: MPF runs only the latest stable, which is what aaru5 carries.
    if [ "$MPF_AA" = "$OUR_AA" ]; then
        ok "MPF buendelt Aaru ${MPF_AA} und aaru5 liefert ${OUR_AA}"
    else
        bad "MPF buendelt Aaru ${MPF_AA:-?}, aaru5 liefert ${OUR_AA:-?}"
    fi

    # 4. ORPHANED PINS. A redumper<N> nobody points at any more keeps building and
    #    keeps being published in all three lanes, forever, because nothing ever
    #    says so. It only becomes an orphan when a CONSUMER moves -- which is
    #    exactly the moment nobody is looking at the pin.
    #
    #    ⚠️ Asked via `rpmspec`, NOT via grep. The specs write their dependency as
    #    `Requires: redumper%{rdpin}` -- a MACRO. A grep for the literal string
    #    finds nothing and cheerfully reports redumper729 as an orphan, i.e. it
    #    tells you to delete a package that redumper-gui hard-depends on. Measured:
    #    the first version of this check did exactly that. Let rpm expand the spec.
    USED=$(
        for s in "$REPO"/fedora/*/[a-z]*.spec; do
            rpmspec -q --requires   "$s" 2>/dev/null
            rpmspec -q --recommends "$s" 2>/dev/null
        done
        # The Debian lane has no macros, so plain text is honest there.
        grep -hoE 'redumper[0-9]+' "$REPO"/ubuntu/*/debian/control 2>/dev/null
    )
    for dir in "$REPO"/fedora/redumper[0-9]*/; do
        [ -d "$dir" ] || continue
        pin=$(basename "$dir")
        if printf '%s\n' "$USED" | grep -qx "$pin"; then
            ok "${pin} wird benutzt"
        else
            bad "${pin} ist ein WAISENPAKET — kein Konsument zeigt mehr darauf"
            echo "     -> Rezept entfernen + 'copr-cli delete-package ${pin}' + aus PPA/OBS nehmen."
            echo "        Sonst baut und publiziert es fuer immer weiter, ohne dass es jemand braucht."
        fi
    done
fi

# --- silent failure #2: red runs nobody looked at -----------------------------
# Only a failure that no later green run of the SAME workflow has superseded is
# worth showing. Listing every failure ever means a long-fixed one stays red for
# good, and a permanent red is one you learn to look past -- which is the exact
# blindness this script exists to prevent. Superseded ones are counted, not
# swallowed: a filter that hides its own work is the same bug wearing green.
hr "Workflow-Laeufe (letzte 40)"
RUNS=$(gh run list --limit 40 \
        --json workflowName,conclusion,createdAt,databaseId 2>/dev/null)
RED=$(jq -r '[.[] | select(.conclusion == "success" or .conclusion == "failure")]
             | group_by(.workflowName)
             | map(sort_by(.createdAt) | last)
             | .[] | select(.conclusion == "failure")
             | "  \(.createdAt[0:16])  \(.workflowName)  (run \(.databaseId))"' <<<"$RUNS")
HEALED=$(jq -r '[.[] | select(.conclusion == "failure")] | length' <<<"$RUNS")
if [ -n "$RED" ]; then
    printf '\033[31m%s\033[0m\n' "$RED"
    echo "  -> Grund lesen: gh run view <id> --log-failed"
else
    echo "  keine offenen (letzter Lauf jedes Workflows ist gruen)"
fi
if [ "${HEALED:-0}" -gt 0 ]; then
    echo "  (${HEALED} rote Laeufe im Fenster, seither von einem gruenen Lauf abgeloest)"
fi

# --- silent failure #4: the Debian lane's generated files drift apart ----------
# Each Debian-delivered tool carries THREE generated files (opensuse/<tool>/):
# the .dsc, debian.tar.gz and the deb block of _service. They are generated from
# ONE source -- ubuntu/<tool>/debian/ -- and nothing forces them to stay in step.
#
# Drift here does not fail the build, it CORRUPTS it quietly:
#
#   * debtransform takes the version from the .dsc, and if debian/changelog says
#     something else it silently REWRITES the changelog to match (measured). A
#     stale .dsc therefore ships the wrong version under a green build.
#   * _service names the .orig tarball by version in its Launchpad URL. Stale ->
#     OBS keeps building the previous upstream payload, also green.
#   * debian.tar.gz is a binary blob. Edit debian/rules and forget to regenerate,
#     and OBS builds the OLD rules. Nothing anywhere says so.
#
# So compare against the recipe, and for the blob regenerate it and compare BYTES
# (gen-deb.sh is deterministic precisely so this check can exist).
hr "Debian-Lane — generierte Dateien vs. Rezept"
DEB_DRIFT=0
for dsc in "$REPO"/opensuse/*/*.dsc; do
    tool=$(basename "$(dirname "$dsc")")
    cl="$REPO/ubuntu/$tool/debian/changelog"
    [ -f "$cl" ] || { echo "  $tool: .dsc ohne Rezept in ubuntu/ -- Waise?"; DEB_DRIFT=1; continue; }

    want=$(dpkg-parsechangelog -l "$cl" -SVersion)
    have=$(sed -n 's/^Version: //p' "$dsc")
    upst=${want%-*}

    [ "$want" = "$have" ] || {
        printf '  \033[31m%-18s .dsc sagt %s, changelog sagt %s\033[0m\n' "$tool" "$have" "$want"
        DEB_DRIFT=1; }

    grep -q "${tool}_${upst}\.orig\.tar\.xz" "$REPO/opensuse/$tool/_service" || {
        printf '  \033[31m%-18s _service zeigt nicht auf den Orig von %s\033[0m\n' "$tool" "$upst"
        DEB_DRIFT=1; }

    tmp=$(mktemp); trap 'rm -f "$tmp"' RETURN
    tar -C "$REPO/ubuntu/$tool" --sort=name --owner=0 --group=0 --numeric-owner \
        --mtime=@0 --format=gnu --exclude=debian/changelog -cf - debian \
      | gzip -n9 > "$tmp"
    cmp -s "$tmp" "$REPO/opensuse/$tool/debian.tar.gz" || {
        printf '  \033[31m%-18s debian.tar.gz VERALTET -- scripts/obs/gen-deb.sh %s\033[0m\n' "$tool" "$tool"
        DEB_DRIFT=1; }
    rm -f "$tmp"
done
[ "$DEB_DRIFT" = 0 ] && echo "  alle .dsc / debian.tar.gz / _service passen zum Rezept"
