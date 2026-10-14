#!/bin/bash
#
# dic-helpers.sh -- the master commits DiscImageCreator's three helper tools are
# built from (EccEdc, DVDAuth, unscrambler), in every recipe that names them.
#
#   scripts/dic-helpers.sh get                  print "<repo> <commit>" per helper,
#                                               read from the Fedora spec
#   scripts/dic-helpers.sh set <repo>=<commit> ...
#                                               rewrite the pin in the Fedora spec,
#                                               the openSUSE spec and debian/rules
#   scripts/dic-helpers.sh check                exit 1 unless all three recipes
#                                               pin the same commits
#   scripts/dic-helpers.sh release <message>    a new build of the SAME DIC
#                                               version (only a helper moved):
#                                               Fedora Release +1, Debian
#                                               revision +1, a changelog entry
#                                               in all three recipes
#
# The helpers track master like DIC itself (2026-10-14: EccEdc master carried two
# fixes its last release lacked, and the other two have no release newer than
# their master). Each pin is written in three places -- a %global in both specs
# and a make variable in debian/rules, which unpacks the archive the .dsc
# delivers by its name -- and the Formula follows the Fedora spec through
# brew-sync.py. A pin that differs between them builds one lane from another
# commit, or breaks the Debian build on a missing directory, so lint.sh runs
# `check`, and `set` proves every rewrite landed.
set -euo pipefail

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
FEDORA="$ROOT/fedora/discimagecreator/discimagecreator.spec"
OPENSUSE="$ROOT/opensuse/discimagecreator/discimagecreator.spec"
RULES="$ROOT/ubuntu/discimagecreator/debian/rules"

# repo  spec macro  debian/rules variable
HELPERS=(
    "EccEdc eccedccommit ECCEDCCOMMIT"
    "DVDAuth dvdauthcommit DVDAUTHCOMMIT"
    "unscrambler unscramblcommit UNSCRAMBLCOMMIT"
)

spec_pin() {   # spec_pin <file> <macro>
    local hits
    hits=$(sed -n -E "s/^%global[[:space:]]+${2}[[:space:]]+([0-9a-f]{40})[[:space:]]*$/\1/p" "$1")
    [ "$(printf '%s\n' "$hits" | grep -c .)" = 1 ] || { echo "$1: expected one '%global $2 <40-hex>' line" >&2; return 1; }
    printf '%s\n' "$hits"
}

rules_pin() {  # rules_pin <variable>
    local hits
    hits=$(sed -n -E "s/^${1}[[:space:]]*:=[[:space:]]*([0-9a-f]{40})[[:space:]]*$/\1/p" "$RULES")
    [ "$(printf '%s\n' "$hits" | grep -c .)" = 1 ] || { echo "$RULES: expected one '$1 := <40-hex>' line" >&2; return 1; }
    printf '%s\n' "$hits"
}

case ${1:-} in
get)
    for h in "${HELPERS[@]}"; do
        read -r repo macro _ <<<"$h"
        pin=$(spec_pin "$FEDORA" "$macro") || exit 1
        printf '%s %s\n' "$repo" "$pin"
    done
    ;;
