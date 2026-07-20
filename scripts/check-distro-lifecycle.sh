#!/usr/bin/env bash
#
# check-distro-lifecycle.sh — does a distribution exist that we do not build for,
# and are we still building for one that is dead?
#
# WHY THIS EXISTS
#
# COPR handles this by itself: `fedora-all` and `epel-all` resolve at BUILD time,
# so Fedora 44 appeared in our repo and Fedora 42 left it without anyone touching
# anything. OBS has no equivalent. Every target is a hand-written <repository>
# block in the project meta, so Debian 14, Leap 17 or Ubuntu 26.10 will simply
# never be built for -- and nothing turns red, because nothing asks. That is the
# same shape of silence that let redumper-gui sit two versions behind: a state
# nobody reads cannot go wrong loudly.
#
# WHERE THE TRUTH COMES FROM -- and why not from OBS
#
# Measured 2026-07-20, and it went against my first design:
#
#   * The OBS API needs authentication even to READ a public project (HTTP 401 on
#     /source/<proj>/_meta and on /search/project/id). A GitHub runner has no
#     oscrc, and the fix is NOT to put the OBS account password in a repository
#     secret to power a convenience check.
#   * OBS's /distributions list is INCOMPLETE. It omits CentOS:CentOS-10:Stream,
#     which exists as a project. A check built on it would miss exactly the new
#     releases it is meant to catch.
#   * The project namespace knows that openSUSE:Leap:16.1 exists -- but not that
#     it is a BETA. Asking OBS would have said "you are missing 16.1" and sent a
#     human off to add a repository for an unreleased distribution.
#
# So ask the distributions themselves. Their own feeds are anonymous, and they
# carry the one thing OBS does not: lifecycle STATE (released / beta / EOL).
# That is the actual question here.
#
# WHAT WE SHIP TO comes from scripts/rust-targets.tsv, the only place in git that
# records our targets as data rather than prose. `ship` and `out` are BOTH
# targets for this purpose: an `out` row is frozen at its last build, not gone,
# so its distribution going EOL still matters.
#
# HOW IT REPORTS
#
# Exit non-zero on an actionable finding, and only then. Measured 2026-07-20: a
# SCHEDULED workflow run on main that exits non-zero produces a GitHub e-mail
# that reaches the maintainer's inbox -- two independent instances that day
# (watch-aaru-releases, watch-redumper-releases, both `event: schedule`, both
# failing on an HTTP 503). A green run with a ::warning:: sends nothing. So the
# notification IS the failure; there is no other channel.
#
# Acting on a finding needs a human: adding a <repository> block is a write to
# the OBS project meta, and no OBS token can do that (they do runservice, branch,
# release, rebuild, workflow -- nothing that writes meta). The workflow therefore
# declares itself an exception to the full-automation rule; see the header of
# .github/workflows/watch-distro-lifecycle.yml.

set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
TARGETS="$REPO/scripts/rust-targets.tsv"
FINDINGS=0
UNMEASURED=0

note() { printf '  %s\n' "$1"; }
find_() { printf '  \033[31mFUND\033[0m   %s\n' "$1"; FINDINGS=$((FINDINGS + 1)); }
soon()  { printf '  \033[33m..\033[0m     %s\n' "$1"; }
ok()    { printf '  \033[32mok\033[0m     %s\n' "$1"; }

# A feed we could not read is NOT an all-clear. This script exists because a
# silent gap is invisible; reporting "nothing found" when the answer never
# arrived would rebuild exactly that. Same rule as status.sh: no answer is not
# a good answer.
unmeasured() { printf '  \033[33mUNKLAR\033[0m %s\n' "$1"; UNMEASURED=$((UNMEASURED + 1)); }

