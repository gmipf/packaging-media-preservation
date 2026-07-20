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
hr "MPF-Bundle + Pins (feste Namen, wandernde Version)"
REPO=$(cd "$(dirname "$0")/.." && pwd)
NIX=$(curl -fsSL https://raw.githubusercontent.com/SabreTools/MPF/master/publish-nix.sh 2>/dev/null)
if [ -z "$NIX" ]; then
    echo "  publish-nix.sh nicht erreichbar — Bundle-Drift UNGEPRUEFT"
else
    ok()  { printf '  \033[32mok\033[0m    %s\n' "$1"; }
    bad() { printf '  \033[31mFEHLER\033[0m %s\n' "$1"; }

    # Was MPF heute buendelt.
    MPF_RD=$(printf '%s' "$NIX" | grep -oE 'redumper/releases/download/b[0-9]+' | head -1 | grep -oE '[0-9]+$')
    MPF_AA=$(printf '%s' "$NIX" | grep -oE 'Aaru/releases/download/v[0-9.]+'    | head -1 | sed 's/.*v//')

    # Unsere Pin-Versionen (fester Name, Version = Build). rpmspec, weil Version ein Makro ist.
    verof() { rpmspec -q --queryformat '%{version}\n' "$REPO/fedora/$1/$1.spec" 2>/dev/null | head -1; }
    MPF_PIN=$(verof redumper-mpf)
    AA_PIN=$(verof aaru5)

    # Wohin zeigen die Konsumenten? Feste Namen -- kein Namensbau mehr aus der Build-Nr.
    PTR_META=$(rpmspec -q --recommends "$REPO/fedora/mpf/mpf.spec"          2>/dev/null | grep -oE '^redumper-mpf'  | head -1)
    PTR_SEED=$(grep -oE '^red_p=redumper-mpf' "$REPO/fedora/mpf/mpf.spec" | head -1 | sed 's/^red_p=//')
    RGUI_REQ=$(rpmspec -q --requires "$REPO/fedora/redumper-gui/redumper-gui.spec" 2>/dev/null | grep -oE '^redumper-rgui' | head -1)

    # 1. mpf zeigt auf den FESTEN Namen redumper-mpf (Metadaten UND Config-Seed).
    if [ "$PTR_META" = redumper-mpf ] && [ "$PTR_SEED" = redumper-mpf ]; then
        ok "mpf -> redumper-mpf (Recommends + Config-Seed)"
    else
        bad "mpf zeigt nicht auf redumper-mpf: Recommends=${PTR_META:-?} Seed=${PTR_SEED:-?}"
    fi

    # 2. redumper-mpf VERSION == der Build, den MPF buendelt. Bei festem Namen ist das
    #    ein reiner Versions-Bump; weicht es ab, ist watch-consumer-pins hinterher/aus.
    if [ "$MPF_PIN" = "$MPF_RD" ]; then
        ok "redumper-mpf Version ${MPF_PIN} == MPF-Bundle b${MPF_RD}"
    else
        bad "redumper-mpf ist ${MPF_PIN:-?}, MPF buendelt b${MPF_RD:-?} -> watch-consumer-pins bumpt (oder haengt)"
    fi

    # 3. redumper-gui zeigt auf den festen Namen redumper-rgui.
    if [ "$RGUI_REQ" = redumper-rgui ]; then
        ok "redumper-gui -> redumper-rgui (Requires)"
    else
        bad "redumper-gui Requires zeigt nicht auf redumper-rgui: ${RGUI_REQ:-?}"
    fi

    # 4. Beide Pin-Rezepte in allen drei Lanes.
    for pin in redumper-mpf redumper-rgui; do
        MISS=""
        for lane in fedora ubuntu opensuse; do [ -d "$REPO/$lane/$pin" ] || MISS="$MISS $lane"; done
        [ -z "$MISS" ] && ok "Rezept ${pin} in allen drei Lanes" || bad "Rezept ${pin} FEHLT in:${MISS}"
    done

    # 5. Aaru: MPF faehrt nur latest stable = aaru5.
    if [ "$MPF_AA" = "$AA_PIN" ]; then
        ok "aaru5 Version ${AA_PIN} == MPF-Bundle Aaru ${MPF_AA}"
    else
        bad "aaru5 ist ${AA_PIN:-?}, MPF buendelt Aaru ${MPF_AA:-?}"
    fi

    # KEIN Waisen-Check mehr. Feste Namen, je EIN Konsument pro Pin -> ein Waisenpaket
    # ist strukturell unmoeglich geworden. Genau das war der Zweck der Umbenennung
    # von redumper<N> auf redumper-mpf/-rgui (17.07.): der Pin wandert per Versions-
    # Bump mit, statt dass ein neuer Name entsteht und der alte verwaist.
fi

hr "Workflow-Laeufe (letzte 40)"
# Same trap as the OBS block below, but pointing the OTHER way, which is why this
# one is the dangerous one: when `gh` fails, RUNS is empty, every jq filter below
# yields nothing, RED comes out empty -- and empty RED prints "keine offenen
# (letzter Lauf jedes Workflows ist gruen)". The check whose whole job is to
# catch silent failures reports ALL CLEAR when it could not look.
#
# Not hypothetical: 2026-07-20 two watchers died on `gh: ... (HTTP 503)`. Had the
# same outage hit this script while I was investigating them, it would have told
# me everything was fine. Measured before fixing: jq on empty input exits 0 and
# prints nothing, so nothing anywhere goes wrong loudly.
#
# So verify an ANSWER arrived -- a JSON array -- before believing what it implies.
# An empty array is a real measurement ("no runs"); no array is no measurement.
if ! RUNS=$(gh run list --limit 40 \
            --json workflowName,conclusion,createdAt,databaseId 2>/dev/null) \
   || ! jq -e 'type == "array"' >/dev/null 2>&1 <<<"$RUNS"; then
    echo "  gh nicht erreichbar — Workflow-Zustand UNGEPRUEFT (keine Entwarnung)"
    RUNS=""
fi
if [ -n "$RUNS" ]; then
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
# --- silent failure #6: _service names a file that is not there ---------------
# OBS pulls the recipe itself: every opensuse/<tool>/_service lists each file it
# needs as a download_url off raw.githubusercontent. Delete or rename one of
# those files in git and NOTHING here complains -- the .dsc still matches, the
# debian.tar.gz still matches, the spec still parses. OBS finds out instead, and
# reports it as `broken: service error: ERROR 404: Not Found`, which reads like
# an OBS outage rather than our own dangling reference.
#
# That is exactly what dropping the redumper-gui patch did on 2026-07-19: the
# spec stopped referencing it, gen-deb.sh regenerated the .dsc and the tarball
# happily, and _service went on demanding a file that no longer existed.
# gen-deb.sh only owns the DEB block of _service, not this recipe-file list.
#
# Two questions, because the file exists in two places and they drift apart
# independently:
#   A. does every URL still resolve?  (a deleted file 404s)
#   B. is OBS running the same _service we have in git?  The workflow token can
#      only `runservice`; the _service itself reaches OBS only through an
#      `osc commit` that nothing automates. A forgotten one is invisible until
#      a build breaks for a reason that points at the wrong thing.
# "I could not measure" is NOT a finding, and reporting it as one is its own bug.
# Both halves below talk to the network, so both have a third outcome besides
# ok/broken: no answer at all. They must be told apart, in BOTH directions:
#
#   - Calling "unreachable" a FEHLER makes this section permanently red for
#     anyone without OBS credentials -- and a check that is always red gets
#     ignored exactly like one that can never be red.
#   - But counting it as ok is worse: the summary would then print
#     "OBS-Stand == git" for eight packages nobody actually asked OBS about.
#     A false green is never revisited. So unmeasured suppresses the all-clear
#     without claiming a defect.
hr "OBS _service — Datei-URLs und Stand gegen OBS"
SVC_BAD=0
SVC_UNKNOWN=0
for svc in "$REPO"/opensuse/*/_service; do
    tool=$(basename "$(dirname "$svc")")
    while read -r u; do
        [ -n "$u" ] || continue
        # Measured 2026-07-20: no route/DNS -> exit 56 and code "000"; a real
        # missing file -> exit 0 and code "404". So the status line is the
        # evidence that a question was actually answered, and "000" is not a
        # status -- it is the absence of one.
        code=$(curl -sI -m 20 -o /dev/null -w '%{http_code}' "$u" 2>/dev/null)
        case "$code" in
            200|302) ;;
            000|'') printf '  \033[33mUNKLAR\033[0m %-18s nicht erreichbar (keine Messung)  %s\n' \
                        "$tool" "${u##*/}"
                    SVC_UNKNOWN=$((SVC_UNKNOWN + 1)) ;;
            *) printf '  \033[31mFEHLER\033[0m %-18s HTTP %s  %s\n' "$tool" "$code" "${u##*/}"
               SVC_BAD=$((SVC_BAD + 1)) ;;
        esac
    done <<<"$(sed -n 's|.*<param name="url">\(.*\)</param>.*|\1|p' "$svc")"

    # osc's failure does NOT look like "empty" -- which is why the `-z` test that
    # stood here sailed straight past it. Without readable credentials osc prints
    # its interactive prompt to STDOUT and exits 1: 29 bytes of
    # "Username [api.opensuse.org]: " that are non-empty, differ from the file,
    # and so reported all eight packages as drifted. Measured 2026-07-20 in the
    # sandbox, where ~/.config/osc/oscrc is unreadable; with credentials the very
    # same run is green.
    #
    # So do not ask "did anything come back" -- ask "did an ANSWER come back":
    # a non-zero exit, or a body that is not a _service document, means we could
    # not measure. `< /dev/null` because that prompt is read from stdin: given a
    # terminal this call HANGS instead of failing, and a check that hangs never
    # reports anything at all.
    #
    # Note the earlier bug fixed here (trailing newline, see printf '%s\n' below)
    # had the SAME symptom -- all eight red -- and a different cause. The comment
    # explaining it made this second cause look like something already handled.
    if ! remote=$(osc -A https://api.opensuse.org api \
                  "/source/${OBS_PROJECT}/${tool}/_service" 2>/dev/null </dev/null) \
       || ! printf '%s' "$remote" | grep -q '<services'; then
        printf '  \033[33mUNKLAR\033[0m %-18s OBS nicht befragbar (keine Messung, kein Befund)\n' "$tool"
        SVC_UNKNOWN=$((SVC_UNKNOWN + 1))
    # printf '%s\n', not '%s': $(...) strips the trailing newline the file has,
    # so comparing raw makes EVERY package look drifted.
    elif ! diff -q <(printf '%s\n' "$remote") "$svc" >/dev/null 2>&1; then
        printf '  \033[31mFEHLER\033[0m %-18s _service in OBS != git -- `osc commit` fehlt\n' "$tool"
        SVC_BAD=$((SVC_BAD + 1))
    fi
