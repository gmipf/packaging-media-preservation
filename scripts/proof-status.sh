#!/usr/bin/env bash
#
# proof-status.sh — turn "I proved drive access works here" from a sentence into
# a machine-checked fact. Companion to status.sh, same spirit: it does not just
# state that something is proven, it names when the proof went SILENTLY stale.
#
# A drive-access proof (groupless, sudoless dumping) hangs on recipe fragments:
#   * node access (uaccess ACL)     -> the udev *.rules file + the %post/postinst
#                                       that reloads & re-triggers udev
#   * vendor SCSI (cap_sys_rawio)    -> Fedora  %caps() directive
#                                       Debian  setcap in postinst
#                                       openSUSE permissions-framework profile
#                                       (a here-doc in %install + %set_permissions)
#
# proof-ledger.tsv records, per proof, a fingerprint of exactly those fragments.
# This script recomputes it from the live tree and shouts if it moved. It is keyed
# on the MECHANISM, never the version: a redumper b731->b732 bump leaves the cap
# and udev fragments untouched, so the proof correctly still holds; touching the
# scriptlet moves the hash and voids it.
#
# Two independent checks:
#   1. DRIFT      — a ledgered proof whose fragments changed since it was recorded.
#   2. COVERAGE   — a mechanism fragment in the tree that NO proof entry references.
#                   This is the completeness half: you cannot add a %caps() or a
#                   *.rules file and leave it silently unproven.
#
# Three evidence states, and nothing else:
#   not-yet                        open obligation. Never proven. Not drift-checked.
#   log:<path>                     proven by a real red+green run; <path> must exist.
#   blocked:<version>:<path>       red is proven (the mechanism is delivered and
#                                  load-bearing), green is blocked BY UPSTREAM at
#                                  exactly <version>. Passes through: not counted as
#                                  open, not counted as proven. The moment the tool's
#                                  Version differs from <version> the entry FAILS
#                                  loudly -- upstream moved, the blockade must be
#                                  re-judged. That auto-recheck is the whole point:
#                                  a plain 'proven' would sit green forever and
#                                  nobody would ever measure it again.
#
# Both log: and blocked: MUST point at a file that exists. Until 2026-07-17 this
# field was never opened -- any string that was not 'not-yet' counted as a proof.
# Measured: a row pointing at log:proofs/DOES-NOT-EXIST.log reported "bewiesen &
# frisch" and the script exited 0. It verified the recipe it HASHES and not the
# proof it CLAIMS.
#
# Usage:
#   scripts/proof-status.sh            verify (drift + coverage); exit 1 on any problem
#   scripts/proof-status.sh --refresh  recompute mech_hash for every entry and rewrite
#                                      the ledger. Run this ONLY right after you have
#                                      RE-MEASURED and want to record the new mechanism
#                                      state (also update date + evidence by hand).
#
# Runs fully offline -- it only reads files in the repo. Safe in the sandbox.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
LEDGER="$REPO/scripts/proof-ledger.tsv"

# Guard: if REPO misresolves (e.g. this file gets sourced instead of run), the
# coverage find below would sweep the whole filesystem. Refuse unless the ledger
# is actually here.
[ -f "$LEDGER" ] || { echo "proof-status.sh: ledger not found at $LEDGER -- run it, do not source it." >&2; exit 2; }

hr()   { printf '\n\033[1m== %s\033[0m\n' "$1"; }
red()  { printf '\033[31m%s\033[0m\n' "$1"; }
grn()  { printf '\033[32m%s\033[0m\n' "$1"; }
ylw()  { printf '\033[33m%s\033[0m\n' "$1"; }

# --- Slice a .spec down to just the fragments that DELIVER a drive-access
# mechanism, so a version/changelog bump does not move the hash. Captured:
#   * real %caps() directives          (Fedora vendor cap) -- not %%caps, not comments
#   * permissions-framework profile     (openSUSE) -- the here-doc that writes
#     .../permissions.d/<tool> with `+capabilities`, plus %set_permissions /
#     %verify_permissions. Bare `cap_sys_rawio` is NOT a keyword (it appears in
#     prose); `+capabilities` is the profile syntax and does not.
#   * %post / %postun scriptlet bodies  (udev reload+trigger; openSUSE set_permissions)
mech_slice_spec() {
    awk '
      # %description AND %changelog are free prose that NAME the mechanism ("...the
      # permissions.d profile...", "- cap_sys_rawio granted through..."). Exclude
      # both, or (a) a doc reword and (b) EVERY version bump (which appends a
      # changelog entry) would flag drift -- the tool would cry wolf and, worse,
      # re-introduce the version coupling this whole design avoids.
      /^%(description|changelog)/                                     { prose=1; cap=0; next }
      /^%(post|postun)([[:space:]]|$)/                                { cap=1; prose=0; print; next }
      /^%[A-Za-z]/                                                    { cap=0; prose=0 }
      !prose && /%caps\(/ && $0 !~ /%%caps/ && $0 !~ /^[[:space:]]*#/ { print; next }
      !prose && /permissions\.d|\+capabilities|%set_permissions|%verify_permissions/ \
                                       && $0 !~ /^[[:space:]]*#/       { print; next }
      cap                                                            { print }
    ' "$1"
}

# --- Fingerprint one entry: concatenate its fragment sources (spec -> sliced,
# everything else -> whole) in listed order, sha256. Missing file -> loud MISS.
mech_hash() {   # $1 = comma-separated repo-relative files
    local files="$1" f abs
    {
        IFS=',' read -ra arr <<< "$files"
        for f in "${arr[@]}"; do
            abs="$REPO/$f"
            if [ ! -f "$abs" ]; then printf 'MISSING-FILE:%s\n' "$f"; continue; fi
            case "$f" in
                *.spec) mech_slice_spec "$abs" ;;
                *)      cat "$abs" ;;
            esac
        done
    } | sha256sum | cut -c1-16
}