fetch() {  # fetch <url> <outfile> -> 0 on a real 200 with a non-empty body
    local url=$1 out=$2 code
    code=$(curl -sSL -m 30 -o "$out" -w '%{http_code}' "$url" 2>/dev/null)
    [ "$code" = 200 ] && [ -s "$out" ]
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Without the target inventory every comparison below silently compares against
# nothing -- awk prints its complaint to stderr, the loops iterate zero times and
# the script reports a tidy "kein fehlendes Ziel". Found while testing: a copy of
# this script run from outside the repo did exactly that. Stop instead.
if [ ! -r "$TARGETS" ]; then
    printf '  \033[31mABBRUCH\033[0m %s nicht lesbar — ohne Ziel-Inventar ist jeder Vergleich wertlos\n' "$TARGETS" >&2
    exit 2
fi

# Our OBS targets, as data. Column 2 is the target name; the lane column keeps
# COPR's rows out, because COPR resolves its own lifecycle and has nothing to
# report here.
obs_targets() { awk -F'\t' '$1 == "obs" { print $2 }' "$TARGETS" | sort -u; }

# version_of <target> -- pull the version out of our target spelling.
#   openSUSE_Leap_16.0 -> 16.0     xUbuntu_26.04 -> 26.04     Debian_13 -> 13
version_of() { printf '%s\n' "$1" | grep -oE '[0-9]+(\.[0-9]+)?$'; }

printf '\033[1m== Distro-Lebenszyklus — bauen wir fuer alles Aktuelle?\033[0m\n'
note "unsere OBS-Ziele: $(obs_targets | tr '\n' ' ')"
echo

# ---------------------------------------------------------------- openSUSE Leap
# get.opensuse.org carries a `state` field: Stable / Beta / EOL. That field is
# the whole reason this source beats the OBS project list.
if fetch "https://get.opensuse.org/api/v0/distributions.json" "$WORK/suse.json"; then
    OURS=$(obs_targets | grep -i 'leap' | while read -r t; do version_of "$t"; done | sort -V | tail -1)
    if [ -z "$OURS" ]; then
        unmeasured "Leap — kein Leap-Ziel in rust-targets.tsv gefunden, Vergleich unmoeglich"
    else
        LATEST_STABLE=$(jq -r '.Leap[] | select(.state == "Stable") | .version' "$WORK/suse.json" 2>/dev/null | sort -V | tail -1)
        if [ -z "$LATEST_STABLE" ]; then
            unmeasured "Leap — Feed gelesen, aber keine stabile Version darin erkannt"
        elif [ "$LATEST_STABLE" = "$OURS" ]; then
            ok "Leap ${OURS} ist die aktuelle stabile Version"
        elif [ "$(printf '%s\n%s\n' "$OURS" "$LATEST_STABLE" | sort -V | tail -1)" = "$LATEST_STABLE" ]; then
            find_ "Leap ${LATEST_STABLE} ist stabil, wir bauen fuer ${OURS} — <repository> fehlt"
        else
            ok "Leap ${OURS} ist neuer als der Feed meldet (${LATEST_STABLE})"
        fi
        # Not a finding: a beta is something to watch, not something to add. But
        # saying nothing about it would leave the next stable release a surprise.
        while read -r b; do
            [ -n "$b" ] && soon "Leap ${b} — noch nicht stabil, nichts zu tun; wird spaeter ein FUND"
        done < <(jq -r '.Leap[] | select(.state != "Stable" and .state != "EOL") | "\(.version) (\(.state))"' \
                    "$WORK/suse.json" 2>/dev/null | sort -V)
    fi
else
    unmeasured "Leap — get.opensuse.org nicht lesbar, Lebenszyklus UNGEPRUEFT"
fi
echo

# --------------------------------------------------------------------- Ubuntu
# meta-release carries `Supported: 0|1`, so it answers both halves: what is new,
# and what we still build for that Canonical has stopped supporting.
if fetch "https://changelogs.ubuntu.com/meta-release" "$WORK/ubu.txt"; then
    # The feed names POINT releases: "Version: 22.04.5 LTS", while we (and
    # everyone else) call that target 22.04. Comparing the strings raw made
    # jammy and noble look absent from a feed that lists them both -- the first
    # run of this script reported exactly that. Cut to MAJOR.MINOR.
    awk '/^Version:/ {v=$2} /^Supported:/ {print v"\t"$2}' "$WORK/ubu.txt" \
        | awk -F'\t' '{n=split($1,p,"."); printf "%s.%s\t%s\n", p[1], p[2], $2}' \
        | sort -u > "$WORK/ubu.tsv"
    if [ ! -s "$WORK/ubu.tsv" ]; then
        unmeasured "Ubuntu — Feed gelesen, aber keine Version/Supported-Paare erkannt"
    else
        NEWEST_SUPPORTED=$(awk -F'\t' '$2 == 1 {print $1}' "$WORK/ubu.tsv" | sort -V | tail -1)
        OURS_NEWEST=$(obs_targets | grep -i 'ubuntu' | while read -r t; do version_of "$t"; done | sort -V | tail -1)
        if [ -z "$NEWEST_SUPPORTED" ] || [ -z "$OURS_NEWEST" ]; then
            unmeasured "Ubuntu — Vergleich unmoeglich (Feed oder Ziel leer)"
        elif [ "$NEWEST_SUPPORTED" = "$OURS_NEWEST" ]; then
            ok "Ubuntu ${OURS_NEWEST} ist die neueste unterstuetzte Version"
        elif [ "$(printf '%s\n%s\n' "$OURS_NEWEST" "$NEWEST_SUPPORTED" | sort -V | tail -1)" = "$NEWEST_SUPPORTED" ]; then
            find_ "Ubuntu ${NEWEST_SUPPORTED} wird unterstuetzt, unser neuestes Ziel ist ${OURS_NEWEST} — <repository> fehlt"
        else
            ok "Ubuntu ${OURS_NEWEST} ist neuer als der Feed meldet"
        fi
        # The other half: targets we still carry that Canonical has dropped.
        #
        # `done < <(...)` and not `... | while`: a pipeline runs the loop in a
        # SUBSHELL, so every counter raised inside it is discarded when the loop
        # ends. The first version of this script did that and printed two UNKLAR
        # lines followed by "alle Familien geprueft" and exit 0 -- the same false
        # green this script exists to prevent, reintroduced in the code meant to
        # prevent it.
        while read -r t; do
            v=$(version_of "$t")
            s=$(awk -F'\t' -v v="$v" '$1 == v {print $2}' "$WORK/ubu.tsv" | head -1)
            case "$s" in
                1) ;;
                0) soon "Ubuntu ${v} (${t}) wird von Canonical nicht mehr unterstuetzt — eingefrorene Pakete bleiben nutzbar" ;;
                *) unmeasured "Ubuntu ${v} (${t}) kommt im Feed nicht vor" ;;
            esac
        done < <(obs_targets | grep -i 'ubuntu')
    fi