set)
    shift
    [ $# -gt 0 ] || { echo "set: nothing to set" >&2; exit 2; }
    for kv in "$@"; do
        repo=${kv%%=*} sha=${kv#*=}
        [[ $sha =~ ^[0-9a-f]{40}$ ]] || { echo "set: '$kv' -- want <repo>=<40-hex commit>" >&2; exit 2; }
        found=
        for h in "${HELPERS[@]}"; do
            read -r r macro var <<<"$h"
            [ "$r" = "$repo" ] || continue
            found=1
            for spec in "$FEDORA" "$OPENSUSE"; do
                spec_pin "$spec" "$macro" >/dev/null
                sed -i -E "s/^(%global[[:space:]]+${macro}[[:space:]]+)[0-9a-f]{40}/\1$sha/" "$spec"
                [ "$(spec_pin "$spec" "$macro")" = "$sha" ] || { echo "set: $macro did not land in $spec" >&2; exit 1; }
            done
            rules_pin "$var" >/dev/null
            sed -i -E "s/^(${var}[[:space:]]*:=[[:space:]]*)[0-9a-f]{40}/\1$sha/" "$RULES"
            [ "$(rules_pin "$var")" = "$sha" ] || { echo "set: $var did not land in $RULES" >&2; exit 1; }
            echo ":: $repo -> ${sha:0:8} (both specs, debian/rules)"
        done
        [ -n "$found" ] || { echo "set: unknown helper '$repo' (known: EccEdc DVDAuth unscrambler)" >&2; exit 2; }
    done
    ;;
check)
    bad=0
    for h in "${HELPERS[@]}"; do
        read -r repo macro var <<<"$h"
        f=$(spec_pin "$FEDORA" "$macro") || { bad=1; continue; }
        o=$(spec_pin "$OPENSUSE" "$macro") || { bad=1; continue; }
        d=$(rules_pin "$var") || { bad=1; continue; }
        if [ "$f" != "$o" ] || [ "$f" != "$d" ]; then
            echo "$repo: fedora ${f:0:8}, opensuse ${o:0:8}, debian/rules ${d:0:8} -- one commit, three places" >&2
            bad=1
        fi
    done
    [ "$bad" = 0 ] || exit 1
    echo "DIC helpers: EccEdc, DVDAuth and unscrambler pinned to the same commits in all three recipes"
    ;;
release)
    # The version names DIC's commit only, so a helper commit leaves it alone.
    # Every lane then needs its own counter to move, or nobody upgrades: Fedora's
    # Release, Debian's revision (apt compares the whole version), and openSUSE's
    # OBS build counter, which moves by itself. The Formula's `revision` follows
    # in brew-sync.py --write.
    msg=${2:?release: message}
    snap=$(sed -n -E 's/^%global[[:space:]]+dicsnap[[:space:]]+([^[:space:]]+)[[:space:]]*$/\1/p' "$FEDORA")
    rel=$(sed -n -E 's/^Release:[[:space:]]+([0-9]+)%\{\?dist\}[[:space:]]*$/\1/p' "$FEDORA")
    [ -n "$snap" ] && [[ $rel =~ ^[0-9]+$ ]] || { echo "release: cannot read dicsnap / Release from $FEDORA" >&2; exit 1; }
    new=$((rel + 1))
    sed -i -E "s/^(Release:[[:space:]]+)$rel(%\{\?dist\})/\1$new\2/" "$FEDORA"
    grep -Eq "^Release:[[:space:]]+$new%\{\?dist\}" "$FEDORA" || { echo "release: Release $new did not land" >&2; exit 1; }
    entry=$(mktemp)
    {
        printf '* %s gmipf <gmipf64@gmail.com> - %s-%s\n' "$(LC_ALL=C date -u +'%a %b %d %Y')" "$snap" "$new"
        printf '%s\n' "$msg" | fold -s -w 74 | sed -e '1s/^/- /' -e '2,$s/^/  /' -e 's/[[:space:]]*$//'
        printf '\n'
    } >"$entry"
    sed -i "/^%changelog/r $entry" "$FEDORA"
    rm -f "$entry"
    echo ":: $FEDORA -> $snap-$new"

    top=$(head -1 "$ROOT/ubuntu/discimagecreator/debian/changelog" | sed -n -E 's/^[^ ]+ \(([^)]+)\).*/\1/p')
    [ "${top%-*}" = "$snap" ] && [[ ${top##*-} =~ ^[0-9]+$ ]] || {
        echo "release: debian/changelog starts with '$top', not $snap-<n> -- the lanes disagree on the DIC version" >&2
        exit 1
    }
    bash "$ROOT/scripts/deb/bump-changelog.sh" "$ROOT/ubuntu/discimagecreator" "$snap" "$msg" "$((${top##*-} + 1))"
    (cd "$ROOT" && bash scripts/opensuse-bump.sh discimagecreator "$snap" - "$msg" dicsnap="$snap")
    ;;
*)
    sed -n '3,12p' "$0" >&2
    exit 2
    ;;
esac
