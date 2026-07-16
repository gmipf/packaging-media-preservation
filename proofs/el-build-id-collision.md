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
