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
# script does not just print state, it names the two silent failures:
#
#   * VERSION DRIFT — one tool, different versions across the PPA series.
#   * RED RUNS      — failed workflow runs nobody acknowledged.
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

# --- silent failure #2: red runs nobody looked at -----------------------------
hr "Fehlgeschlagene Workflow-Laeufe (letzte 40)"
RED=$(gh run list --limit 40 \
        --json workflowName,conclusion,createdAt,databaseId 2>/dev/null \
      | jq -r '.[] | select(.conclusion == "failure")
               | "  \(.createdAt[0:16])  \(.workflowName)  (run \(.databaseId))"')
if [ -n "$RED" ]; then
    printf '\033[31m%s\033[0m\n' "$RED"
    echo "  -> Grund lesen: gh run view <id> --log-failed"
else
    echo "  keine"
fi
