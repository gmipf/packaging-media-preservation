#!/bin/bash
#
# lint.sh -- every offline lint rule of this repository, in one place.
#
#   scripts/lint.sh          CI (check-repo.yml): every tool must be installed;
#                            a missing one fails the run (not measured != clean)
#   scripts/lint.sh --hook   pre-commit: a tool that is not installed here is
#                            named and skipped -- CI still runs it
#
# Every rule was measured clean before it was switched on and seen red on a
# planted defect (2026-10-13). A finding fails the run; nothing here only warns.
#
#   whitespace      text files: no trailing blanks, no CR, a final newline
#                   (.editorconfig tells editors the same)
#   shell scripts   shellcheck on every *.sh AND every file with a shell shebang --
#                   the postinst scripts, the git hook and the mpf wrapper
#                   template had never been linted (-S warning)
#   xmllint         every OBS _service and *.xml is well-formed (a `--` inside
#                   an XML comment once broke a _service on OBS)
#   desktop-file-validate   every .desktop file, errors and warnings
#   yamllint        workflows, .packit.yaml (rules: .yamllint)
#   packit          .packit.yaml against Packit's own schema
set -uo pipefail

ROOT=$(git rev-parse --show-toplevel) || exit 2
cd "$ROOT" || exit 2
HOOK=0
[ "${1:-}" = --hook ] && HOOK=1

rc=0
skipped=""
bad() { echo "lint: $*" >&2; rc=1; }
ok() { echo "lint: ok   $*"; }
have() {
    command -v "$1" >/dev/null 2>&1 && return 0
    if [ "$HOOK" = 1 ]; then skipped="$skipped $1"; else bad "$1 is not installed -- not measured is not clean"; fi
    return 1
}

# git grep: 0 = found (a finding), 1 = nothing found (clean), else = it failed.
none() {
    local label=$1 out
    shift
    out=$(git grep "$@")
    case $? in
        0) bad "$label:"; printf '%s\n' "$out" >&2 ;;
        1) ok "$label" ;;
        *) bad "$label: git grep failed" ;;
    esac
}

# --- whitespace -------------------------------------------------------------
none "no trailing whitespace" -I -nE '[[:blank:]]+$'
none "no CR line endings" -I -l $'\r'
texts=$(git grep -I -l '') || { bad "could not list text files"; texts=""; }
[ -n "$texts" ] || bad "no text files found -- the check would pass on nothing"
missing=""
while IFS= read -r f; do
    [ -n "$f" ] && [ -n "$(tail -c1 "$f")" ] && missing="$missing $f"
done <<<"$texts"
if [ -n "$missing" ]; then bad "no newline at end of:$missing"; else ok "final newline ($(wc -l <<<"$texts") text files)"; fi

# --- shellcheck -------------------------------------------------------------
if have shellcheck; then
    shebang=$(git grep -I -n -E '^#!(/usr)?/bin/(env +)?(ba|da|k)?sh\b' -- ':!*.sh' | sed -n 's/:1:#!.*//p')
    mapfile -t sh < <({ git ls-files '*.sh'; printf '%s\n' "$shebang"; } | sed '/^$/d' | sort -u)
    if [ "${#sh[@]}" -lt 10 ]; then
        bad "shellcheck: only ${#sh[@]} scripts found -- the layout moved"
    elif shellcheck -S warning -f gcc "${sh[@]}"; then
        ok "shellcheck (${#sh[@]} scripts, $(wc -w <<<"$shebang") of them by shebang)"
    else
        bad "shellcheck found the above"
    fi
fi

# --- xmllint ----------------------------------------------------------------
if have xmllint; then
    mapfile -t xml < <(git ls-files '*_service' '*.xml')
    if [ "${#xml[@]}" -eq 0 ]; then bad "xmllint: no _service found -- the layout moved"
    elif xmllint --noout "${xml[@]}"; then ok "xmllint (${#xml[@]} files)"
    else bad "xmllint found the above"; fi
fi

# --- desktop files ----------------------------------------------------------
if have desktop-file-validate; then
    mapfile -t desk < <(git ls-files '*.desktop')
    # It exits 0 on warnings; hints ("can be extended with ...") are advice.
    out=$(desktop-file-validate "${desk[@]}" 2>&1)
    drc=$?
    if [ "${#desk[@]}" -eq 0 ]; then bad "desktop-file-validate: no .desktop found -- the layout moved"
    elif [ "$drc" -ne 0 ] || grep -qE ': (error|warning): ' <<<"$out"; then
        bad "desktop-file-validate:"; grep -E ': (error|warning): ' <<<"$out" >&2
    else ok "desktop-file-validate (${#desk[@]} files)"; fi
fi

# --- yamllint ---------------------------------------------------------------
if have yamllint; then
    mapfile -t yml < <(git ls-files '*.yml' '*.yaml' .yamllint)
    if yamllint -s -f parsable "${yml[@]}"; then ok "yamllint (${#yml[@]} files)"
    else bad "yamllint found the above"; fi
fi

# --- packit -----------------------------------------------------------------
if have packit; then
    # Its log is long and full of harmless dist-git warnings; shown only on failure.
    if out=$(packit validate . 2>&1); then ok "packit validate (.packit.yaml)"
    else bad "packit validate:"; printf '%s\n' "$out" | tail -20 >&2; fi
fi

if [ -n "$skipped" ]; then
    echo "lint: NOT RUN here (not installed):$skipped -- CI runs them" >&2
fi
exit $rc