else
    unmeasured "Ubuntu — changelogs.ubuntu.com nicht lesbar, Lebenszyklus UNGEPRUEFT"
fi
echo

# --------------------------------------------------------------------- Debian
# Debian publishes no state feed in the shape the other two do, so read what its
# archive itself calls `stable`: dists/stable/Release names the current release.
if fetch "https://deb.debian.org/debian/dists/stable/Release" "$WORK/deb.txt"; then
    DEB_STABLE=$(awk -F': ' '/^Version:/ {print $2; exit}' "$WORK/deb.txt" | cut -d. -f1)
    OURS_NEWEST=$(obs_targets | grep -i 'debian' | while read -r t; do version_of "$t"; done | sort -V | tail -1)
    if [ -z "$DEB_STABLE" ] || [ -z "$OURS_NEWEST" ]; then
        unmeasured "Debian — Vergleich unmoeglich (Release-Datei oder Ziel leer)"
    elif [ "$DEB_STABLE" = "$OURS_NEWEST" ]; then
        ok "Debian ${OURS_NEWEST} ist die aktuelle stabile Version"
    elif [ "$(printf '%s\n%s\n' "$OURS_NEWEST" "$DEB_STABLE" | sort -V | tail -1)" = "$DEB_STABLE" ]; then
        find_ "Debian ${DEB_STABLE} ist stabil, unser neuestes Ziel ist ${OURS_NEWEST} — <repository> fehlt"
    else
        ok "Debian ${OURS_NEWEST} ist neuer als der Feed meldet (${DEB_STABLE})"
    fi
else
    unmeasured "Debian — deb.debian.org nicht lesbar, Lebenszyklus UNGEPRUEFT"
fi
echo

# ----------------------------------------------------------------------- Fazit
printf '\033[1m== Fazit\033[0m\n'
if [ "$FINDINGS" -gt 0 ]; then
    printf '  \033[31m%s Distribution(en) ohne <repository>-Block.\033[0m\n' "$FINDINGS"
    note "Das braucht eine Hand: der OBS-Projekt-Meta-Schreibpfad ist keinem Token zugaenglich."
    note "  osc meta prj -e home:gmipf:media-preservation   (Block ergaenzen)"
    note "  danach scripts/rust-targets.tsv um eine gemessene Zeile erweitern"
fi
if [ "$UNMEASURED" -gt 0 ]; then
    printf '  \033[33m%s Pruefung(en) nicht durchgefuehrt — kein Befund, aber auch keine Entwarnung.\033[0m\n' "$UNMEASURED"
fi
if [ "$FINDINGS" = 0 ] && [ "$UNMEASURED" = 0 ]; then
    printf '  \033[32mAlle Familien geprueft, kein fehlendes Ziel.\033[0m\n'
fi

# A feed we could not read fails the run too. Not because it is a defect, but
# because the alternative is a check that goes quiet exactly when the network it
# depends on is down -- and quiet is the failure mode this whole script exists
# to prevent.
[ "$FINDINGS" = 0 ] && [ "$UNMEASURED" = 0 ]