done
if [ "$SVC_BAD" = 0 ] && [ "$SVC_UNKNOWN" = 0 ]; then
    echo "  alle _service-URLs loesen auf, OBS-Stand == git"
elif [ "$SVC_UNKNOWN" -gt 0 ]; then
    printf '  \033[33m--\033[0m       %s Pruefung(en) nicht durchgefuehrt — kein Befund, aber auch keine Entwarnung\n' \
        "$SVC_UNKNOWN"
fi

# --- silent failure #7: a package nobody tracks -------------------------------
# HARD RULE (2026-07-19): no package here may be human-supervised. Upstream
# tracking AND building must be automatic, without exception. A loud-fail guard
# that pings a human is a STEPPING STONE, not a finished state.
#
# The rule exists because of redumper-gui. It was the only one of the eight with
# no watcher at all -- and that was *documented*, in watch-consumer-pins.yml:
# "redumper-gui is not hourly-tracked; ... bump redumper-rgui in the SAME change".
# The coupling was described correctly and was still useless, because it assumed
# a human would notice a release. Nobody did: upstream v1.0.2 sat there for two
# days while we shipped 1.0.1, and the coupled pin (b729 vs the bundled b733)
# went stale with it. Nothing turned red. It was SILENCE -- and a package that
# quietly falls two versions behind looks green in every overview there is.
#
# So this check derives the package list from the FILESYSTEM, never from a list
# someone maintains here, and asks two questions:
#
#   A. COVERAGE  -- does some watcher actually reference this package?
#      Comments are STRIPPED before matching, deliberately. That is the whole
#      point: redumper-rgui *is* named in watch-consumer-pins.yml, but only in
#      prose. Documented is not implemented, and this check must not confuse the
#      two -- confusing them is precisely what cost us those two days.
#
#   B. HANDOFF   -- does a watcher deliberately stop and ask a human to act?
#      Only "the automation chose to stop" counts. "could not push after 3
#      attempts" is the tool being broken, which SHOULD be loud and is not a
#      rule violation.
#
# Honest limit: B matches on wording, so a novel phrasing ("please fix this
# yourself") would slip past. A is mechanical and cannot. If you add a watcher,
# A is the one that guarantees you get caught; keep B's vocabulary in mind when
# writing a new guard.
hr "Auto-Tracking — kein Paket darf menschenueberwacht sein"
TRACK_BAD=0
for d in "$REPO"/fedora/*/; do
    pkg=$(basename "$d")
    [ -f "$d/$pkg.spec" ] || continue
    seen=""
    for w in "$REPO"/.github/workflows/watch-*.yml; do
        [ -f "$w" ] || continue
        sed 's/#.*//' "$w" | grep -qE "fedora/$pkg/|(^|[^-])$pkg\.spec" \
            && seen="$seen $(basename "$w" .yml)"
    done
    if [ -n "$seen" ]; then
        printf '  \033[32mok\033[0m    %-18s <-%s\n' "$pkg" "$seen"
    else
        printf '  \033[31mFEHLER\033[0m %-18s KEIN Watcher nennt dieses Paket (Kommentare zaehlen nicht)\n' "$pkg"
        TRACK_BAD=$((TRACK_BAD + 1))
    fi
