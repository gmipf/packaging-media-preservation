#!/usr/bin/env bash
#
# status.sh — one look at both delivery lanes, plus the things that go wrong
# QUIETLY.
#
#   COPR                       -> copr-cli        (Fedora, EPEL)
#   OBS                        -> osc results     (openSUSE, Debian, Ubuntu)
#
# There used to be a third: a Launchpad PPA for Ubuntu. It is gone, and the way it
# failed is why the checks below exist at all. Launchpad dropped roughly 3% of its
# builds with no log and no start time -- its dispatcher, never our recipe -- and
# the failure was INVISIBLE: the source stayed "Published" on all three series at
# identical versions, so every version check we had stayed green while a binary
# simply did not exist. Ubuntu is built on OBS now, where a failed build is red.
#
# So this script does not just print state, it names the silent failures:
#
#   * BUNDLE DRIFT  — MPF bundles a specific redumper and Aaru build, and our mpf
#                     package deliberately drops those bundled binaries and points
#                     MPF's config at the system packages instead. If upstream MPF
#                     moves to a different bundled build, an MPF dump silently runs
#                     a dumper version its own upstream never tested. Nothing in
#                     either project says so: MPF has no version check at all, it
#                     only writes whatever version it finds into the submission.
#   * ORPHANED PINS — a pinned redumper<N> nobody points at any more keeps building
#                     and publishing forever, because nothing ever says otherwise.
#   * RED RUNS      — failed workflow runs nobody acknowledged.
#   * DEB DRIFT     — the .dsc, debian.tar.gz and _service are GENERATED from the
#                     recipe. Drift does not fail a build, it corrupts one: a stale
#                     .dsc makes debtransform silently rewrite debian/changelog to
#                     the version the .dsc claims, and a stale debian.tar.gz makes
#                     OBS build yesterday's debian/rules.
#   * BROKEN LINE    — a shell line continuation followed by a blank line. Valid
#                     YAML, valid bash, and it silently truncates the command and
#                     then tries to EXECUTE the next argument as a program.
#
# Usage: scripts/status.sh
# Needs network (copr, obs, github) -- run it outside the command sandbox.
#
# Sibling: scripts/proof-status.sh checks a fourth silent failure this one does
# NOT -- a drive-access proof (groupless/sudoless dumping) gone stale because the
# udev rule / scriptlet / %caps changed under it. Offline; run it too on "sync".
set -uo pipefail

COPR_PROJECT=${COPR_PROJECT:-gmipf/media-preservation}
OBS_PROJECT=${OBS_PROJECT:-home:gmipf:media-preservation}

hr() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

hr "COPR — ${COPR_PROJECT}"
copr-cli monitor "$COPR_PROJECT" \
    --output-format text-row --fields name,chroot,state,build_id 2>/dev/null \
  | awk -F'\t' '{printf "  %-16s %-22s %s\n", $1, $2, $3}' \
  | sort

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
            echo "     -> Rezept entfernen + 'copr-cli delete-package ${pin}' + aus OBS nehmen."
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
#   * die .dsc BENENNT die Upstream-Archive (Debtransform-Tar/-Files). Nennt sie
#     andere als die Spec, baut OBS das .deb aus anderen Bytes als die RPM --
#     beide gruen, beide "dieselbe" Version, verschiedener Inhalt.
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

    [ "$want" = "$have" ] || {
        printf '  \033[31m%-18s .dsc sagt %s, changelog sagt %s\033[0m\n' "$tool" "$have" "$want"
        DEB_DRIFT=1; }

    # Die Spec ist die Quelle der Wahrheit: download_files laedt GENAU ihre
    # Source:-URLs. Nennt die .dsc etwas anderes, sucht debtransform eine Datei,
    # die niemand geladen hat -- oder schlimmer: eine ALTE, die noch herumliegt.
    spec_src=$(rpmspec -P "$REPO/fedora/$tool/$tool.spec" 2>/dev/null \
        | sed -n 's/^Source[0-9]*:[[:space:]]*//p' | grep -E '^[a-z]+://' \
        | sed 's|.*#/||; s|.*/||' | sort | tr '\n' ' ')
    # Case-insensitiv lesen -- so wie debtransform es tut. Die .dsc MUSS die
    # Header GROSS schreiben (obs-build grept case-sensitiv nach
    # ^DEBTRANSFORM-FILES:, sonst kein --include-binaries), aber ein Pruefer, der
    # nur EINE Schreibweise kennt, meldet beim naechsten Wechsel wieder Rot fuer
    # nichts. Genau das ist hier passiert.
    dsc_src=$( { grep -i '^DEBTRANSFORM-TAR:'   "$dsc" | cut -d: -f2-
                 grep -i '^DEBTRANSFORM-FILES:' "$dsc" | cut -d: -f2- | tr ' ' '\n'; } \
        | tr -d ' ' | grep -v '^$' | sort | tr '\n' ' ')
    [ "$spec_src" = "$dsc_src" ] || {
        printf '  \033[31m%-18s .dsc nennt andere Upstream-Quellen als die Spec\033[0m\n' "$tool"
        printf '                     Spec: %s\n                     .dsc: %s\n' "$spec_src" "$dsc_src"
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

# --- silent failure #5: a line continuation followed by a blank line -----------
# `foo bar \` + an empty line is not a syntax error anywhere in the toolchain: the
# YAML is valid, `bash -n` is happy, and bash simply ENDS the command at the blank
# line. The arguments below it become COMMANDS -- so a `git add a \ / b \ / c`
# staged only `a` and then tried to execute `b`, exit 126, "permission denied".
# That killed all four watchers for five hours on 2026-07-14, and a red run only
# tells you AFTER an upstream release you then failed to ship. Grep for the shape
# instead: it is never intentional.
hr "Workflow-Shell — abgebrochene Zeilenfortsetzungen"
CONT=$(for f in "$REPO"/.github/workflows/*.yml "$REPO"/scripts/*.sh "$REPO"/scripts/obs/*.sh; do
    [ -f "$f" ] || continue
    awk -v F="${f#$REPO/}" '/\\[ \t]*$/ { l=$0; ln=NR; if ((getline nxt) > 0 && nxt ~ /^[ \t]*$/)
        printf "  %s:%d: %s\n", F, ln, l }' "$f"
done)
if [ -n "$CONT" ]; then
    printf '\033[31m%s\033[0m\n' "$CONT"
    echo "  -> Die Leerzeile MUSS weg: bash beendet den Befehl dort und fuehrt die"
    echo "     naechste Zeile als Programm aus (exit 126)."
else
    echo "  keine (kein '\\' am Zeilenende vor einer Leerzeile)"
fi