# Read data rows (skip comments, blank, and the header line).
data_rows() { grep -v -e '^#' -e '^[[:space:]]*$' -e '^tool|lane|' "$LEDGER"; }

# ---------------------------------------------------------------- refresh mode
if [ "${1:-}" = "--refresh" ]; then
    tmp="$LEDGER.tmp"
    : > "$tmp"
    while IFS= read -r line; do
        case "$line" in
            '#'*|''|'tool|lane|'*) printf '%s\n' "$line" >> "$tmp"; continue ;;
        esac
        IFS='|' read -r tool lane prop date oldhash ev files <<< "$line"
        # Only compute for a freshly-proven row (mech_hash=AUTO). Leave not-yet
        # rows ('-') and already-recorded proofs untouched -- we do NOT silently
        # re-baseline a standing proof, that would hide the very drift we watch for.
        if [ "$oldhash" = "AUTO" ]; then h=$(mech_hash "$files"); else h="$oldhash"; fi
        printf '%s|%s|%s|%s|%s|%s|%s\n' "$tool" "$lane" "$prop" "$date" "$h" "$ev" "$files" >> "$tmp"
    done < "$LEDGER"
    mv "$tmp" "$LEDGER"
    grn "proof-ledger.tsv refreshed — mech_hash filled for AUTO (freshly proven) rows."
    exit 0
fi

# ---------------------------------------------------------------- verify mode
fail=0; proven=0; open=0; blocked=0

hr "Beweis-Ledger — offen vs. bewiesen, und Drift"
while IFS='|' read -r tool lane prop date hash ev files; do
    [ -n "${tool:-}" ] || continue
    tag="$tool/$lane/$prop"
    # not-yet: an OPEN obligation. Nothing to drift-check -- it was never proven.
    # Listed loudly so the backlog is visible, but it is NOT a failure.
    if [ "$ev" = "not-yet" ]; then
        ylw "  ☐ $tag — offen (im neuen System noch nicht bewiesen)"; open=$((open+1)); continue
    fi

    # Parse the evidence field. Unknown shape -> fail closed: a state we cannot
    # interpret must never silently pass as a proof.
    art=""; bver=""
    case "$ev" in
        log:*)     art=${ev#log:} ;;
        blocked:*) rest=${ev#blocked:}; bver=${rest%%:*}; art=${rest#*:}
                   if [ -z "$bver" ] || [ "$art" = "$rest" ]; then
                       red "  ✗ $tag — kaputtes blocked-Feld: '$ev' (erwartet blocked:<version>:<pfad>)"; fail=1; continue
                   fi ;;
        *)         red "  ✗ $tag — unbekannter evidence-Zustand: '$ev'"
                   red "      erlaubt: not-yet | log:<pfad> | blocked:<version>:<pfad>"; fail=1; continue ;;
    esac

    # The artifact must exist. This is the check whose absence let a phantom log
    # stand as a proof for two days.
    if [ ! -f "$REPO/$art" ]; then
        red "  ✗ $tag — Beleg-Artefakt fehlt: $art"; fail=1; continue
    fi

    # A blockade is pinned to an exact upstream version. Any change -- up OR down --
    # voids it; we compare for INEQUALITY on purpose, so no version-sorting logic
    # (and no tilde/Epoch subtlety) can get this wrong. The version source is the
    # tool's Fedora spec: the debian lane's mech_files is a postinst, which carries
    # no version at all, so the row cannot answer this question by itself.
    if [ -n "$bver" ]; then
        vspec="$REPO/fedora/$tool/$tool.spec"
        if [ ! -f "$vspec" ]; then
            red "  ✗ $tag — blocked, aber die Versionsquelle fehlt: fedora/$tool/$tool.spec"; fail=1; continue
        fi
        cur=$(awk '/^Version:[[:space:]]/{print $2; exit}' "$vspec")
        if [ -z "$cur" ]; then
            red "  ✗ $tag — blocked, aber fedora/$tool/$tool.spec hat keine lesbare Version:-Zeile"; fail=1; continue
        fi
        if [ "$cur" != "$bver" ]; then
            red "  ✗ $tag — $tool steht auf $cur, blockiert war $bver: UPSTREAM HAT SICH BEWEGT."
            red "      Blockade neu bewerten — messen und auf log:<pfad> setzen, oder blocked: auf $cur nachziehen."
            fail=1; continue
        fi
    fi

    live=$(mech_hash "$files")
    if [[ "$live" == MISSING-FILE:* ]] || printf '%s' "$live" | grep -q MISSING; then
        red "  ✗ $tag — Mechanismus-Datei fehlt: $files"; fail=1; continue
    fi
    if [ "$hash" = "AUTO" ]; then
        ylw "  ? $tag — als bewiesen markiert, aber mech_hash=AUTO -> --refresh"; fail=1; continue
    fi
    if [ "$live" != "$hash" ]; then
        red "  ✗ $tag — DRIFT: Rezept ($hash -> $live). Beweis veraltet, NEU MESSEN."
        fail=1; continue
    fi
    if [ -n "$bver" ]; then
        ylw "  ⊘ $tag — blockiert bei $tool $bver: Rot bewiesen, Grün fremdverschuldet ($art)"
        blocked=$((blocked+1))
    else
        grn "  ✓ $tag — bewiesen & frisch ($ev)"; proven=$((proven+1))
    fi
