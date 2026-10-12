#!/bin/sh
# Build-time helper for the dreamdump package: two guards and the manpage.
#
#   dreamdump-build.sh verify  <source-dir> <source-tarball> <binary>
#   dreamdump-build.sh manpage <source-dir> <version>            > dreamdump.1
#
# The package repackages upstream's statically linked release binaries and
# carries the matching source tarball next to them. The source is not compiled
# (dreamdump needs Go >= 1.26, which most targets lack); it is READ, three ways:
#
# 1. PROVENANCE (verify). Upstream publishes no checksums. What it does publish
#    is checkable: Go stamps `vcs.revision` into every binary, and Forgejo's
#    archive carries the tagged commit in its pax header. They must be the same
#    40 hex digits, so the binary we ship was built from the source we ship. A
#    re-uploaded asset, or a tag moved after the build, fails here.
#
# 2. NO CAPABILITY NEEDED (verify, and again in manpage). The package ships
#    WITHOUT cap_sys_rawio. At 0.6.0 the whole code base sets exactly three SCSI
#    opcodes, INQUIRY (0x12), SET CD SPEED (0xBB) and READ CD (0xBE), all on the
#    kernel's unprivileged SG_IO list. Measured as a plain user on 2026-10-12,
#    red and green: proofs/dreamdump-optical-access-MEASURED-x86_64.md. The day
#    upstream adds a vendor command, every user would get EPERM, and dreamdump
#    reports a drive it cannot open as "Drive couldn't be found" with exit
#    status 0 -- invisible. The watcher bumps the version on its own, so this
#    check is what turns that into a red build and a fresh look at the cap.
#
# 3. THE MANPAGE (manpage). dreamdump ships no manpage, no --help and no
#    --version; run without a command it prints one usage line. So the page is
#    built from the source: command and option NAMES from the code, the drive
#    table from DRIVES.csv, the caveats from what the code does. The one-line
#    descriptions are ours -- a second copy of upstream behaviour -- so the
#    build fails the moment the code's option or command set differs from the
#    tables below, in either direction.
#
# Every lookup that comes back EMPTY fails. An empty answer here means the
# upstream layout moved, never "nothing to report".
set -eu

fail() { echo "dreamdump-build.sh: $*" >&2; exit 1; }

# Kernel opcodes dreamdump is KNOWN to send without privilege. Not the kernel's
# full list on purpose: any opcode new to dreamdump deserves a human look.
ALLOWED_OPCODES="0x12 0xBB 0xBE"

need() { for f in "$@"; do [ -f "$SRC/$f" ] || fail "$f missing in $SRC -- upstream layout changed"; done; }

check_opcodes() {
    sets=$(grep -rhoE --include='*.go' --exclude='*_test.go' \
               'OperationCode:[[:space:]]*[^,}[:space:]]+' "$SRC") \
        || fail "no OperationCode assignment found -- upstream layout changed"
    other=$(grep -rnE --include='*.go' --exclude='*_test.go' \
               '\.OperationCode[[:space:]]*=[^=]' "$SRC" || true)
    [ -z "$other" ] || fail "opcode set in a form this check does not read: $other"
    for v in $(printf '%s\n' "$sets" | sed -E 's/^OperationCode:[[:space:]]*//' | sort -u); do
        case $v in scsi.[A-Z]*) ;; *) fail "opcode '$v' is not a scsi.<CONST> -- read it by hand" ;; esac
        name=${v#scsi.}
        hex=$(grep -rhoE --include='*.go' "^[[:space:]]*${name}[[:space:]]*=[[:space:]]*0x[0-9A-Fa-f]+" "$SRC/scsi" \
                | sed -E 's/.*=[[:space:]]*0x/0x/' | tr 'a-f' 'A-F' | sed 's/^0X/0x/' | head -1)
        [ -n "$hex" ] || fail "cannot resolve $v to a value"
        case " $ALLOWED_OPCODES " in
            *" $hex "*) echo "opcode ok: $name = $hex" >&2 ;;
            *) fail "dreamdump now sends $name = $hex. This package ships WITHOUT cap_sys_rawio because every opcode it sent was on the kernel's unprivileged list. Check whether $hex is (scsi_cmd_allowed in drivers/scsi/scsi_ioctl.c), measure it as a plain user, then extend ALLOWED_OPCODES -- or add the capability and a proof-ledger row." ;;
        esac
    done
}

