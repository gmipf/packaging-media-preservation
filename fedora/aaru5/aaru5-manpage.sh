#!/bin/sh
# Build-time aaru5(1) command-reference generator.
#
# Same idea as aaru-manpage.sh (the v6 generator): walk the shipped binary's
# `--help` tree at build time and splice the live reference into a curated
# template, so the command/option reference can never drift from the binary
# that actually ships. A HAND-MAINTAINED command list would go stale silently;
# a generated one cannot.
#
# But Aaru 5 is a different CLI generation from v6 and the v6 parser does NOT
# work on it -- measured, not assumed:
#
#   v6 (Spectre.Console.Cli)     Aaru 5 (System.CommandLine)
#   ------------------------     ---------------------------
#   COMMANDS:                    Commands:
#   four-space indented entries  two-space indented entries
#   bare command names           comma-separated aliases: "database, db"
#   config ~/.config/Aaru.json   config ~/.config/Aaru.xml (DicSettings)
#
#   Usage: aaru5-manpage.sh <aaru-binary> <template.in> [fallback-version] > aaru5.1
#
set -eu

AARU=$1
TEMPLATE=$2
FALLBACK_VERSION=$(printf '%s' "${3:-}" | tr '~' '-')

# Private throwaway HOME, auto-removed. On a fresh HOME Aaru 5 opens its
# interactive GDPR consent dialog and, with no TTY on stdin, aborts with
# SIGABRT -- the build would die. Pre-seeding the settings with a saturated
# GdprCompliance level keeps the wizard from ever running. Aaru 5 stores this
# as XML (DicSettings), not the JSON v6 uses.
WORKDIR=$(mktemp -d "${TMPDIR:-/tmp}/aaru5-manpage.XXXXXX")
trap 'rm -rf "$WORKDIR"' EXIT
GENHOME=$WORKDIR/home
mkdir -p "$GENHOME/.config"
cat > "$GENHOME/.config/Aaru.xml" <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<DicSettings xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <EnableDecryption>false</EnableDecryption>
  <GdprCompliance>2147483647</GdprCompliance>
  <SaveReportsGlobally>false</SaveReportsGlobally>
  <ShareReports>false</ShareReports>
  <Stats>
    <BenchmarkStats>false</BenchmarkStats>
    <CommandStats>false</CommandStats>
    <DeviceStats>false</DeviceStats>
    <FilesystemStats>false</FilesystemStats>
    <FilterStats>false</FilterStats>
    <MediaImageStats>false</MediaImageStats>
    <MediaScanStats>false</MediaScanStats>
    <MediaStats>false</MediaStats>
    <PartitionStats>false</PartitionStats>
    <ShareStats>false</ShareStats>
    <VerifyStats>false</VerifyStats>
  </Stats>
</DicSettings>
XML

# LC_ALL=C pins the .NET UI culture to the invariant (English) resources, so the
# section headers we parse on and the emitted text are the same on every build
# host regardless of its locale. TERM=dumb plus redirected stdout keeps the
# output ANSI-free.
aaru_help() {
    HOME=$GENHOME LC_ALL=C LANG=C TERM=dumb "$AARU" "$@" --help 2>/dev/null
}

# First run on a fresh HOME builds the device/statistics database and prints
# chatter to stdout. Run once and throw it away so the captured blocks are clean.
aaru_help >/dev/null 2>&1 || true

# Render a captured help block (stdin) as a roff subsection in a literal display.
# Inside .EX/.EE we still neutralise lines that begin with a roff control
# character (. or ') and render backslashes literally.
emit_block() {
    if [ -z "$1" ]; then
        printf '.SS aaru5\n'
    else
        printf '.SS aaru5 %s\n' "$1"
    fi
    printf '.EX\n'
    expand | sed -e 's/[[:space:]]*$//' \
                 -e 's/\\/\\e/g' \
                 -e 's/^[.'\'']/\\\&&/'
    printf '.EE\n'
    # No trailing .P here: a paragraph macro directly before the next .SS has no
    # content, and mandoc rightly warns ("skipping paragraph macro: PP empty").
    # .SS already breaks and spaces the section. (The v6 generator still emits
    # one -- same warning, worth cleaning up there too.)
}