done

# A DECLARED exception is not a violation -- but it must stay visible, or it is just
# a silent handoff with better manners. A workflow declares one with a line
#
#   # full-automation-exception: <pkg> — <reason>
#
# and this prints it every run, in its own colour, with the reason. Delete the line
# and the handoff below it counts as a violation again.
#
# This is not a loophole in the same sense the comment-stripping in part A closes.
# There, the danger was prose PRETENDING to be an implementation. Here the exception
# IS a documentation decision -- the check exists to stop handoffs nobody NOTICED,
# and a declared one has been noticed. What it must not do is let the declaration
# fade: hence printed, not merely subtracted.
EXC=$(grep -h '# full-automation-exception:' "$REPO"/.github/workflows/watch-*.yml 2>/dev/null \
      | sed 's/.*full-automation-exception:[[:space:]]*//')
if [ -n "$EXC" ]; then
    while IFS= read -r e; do
        [ -n "$e" ] || continue
        printf '  \033[33mAUSNAHME\033[0m %s\n' "$e"
    done <<<"$EXC"
fi

for w in "$REPO"/.github/workflows/watch-*.yml; do
    [ -f "$w" ] || continue
    # Does THIS workflow declare an exception? Then its handoffs are accounted for.
    # No `|| echo 0` here: `grep -c` already PRINTS 0 when it matches nothing, and
    # exits 1 while doing it -- so the fallback fires too and the variable becomes
    # the two-line string "0\n0", which `[ -gt ]` then rejects with "integer
    # expected". Measured, not guessed: the first version of this line did exactly
    # that, and bash said so on stderr while the check still produced right answers.
    declared=$(grep -c '# full-automation-exception:' "$w" 2>/dev/null) || true
    while IFS= read -r hit; do
        [ -n "$hit" ] || continue
        if [ "$declared" -gt 0 ]; then
            printf '  \033[33m--\033[0m       %-18s %s:%s — Uebergabe, aber DEKLARIERT\n' \
                "-" "$(basename "$w")" "${hit%%:*}"
        else
            printf '  \033[31mFEHLER\033[0m %-18s %s:%s uebergibt an einen MENSCHEN\n' \
                "-" "$(basename "$w")" "${hit%%:*}"
            TRACK_BAD=$((TRACK_BAD + 1))
        fi
    done <<<"$(grep -nE '::error::' "$w" \
                | grep -iE 'by hand|manual|von Hand|review required|bump it|by a human|decided to measure|deliberately NOT auto' \
                | cut -d: -f1)"
