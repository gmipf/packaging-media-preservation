# EL: redumper vs redumper732 build-id collision — RED baseline

Measured 2026-07-16 on `test-centos` (CentOS Stream 10, kernel 6.12.0-248.el10),
groupless user (`gmipf wheel`), EPEL + COPR gmipf/media-preservation enabled per
the README canon.

## RED (before the fix)

    $ sudo dnf install -y redumper aaru aaru5 discimagecreator redumper-gui mpf-cli mpf-check
    ...
    Fehler: Transaktionstest fehlerhaft:
      Datei /usr/lib/.build-id/db/ea49d3a61bf33c19f2e3b7bff5cf8fb66940ce kollidiert
      zwischen den versuchten Installationen von redumper-732-1.el10.x86_64 und
      redumper732-732-1.el10.x86_64
    dnf exit=1     # nothing installed

`mpf-cli` recommends `redumper732`; the rolling `redumper` is at build 732 — same
upstream binary, same build-id, same link path, two owners.

## Why Fedora could never show it

Both specs already set `%global debug_package %{nil}`. Measured on the published
artifacts of the same commit:

| package | fedora-43 | epel-10 |
|---|---|---|
| redumper-732 / redumper732-732 | 0 build-id files | 3 each, identical path |
| aaru, mpf-cli (have `_build_id_links none`) | 0 | 0 |
| redumper729, redumper-gui, discimagecreator | — | 2 / 2 / 8 |

Fedora's rpm drops the links together with debug_package; EL's does not.

## Why the distributions differ -- measured 2026-07-16

Not the distro's macro: Fedora and EL set the *same* `_build_id_links`. What
differs is the rpm generation.

| | rpm | `%_build_id_links` | `/usr/lib/.build-id` on a stock install |
|---|---|---|---|
| Fedora 43 | **6.0.1** | compat | -- |
| CentOS Stream 10 | **4.19.1.1** | compat | **4634 entries** |
| openSUSE Leap 16.0 | 4.20.1 | **alldebug** | **does not exist** |

Fedora is protected by rpm 6, not by a macro. Worth knowing: a Fedora-only test
keeps hiding this class of bug for as long as EL stays on rpm 4.

## openSUSE was never affected -- and the proof was an accident

openSUSE defaults to `alldebug`: build-id links only ever go into the debuginfo
subpackage. With `debug_package %{nil}` there is no debuginfo package, so there
is nowhere for them to go. Across an entire Leap 16.0 install not one main
package carries a build-id file -- `/usr/lib/.build-id` does not exist at all,
where EL 10 has 4634 entries.

The artifact-level proof turned up by accident: `test-openSUSE` still had the
*pre-fix* OBS builds installed side by side, left over from the 2026-07-14 drive
proofs (today's builds are lp160.39.1 / lp160.21.1):

    redumper-732-lp160.27.1.x86_64      <- pre-fix
    redumper732-732-lp160.11.1.x86_64   <- pre-fix

On EL the same spec pair at the same upstream build could not be co-installed at
all. The build-id entries are symlinks pointing at *different* targets, which is
a genuine conflict rather than a duplicate file rpm would tolerate. These two
coexisted -- so the openSUSE builds never shipped them.

An attempt to reproduce the collision with a throwaway package in the VM FAILED
and proves nothing: openSUSE creates debuginfo from the OBS build root, so a
local `rpmbuild` never starts the machinery. The control stayed green across
four variants (alldebug / none / compat, debug_package on and off) and through
`_build_create_debug`. Four zeroes from a test that cannot go red are not a
result; the coexistence artifact above is the whole evidence.

Coexistence re-verified against the real OBS repo (2026-07-16): all nine
packages in one transaction, `zypper` exit=0, 0 build-id files per package. The
repackaged binaries also ran on openSUSE for the first time on record --
`redumper` b732, `redumper729` b729, `redumper732` b732.

## GREEN (after `_build_id_links none`, same VM, same command)

    $ sudo dnf clean all
    $ sudo dnf install -y redumper aaru aaru5 discimagecreator redumper-gui mpf-cli mpf-check
    ...
    Fertig!
    dnf exit=0

    $ rpm -q redumper redumper729 redumper732 ...
    redumper-732-2.el10.x86_64          <- the colliding pair, now side by side
    redumper732-732-2.el10.x86_64
    redumper729-729-2.el10.x86_64
    aaru-6.0.0~beta.1-2.el10.x86_64
    aaru5-5.4.2-7.el10.x86_64
    discimagecreator-20260703121302.efa7d482-4.el10.x86_64
    redumper-gui-1.0.1-6.el10.x86_64
    mpf-cli / mpf-check-3.8.3~20260715133029.4c0f474a-1.el10.x86_64

Cause gone -- build-id files per installed package: redumper 0, redumper729 0,
redumper732 0, redumper-gui 0, discimagecreator 0, aaru 0.

Nothing else broke. Swept mechanically (every file of every package via `rpm -ql`,
not a hand-written list -- which would have missed it: redumper lives at
/usr/bin/redumper, not under /usr/lib64/<tool>/ like aaru):

    /usr/bin/redumper cap_sys_rawio=ep
    /usr/bin/redumper729 cap_sys_rawio=ep
    /usr/bin/redumper732 cap_sys_rawio=ep
    /usr/libexec/discimagecreator/DVDAuth.out cap_sys_rawio=ep
    /usr/libexec/discimagecreator/DiscImageCreator.out cap_sys_rawio=ep
    /usr/lib64/aaru/aaru cap_sys_rawio=ep
    /usr/lib64/aaru5/aaru cap_sys_rawio=ep

redumper-gui and mpf carry none, deliberately (a GUI with file caps is
non-dumpable and every portal file dialog dies).

## Also measured here for the first time: EL runtime

We have shipped epel-8/9/10 for months without ever running an EL artifact.
On CentOS Stream 10 the repackaged binaries do start, and the generated manpages
are not the silent fallback:

    redumper --version    -> redumper (build: b732)
    redumper729           -> redumper (build: b729)
    redumper732           -> redumper (build: b732)
    aaru5 --version       -> runs (first-run DB chatter)
    man redumper 146 lines | aaru 1106 | aaru5 855 | discimagecreator 133

NOT covered here: drive access. That needs the Plextor/NEC passed through to this
VM; the ledger's fedora %caps proofs cover the MECHANISM, which EPEL shares with
Fedora (same spec, same %caps directive).