# Sub-command names from a help block's "Commands:" section. Entries are indented
# exactly two spaces; wrapped description lines are indented far deeper and so do
# not match.
#
# Entries carry comma-separated aliases, and upstream is not consistent about the
# order -- "database, db" leads with the long name, "fi, filesystem, fs" and
# "m, media" lead with the short one. Taking the first field would therefore
# produce `aaru5 fi info` in one place and `aaru5 database stats` in another. We
# pick the LONGEST alias instead: every alias invokes the same command, so the
# choice is purely about what reads well on the page, and one name per subtree
# keeps the walk from visiting it twice.
parse_subcommands() {
    awk '
        /^Commands:/  { in_cmds = 1; next }
        /^[A-Za-z]/   { in_cmds = 0 }
        in_cmds && /^  [^ ]/ {
            line = $0
            sub(/^  /, "", line)        # drop the entry indent
            sub(/  +.*$/, "", line)     # drop the description (starts after 2+ spaces)
            n = split(line, alias, /, */)
            best = alias[1]
            for (i = 2; i <= n; i++)
                if (length(alias[i]) > length(best)) best = alias[i]
            # Some entries carry an argument placeholder ("remote <host>").
            # Keep the command name only -- feeding "<host>" back into the walk
            # made aaru exit non-zero, which under `set -e` killed the whole
            # generator mid-tree and produced an EMPTY manpage rather than a
            # merely incomplete one.
            sub(/[ \t].*$/, "", best)
            print best
        }
    '
}

# Depth-generic walk. Each node's help is fetched ONCE (a .NET cold start costs
# real time) and reused both for emitting and for discovering children.
walk() {
    # `|| true`: a node whose --help exits non-zero must not take the whole
    # generator down with it under `set -e`. We would rather ship a page missing
    # one subsection than no page at all.
    help=$(aaru_help "$@" || true)
    [ -n "$help" ] || return 0
    printf '%s\n' "$help" | emit_block "$*"
    for sub in $(printf '%s\n' "$help" | parse_subcommands); do
        walk "$@" "$sub"
    done
}

# Write the reference to a side file so the assembly step can inject it verbatim
# (awk -v would mangle the roff escapes).
#
# Probe first whether the prebuilt binary actually runs in this build root: a
# newer distribution can ship runtime libraries whose SONAMEs this self-contained
# .NET 5 binary was never linked against. If it will not start we still emit the
# curated page, with a short note instead of the generated reference, rather than
# failing the whole build.
REFFILE=$WORKDIR/cmdref.roff
if HOME=$GENHOME LC_ALL=C LANG=C TERM=dumb "$AARU" --version >/dev/null 2>&1; then
    walk > "$REFFILE"
    # --version prints "5.4.2+<sha>.<sha>"; keep the release, drop the build metadata.
    VERSION=$(HOME=$GENHOME LC_ALL=C LANG=C TERM=dumb "$AARU" --version 2>/dev/null \
              | sed -e 's/+.*//' -e 's/[[:space:]]*$//' || true)
else
    cat > "$REFFILE" <<'ROFF'
The per\-command reference is not embedded in this build of the manpage:
the prebuilt
.B aaru5
binary does not run in this build environment, so its
.B \-\-help
output could not be captured. Run
.B aaru5 \fICOMMAND\fB \-\-help
on the installed system for the complete command and option reference.
ROFF
    VERSION=$FALLBACK_VERSION
fi
[ -n "${VERSION:-}" ] || VERSION=unknown

# Reproducible date: the source epoch, never the build wall clock.
DATE=$(date -u -d "@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y-%m-%d 2>/dev/null || date -u +%Y-%m-%d)

awk -v reffile="$REFFILE" -v version="$VERSION" -v date="$DATE" '
    { gsub(/@VERSION@/, version); gsub(/@DATE@/, date) }
    $0 == "@AARU5_COMMAND_REFERENCE@" {
        while ((getline line < reffile) > 0) print line
        next
    }
    { print }
' "$TEMPLATE"