done < <(data_rows)

# ---------------------------------------------------------------- coverage
hr "Mechanismus-Abdeckung — kein Fragment ohne Beweis"
# Every proof's referenced files, flattened, for membership tests.
referenced=$(data_rows | cut -d'|' -f7 | tr ',' '\n' | sort -u)
is_ref() { printf '%s\n' "$referenced" | grep -qxF "$1"; }

# 1) every udev rule (node access) must be referenced
while IFS= read -r r; do
    rel=${r#$REPO/}
    is_ref "$rel" || { red "  ✗ udev-Regel ohne Beweis: $rel"; fail=1; }
done < <(find "$REPO" -name '*.rules' -not -path '*/.deb-out/*' | sort)

# 2) every REAL %caps() spec (Fedora vendor cap) must be referenced
while IFS= read -r s; do
    rel=${s#$REPO/}
    if awk '/%caps\(/ && $0 !~ /%%caps/ && $0 !~ /^[[:space:]]*#/{h=1} END{exit !h}' "$s"; then
        is_ref "$rel" || { red "  ✗ %caps()-Spec ohne Beweis: $rel"; fail=1; }
    fi
done < <(find "$REPO/fedora" -name '*.spec' | sort)

# 3) every setcap postinst (Debian vendor cap) must be referenced
while IFS= read -r p; do
    rel=${p#$REPO/}
    if grep -q 'setcap' "$p"; then
        is_ref "$rel" || { red "  ✗ setcap-postinst ohne Beweis: $rel"; fail=1; }
    fi
done < <(find "$REPO/ubuntu" -name '*postinst' -not -path '*/.deb-out/*' | sort)

# 4) every openSUSE spec with a REAL %set_permissions directive (permissions-
#    framework vendor cap) must be referenced. Anchored ^%set_permissions, one %,
#    so the escaped %%set_permissions in mpf's comments/changelog does NOT count --
#    mpf carries no cap on any lane, and a naive `grep -l` would falsely demand one.
while IFS= read -r s; do
    rel=${s#$REPO/}
    if awk '/^%set_permissions[[:space:]]/{h=1} END{exit !h}' "$s"; then
        is_ref "$rel" || { red "  ✗ openSUSE permissions-Spec ohne Beweis: $rel"; fail=1; }
    fi
done < <(find "$REPO/opensuse" -name '*.spec' | sort)

grn "  Abdeckung geprüft: udev-Regeln · Fedora %caps() · Debian setcap · openSUSE %set_permissions"

# ---------------------------------------------------------------- verdict
hr "Fazit"
printf '  bewiesen & frisch: %d   blockiert (upstream): %d   offen (noch zu messen): %d\n' \
       "$proven" "$blocked" "$open"
if [ "$fail" -eq 0 ]; then
    grn "Kein Drift, jedes Mechanismus-Fragment hat eine Ledger-Zeile."
    [ "$open" -gt 0 ] && ylw "  $open offen — im neuen System noch nichts bewiesen; das ist die Backlog, kein Fehler."
    [ "$blocked" -gt 0 ] && ylw "  $blocked blockiert — Rot bewiesen, Grün wartet auf Upstream. Fällt automatisch auf, sobald sich die Version bewegt."
    exit 0
else
    red "Ein Beweis ist veraltet, unfertig (AUTO) oder ein Fragment fehlt im Ledger — oben."
    exit 1
fi