cmd=${1:-}
case $cmd in
verify)
    SRC=${2:?verify <source-dir> <source-tarball> <binary>}
    TARBALL=${3:?verify <source-dir> <source-tarball> <binary>}
    BIN=${4:?verify <source-dir> <source-tarball> <binary>}
    src_rev=$(gzip -dc "$TARBALL" | head -c 2048 | tr -c '0-9a-z=' '\n' \
                | sed -n 's/^comment=\([0-9a-f]\{40\}\)$/\1/p' | head -1)
    bin_rev=$(grep -aoE 'vcs\.revision=[0-9a-f]{40}' "$BIN" | head -1 | cut -d= -f2)
    [ -n "$src_rev" ] || fail "no commit id in the pax header of $TARBALL"
    [ -n "$bin_rev" ] || fail "no vcs.revision stamped in $BIN"
    [ "$src_rev" = "$bin_rev" ] || fail "binary built from $bin_rev, source tarball is $src_rev"
    grep -aq 'CGO_ENABLED=0' "$BIN" || fail "$BIN not built with CGO_ENABLED=0 -- no longer self-contained?"
    echo "provenance ok: $(basename "$BIN") and the source tarball are both $src_rev" >&2
    check_opcodes
    ;;
manpage)
    SRC=${2:?manpage <source-dir> <version>}
    VERSION=${3:?manpage <source-dir> <version>}
    need cli/option_parser.go cli/command_executor.go main.go DRIVES.csv
    check_opcodes

    # name|argument|description -- verified against the 0.6.0 source.
    OPTIONS=$(cat <<'EOF'
drive|DEVICE|Drive to read, as an absolute device path. Default: /dev/sr0.
image-path|DIR|Directory for the dump files, created if missing. Default: ./Game.
image-name|NAME|Base name of the dump files. Default: Game.
speed|N|Read speed as a CD multiple (N x 176 kB/s), capped at 48. Without it, or with 0, the drive's speed is left alone.
retries|N|Read attempts per section of the high-density area, up to 255. Default: 20.
cutoff|LBA|Sector at which reading the high-density area stops, between 44990 and 549152. Default: 446261.
read-offset|N|Read offset of the drive, in samples. Ignored for drives in the built-in list, which bring their own. Default: 0.
read-at-once|N|Sectors per READ CD command, at most 40 on Linux. Default: 40, or the drive's own value for drives in the built-in list.
sector-order|ORDER|Order in which the drive returns data, C2 and subchannel: DATA_C2, DATA_SUB, DATA_C2_SUB or DATA_SUB_C2 (the default). An unrecognised value selects DATA_C2_SUB. Drives in the built-in list use their own order unless --force-sector-order is given.
force-sector-order||Use --sector-order even for a drive in the built-in list.
force-qtoc||Split the tracks by the TOC read from the Q subchannel instead of the TOC in the disc header.
train||When the first section reads bad, run a training pass, reading backwards from sector 55000, before the next attempt.
EOF
)
    COMMANDS=$(cat <<'EOF'
disc|Dump the high-density area of the GD-ROM in --drive into --image-path, then split it into tracks.
split|Split an existing dump in --image-path into tracks again, without reading a drive.
EOF
)

    code_opts=$(grep -rhoE --include='*.go' --exclude='*_test.go' \
                    '(Find|Has)ArgumentString\("[a-z0-9-]+"\)' "$SRC/cli" \
                | sed -E 's/.*\("([^"]+)"\)/\1/' | sort -u) || true
    our_opts=$(printf '%s\n' "$OPTIONS" | cut -d'|' -f1 | sort -u)
    [ -n "$code_opts" ] || fail "no options found in cli/ -- upstream layout changed"
    [ "$code_opts" = "$our_opts" ] || fail "option set drifted. In the code but not here: $(printf '%s\n' "$code_opts" | grep -vxF "$our_opts" | tr '\n' ' ')-- here but not in the code: $(printf '%s\n' "$our_opts" | grep -vxF "$code_opts" | tr '\n' ' ')"

    code_cmds=$(grep -oE 'Name:[[:space:]]*"[a-z0-9-]+"' "$SRC/cli/command_executor.go" \
                | sed -E 's/.*"([^"]+)"/\1/' | sort -u) || true
    our_cmds=$(printf '%s\n' "$COMMANDS" | cut -d'|' -f1 | sort -u)
    [ -n "$code_cmds" ] || fail "no commands found in cli/command_executor.go -- upstream layout changed"
    [ "$code_cmds" = "$our_cmds" ] || fail "command set drifted: code has '$(echo $code_cmds)', this table has '$(echo $our_cmds)'"

    # What the binary calls itself (a compiled-in constant, not the tag) and how
    # it exits when the drive cannot be opened (first exit code; iota = 0).
    selfver=$(sed -n 's/^[[:space:]]*VERSION[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$SRC/main.go" | head -1)
    [ -n "$selfver" ] || fail "no VERSION constant in main.go"
    first_exit=$(awk '/^const \(/{f=1;next} f&&NF{print;exit}' "$SRC"/exit_codes/*.go)
    [ -n "$first_exit" ] || fail "no exit code constants found"

    rows=$(awk -F';' 'NR>1 && NF>=3 && $1!="" {print}' "$SRC/DRIVES.csv")
    [ -n "$rows" ] || fail "DRIVES.csv has no drive rows"

    if [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
        date=$(date -u -d "@$SOURCE_DATE_EPOCH" +%Y-%m-%d)
    else
        date=$(date -u +%Y-%m-%d)
    fi

    # roff: a line must not start with . or ' and a backslash must be doubled.
    esc() { sed -e 's/\\/\\e/g' -e "s/^\([.']\)/\\\\\&\1/" -e 's/-/\\-/g'; }

    cat <<EOF
.TH DREAMDUMP 1 "$date" "dreamdump $VERSION" "User Commands"
.SH NAME
dreamdump \- dump the high-density area of a Sega Dreamcast GD-ROM
.SH SYNOPSIS
.B dreamdump
.RI { disc | split }
.RI [ options ]
.SH DESCRIPTION
.B dreamdump
reads the high-density area of a Dreamcast GD-ROM (from sector 44990 on)
through raw SCSI READ CD commands, checks each section by reading it
repeatedly, and writes the result as track files.
MPF uses it as one of its dumping programs.
.PP
Options take the form
.BI \-\-name= value\fR;\fP
a space instead of the equals sign is not understood.
Every run prints a log to the terminal and to the dump directory.
.SH COMMANDS
EOF
    printf '%s\n' "$COMMANDS" | while IFS='|' read -r name desc; do
        printf '.TP\n.B %s\n%s\n' "$name" "$(printf '%s' "$desc" | esc)"
    done
    echo ".SH OPTIONS"
    printf '%s\n' "$OPTIONS" | while IFS='|' read -r name arg desc; do
        n=$(printf '%s' "$name" | esc)
        if [ -n "$arg" ]; then
            printf '.TP\n.BI \\-\\-%s= %s\n' "$n" "$arg"
        else
            printf '.TP\n.B \\-\\-%s\n' "$n"
        fi
        printf '%s\n' "$desc" | esc
    done

    cat <<'EOF'
.SH DRIVES
Reading the high-density area needs a drive that can be made to read past
the first session of a GD-ROM.
dreamdump has a built-in list of drives it recognises; for those it sets
sector order, read offset and sectors per command itself, and its log says
.I Known Drive found.
Any other drive is used with the defaults above, without a warning.
The table below is upstream's own record of tested drives
(drive, firmware, result, notes) at this version:
EOF
    # columns: drive;firmware;quality;tester;notes -- the tester is not printed
    printf '%s\n' "$rows" | while IFS=';' read -r drv fw q _ notes; do
        fw=${fw#\'}
        line="$drv (firmware $fw): $q"
        [ -n "${notes:-}" ] && line="$line. $notes"
        printf '.IP \\(bu 2\n%s\n' "$(printf '%s' "$line" | esc)"
    done

    cat <<'EOF'
.SH PERMISSIONS
dreamdump needs no root, no group membership and no file capability.
Every command it sends (INQUIRY, SET CD SPEED, READ CD) is one the kernel
lets any process send that can open the drive read-write, and
systemd-logind grants that to the user logged in at the local seat.
A drive that cannot be opened, for want of permission or because it does
not exist, is reported as
.IR "Drive couldn't be found or disc is incorrect" .
EOF

    case $first_exit in
        *=*iota*+*|*=*[0-9]*) ;;
        *=*iota*)
            name=$(printf '%s' "$first_exit" | sed -E 's/^[[:space:]]*([A-Za-z_]+).*/\1/')
            cat <<EOF
.SH EXIT STATUS
In this version a drive that cannot be found or opened ends the program with
exit status 0, the same as success: the exit code for that case,
.BR $name ,
is the first in upstream's list and therefore 0.
Check the log, not only the exit status.
EOF
            ;;
    esac

    if [ "$selfver" != "$VERSION" ]; then
        cat <<EOF
.SH VERSION
This is release $VERSION.
The program itself reports
.IR "build: $selfver" ,
because that constant was not updated for the release.
EOF
    fi

    cat <<'EOF'
.SH SEE ALSO
.BR mpf\-cli (1),
.BR redumper (1)
.PP
https://codeberg.org/MoriGM/dreamdump
.SH NOTES
dreamdump ships no manual page. This one is generated when the package is
built, from the dreamdump source of the same release; the build fails if
the source has an option, a command or a SCSI command this page does not
account for.
EOF
    ;;
*)
    fail "usage: dreamdump-build.sh verify <source-dir> <tarball> <binary> | manpage <source-dir> <version>"
    ;;
esac
