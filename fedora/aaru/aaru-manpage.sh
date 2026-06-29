#!/bin/sh
# Build-time aaru(1) command-reference generator.
#
# Aaru ships no manpage and has no native man/roff generator, but its
# Spectre.Console.Cli `--help` is structured and — when stdout is not a
# TTY — ANSI-free and width-stable at 80 columns. We walk the command
# tree at %build time and splice the live help into the curated manpage
# template, so the COMMAND/OPTIONS reference can never drift from the
# binary that actually ships, without asking upstream for anything.
#
#   Usage: aaru-manpage.sh <aaru-binary> <template.in>  > aaru.1
#
set -eu

AARU=$1
TEMPLATE=$2
MARKER='@AARU_COMMAND_REFERENCE@'

# Private throwaway work dir (HOME + side files), auto-removed on exit.
# Aaru creates a SQLite database and writes ~/.config/Aaru.json on first
# run; a pre-seeded config with a saturated GdprCompliance level keeps
# the interactive GDPR / `configure` wizard from blocking the
# non-interactive build.
WORKDIR=$(mktemp -d "${TMPDIR:-/tmp}/aaru-manpage.XXXXXX")
trap 'rm -rf "$WORKDIR"' EXIT
GENHOME=$WORKDIR/home
mkdir -p "$GENHOME/.config"
cat > "$GENHOME/.config/Aaru.json" <<'JSON'
{
  "EnableDecryption": false,
  "GdprCompliance": 2147483647,
  "SaveReportsGlobally": false,
  "ShareReports": false
}
JSON

# `aaru <path...> --help`. LC_ALL=C pins the .NET UI culture to the
# invariant (English) resources so the section headers we parse on
# (COMMANDS:/OPTIONS:) and the emitted text are stable across build
# hosts regardless of their locale. ANSI is already stripped when
# stdout is redirected.
aaru_help() {
    HOME=$GENHOME LC_ALL=C LANG=C TERM=dumb "$AARU" "$@" --help 2>/dev/null
}

# Warm-up: the very first invocation on a fresh HOME prints database
# build chatter ("Creating main database", "Added N USB vendors", ...)
# to stdout. Run once and discard so the captured help blocks are clean.
aaru_help >/dev/null 2>&1 || true

# Render a captured help block (stdin) as a roff subsection inside a
# literal display. Within .EX/.EE we still neutralise lines that begin
# with a roff control character (. or '\'') and render backslashes
# literally.
emit_block() {
    if [ -z "$1" ]; then
        printf '.SS aaru\n'
    else
        printf '.SS aaru %s\n' "$1"
    fi
    printf '.EX\n'
    expand | sed -e 's/[[:space:]]*$//' \
                 -e 's/\\/\\e/g' \
                 -e 's/^[.'\'']/\\\&&/'
    printf '.EE\n'
    printf '.P\n'
}

# Sub-command names advertised in a help block's COMMANDS: section. A
# command entry is a line indented exactly four spaces; its first token
# is the command name (argument placeholders such as <device-path>
# follow it). Wrapped description lines are indented deeper and ignored
# by the exact-four-space match.
parse_subcommands() {
    awk '
        /^COMMANDS:/           { in_cmds = 1; next }
        /^[A-Z]/               { in_cmds = 0 }
        in_cmds && /^    [^ ]/ { print $1 }
    '
}

# Depth-generic tree walk. Each node'\''s help is fetched ONCE (an aaru
# invocation costs several seconds of .NET cold-start) and reused for
# both emitting and discovering children.
walk() {
    help=$(aaru_help "$@")
    printf '%s\n' "$help" | emit_block "$*"
    for sub in $(printf '%s\n' "$help" | parse_subcommands); do
        walk "$@" "$sub"
    done
}

# Generate the reference block to a side file so the assembly step can
# inject it verbatim (awk -v would mangle the roff escapes).
REFFILE=$WORKDIR/cmdref.roff
walk > "$REFFILE"

# Stamp the real shipped version (drop the +commit build-metadata) and a
# date into .TH, then splice the reference in at the marker line.
VERSION=$(HOME=$GENHOME LC_ALL=C LANG=C TERM=dumb "$AARU" --version 2>/dev/null | sed -e 's/+.*//' -e 's/[[:space:]]*$//' || true)
[ -n "${VERSION:-}" ] || VERSION=unknown
DATE=$(date -u -d "@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y-%m-%d 2>/dev/null || date -u +%Y-%m-%d)

awk -v reffile="$REFFILE" -v version="$VERSION" -v date="$DATE" '
    { gsub(/@VERSION@/, version); gsub(/@DATE@/, date) }
    $0 == "@AARU_COMMAND_REFERENCE@" {
        while ((getline line < reffile) > 0) print line
        next
    }
    { print }
' "$TEMPLATE"
