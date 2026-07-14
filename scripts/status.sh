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
hr "MPF-Bundle vs. unsere Pakete"
NIX=$(curl -fsSL https://raw.githubusercontent.com/SabreTools/MPF/master/publish-nix.sh 2>/dev/null)
if [ -z "$NIX" ]; then
    echo "  publish-nix.sh nicht erreichbar — Bundle-Drift UNGEPRUEFT"
else
    MPF_RD=$(printf '%s' "$NIX" | grep -oE 'redumper/releases/download/b[0-9]+' | head -1 | grep -oE '[0-9]+$')
    MPF_AA=$(printf '%s' "$NIX" | grep -oE 'Aaru/releases/download/v[0-9.]+' | head -1 | sed 's/.*v//')
    OUR_RD=$(grep -m1 '^Version:' "$(dirname "$0")/../fedora/redumper/redumper.spec" | awk '{print $2}')
    OUR_AA=$(grep -m1 '^Version:' "$(dirname "$0")/../fedora/aaru5/aaru5.spec"       | awk '{print $2}')

    cmp_line() {   # name, what MPF bundles, what we point at
        if [ "$2" = "$3" ]; then
            printf '  \033[32mok\033[0m    %-10s MPF buendelt %-10s wir liefern %s\n' "$1" "$2" "$3"
        else
            printf '  \033[31mDRIFT\033[0m %-10s MPF buendelt %-10s wir liefern %s\n' "$1" "$2" "$3"
        fi
    }
    cmp_line redumper "b${MPF_RD:-?}" "b${OUR_RD:-?}"
    cmp_line aaru5    "${MPF_AA:-?}"  "${OUR_AA:-?}"
    if [ "b${MPF_RD:-x}" != "b${OUR_RD:-y}" ] || [ "${MPF_AA:-x}" != "${OUR_AA:-y}" ]; then
        echo "  -> entscheiden: rolling nachziehen, oder ein gepinntes redumper<N>/aaru<N> bauen"
        echo "     (MPF hat KEINE Versionspruefung — es meldet die Abweichung nie selbst)"
    fi
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