done

if [ "$TRACK_BAD" = 0 ]; then
    echo "  alle Pakete maschinell verfolgt; keine UNDEKLARIERTE Uebergabe an Menschen"
else
    echo "  -> ${TRACK_BAD} Verstoss(e) gegen die Vollautomatik-Regel"
fi

# --- silent failure #8: the lane markers drift apart --------------------------
# Every recipe carries a .upstream-tag naming the upstream revision it describes.
# Only the fedora/ one is ever READ -- the watchers use it as their "what did I
# see last" memory. The opensuse/ and ubuntu/ copies are written by every bump
# path and read by nothing, and state nobody reads cannot go red. It just drifts.
#
# It had, unnoticed, until 2026-07-19: fedora/ and ubuntu/ still said redumper-gui
# v1.0.1 while opensuse/ said v1.0.2, and ubuntu/redumper-rgui still said b729
# against b733 in the other two -- bump-pin.sh simply never wrote that one file.
#
# The obvious fix is to delete the unread copies. This does the opposite, because
# the marker is the ONE lane-independent way to ask "do these three recipes
# describe the same upstream revision?": the spec Version, the .dsc and
# debian/changelog each spell it differently, so only the marker compares. Read
# them, and they stop being decoration.
#
# Two mechanical questions:
#   A. do all lanes that carry a marker for a package agree with each other?
#   B. does the marker agree with the version the fedora spec actually builds?
#      Four shapes exist in the tree today and three are checkable:
#        v<semver>   -> spec version, with '-' spelled '~' (rpm sort order)
#        b<N>        -> spec version verbatim
#        <sha40>     -> its first 8 chars END the spec's snapshot version
#        rolling     -> mpf tracks a branch; there is no revision to compare.
#                       SKIPPED -- and counted and named, not passed over. A check
#                       that hides what it did not look at reads as full coverage.
#      Order matters below: the sha40 test runs BEFORE the b<N> test, because a
#      commit hash beginning "b3..." would otherwise be read as build 3.
hr "Upstream-Marker — beschreiben alle Lanes dieselbe Revision?"
MARK_BAD=0
MARK_SKIP=0
MARK_PKGS=$(for l in fedora opensuse ubuntu; do
                for m in "$REPO"/$l/*/.upstream-tag; do
                    [ -f "$m" ] && basename "$(dirname "$m")"
                done
            done | sort -u)
for pkg in $MARK_PKGS; do
    shown=""
    vals=$(for l in fedora opensuse ubuntu; do
               m="$REPO/$l/$pkg/.upstream-tag"
               [ -f "$m" ] && head -1 "$m"
           done)
    for l in fedora opensuse ubuntu; do
        m="$REPO/$l/$pkg/.upstream-tag"
        [ -f "$m" ] && shown="$shown $l=$(head -1 "$m")"
    done
    if [ "$(printf '%s\n' "$vals" | sort -u | wc -l)" -gt 1 ]; then
        printf '  \033[31mFEHLER\033[0m %-18s Lanes uneinig:%s\n' "$pkg" "$shown"
        MARK_BAD=$((MARK_BAD + 1))
        continue
    fi
    tag=$(printf '%s\n' "$vals" | head -1)
    spec="$REPO/fedora/$pkg/$pkg.spec"
    if [ ! -f "$spec" ]; then
        printf '  \033[32mok\033[0m    %-18s %-24s (Pin ohne fedora-Marker, Lanes einig)\n' "$pkg" "$tag"
        continue
    fi
    sv=$(rpmspec -q --queryformat '%{version}\n' "$spec" 2>/dev/null | head -1)
    if [ "$tag" = rolling ]; then
        printf '  \033[33m--\033[0m    %-18s rolling — kein Revisionsvergleich moeglich (Spec: %s)\n' "$pkg" "$sv"
        MARK_SKIP=$((MARK_SKIP + 1))
        continue
    elif [ ${#tag} = 40 ]; then
        short=$(printf '%s' "$tag" | cut -c1-8)
        case "$sv" in *".$short") ok=1 ;; *) ok= ;; esac
        want="Snapshot endend auf .$short"
    elif [ "${tag#v}" != "$tag" ]; then
        want=$(printf '%s' "${tag#v}" | tr '-' '~')
        [ "$sv" = "$want" ] && ok=1 || ok=
    elif [ "${tag#b}" != "$tag" ]; then
        want=${tag#b}
        [ "$sv" = "$want" ] && ok=1 || ok=
    else
        want=$tag
        [ "$sv" = "$want" ] && ok=1 || ok=
    fi
    if [ -n "$ok" ]; then
        printf '  \033[32mok\033[0m    %-18s %-24s == Spec %s\n' "$pkg" "$tag" "$sv"
    else
        printf '  \033[31mFEHLER\033[0m %-18s Marker %s erwartet %s, Spec baut %s\n' \
            "$pkg" "$tag" "$want" "$sv"
        MARK_BAD=$((MARK_BAD + 1))
    fi
done
if [ "$MARK_BAD" = 0 ]; then
    printf '  alle Lanes einig, Marker deckt die gebaute Version'
    [ "$MARK_SKIP" = 0 ] && echo || printf ' (%s ohne Revision uebersprungen)\n' "$MARK_SKIP"
else
    echo "  -> ${MARK_BAD} Marker-Drift(s); Bump-Pfad hat eine Lane nicht mitgezogen"
fi

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
