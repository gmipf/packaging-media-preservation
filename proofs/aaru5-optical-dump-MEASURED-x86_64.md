# aaru5 on optical media — MEASUREMENT REPORT, not a ledger proof (fedora, x86_64)

> ⚠️ **This is deliberately NOT a `proven` artifact and carries no ledger row.**
> A proof needs a RED half, and this one cannot have a real red: the capability is
> not load-bearing here, so stripping it changes nothing. Calling that a red half
> would be exactly the "green that was never able to fail" this ledger exists to
> keep out. Filed as a measurement so the finding does not live only in a commit
> message — and named `MEASURED`, not `.log`, because the filename is a claim too.
>
> 🔴 **The larger finding: for aaru5 on OPTICAL media our recipe supplies no
> mechanism of its own at all.** Our only udev rule matches `fd[0-9]*` (floppy);
> the ACL on `/dev/sr*` comes from systemd's own `70-uaccess.rules` (`ID_CDROM==1`),
> and the reading is done with kernel-whitelisted SCSI opcodes. So there is nothing
> of ours left to prove for this path — which is why the row was never closeable.
> It was asking about a mechanism that does not exist for this use case.

# Measured 2026-07-21, test-fedora (Fedora 44, KDE autologin), Plextor PX-760A over
# USB passthrough, 7-track audio CD. Package aaru5-5.4.2-8.fc44 from COPR
# gmipf/media-preservation, installed from the real repository.
#
# This replaces the retracted `vendor-cap` claim for aaru5. Why the row was
# reframed rather than closed: see proofs/aaru5-vendor-cap-RETRACTED-x86_64.md.
# Short version: cap_sys_rawio is NOT load-bearing for aaru5 on optical media, so
# a red/green A/B on the capability cannot go red. What IS provable, and what the
# package actually promises, is this: a user in no special group, without sudo,
# gets a complete dump.

== PRECONDITIONS (a test that cannot fail proves nothing) ==
groups:                    gmipf wheel          <- no cdrom, no disk, no plugdev
/etc/udev/rules.d:         no hand-written floppy/cdrom rules  <- nothing masking the test
loginctl:                  seat0 present (autologin)           <- uaccess needs a seat
getfacl /dev/sr1:          user:gmipf:rw-                      <- uaccess ACL from the package rule
getcap:                    /usr/lib64/aaru5/aaru cap_sys_rawio=ep
rpm -qf:                   aaru5-5.4.2-8.fc44.x86_64

== GREEN: dump with a real terminal ==
script -qec "stty rows 50 cols 200; /usr/bin/aaru5 media dump /dev/sr1 ~/proof/cd.aaruf" /dev/null

  cd.aaruf        299620825 bytes
  0 sectors could not be read.
  317 subchannels could not be read.
  Reading CD-Text from Lead-In
  Drive reading offset is 120 bytes (30 samples).

The terminal is the point. Without a usable TERM this exact command dies at the
first progress bar (Console.WindowWidth 0 or -1 -> new String(' ', -1)), which is
what produced five days of a wrong "aaru5 cannot dump optical media" claim. Every
earlier run went over ssh, which carries no TERM.

== COUNTER-RUN: same command, capability REMOVED ==
sudo setcap -r /usr/lib64/aaru5/aaru   (verified empty before running: getcap -> '')

  cd.aaruf        299620907 bytes
  0 sectors could not be read.

Identical outcome. The 82-byte difference is metadata/timestamps, not content. So
the capability is NOT what makes this work, and this counter-run is reported as
what it is -- a refutation of the old premise, not a red half.

== WHY: the opcodes aaru5 actually issues (strace -e trace=ioctl, uncapped) ==
  791 SG_IO calls in the traced window
  766  0xBE  READ CD              <- the bulk of the dump; kernel SG whitelist
    6  0x46  GET CONFIGURATION
    6  0x43  READ TOC/PMA/ATIP    <- this is how it reads CD-Text, not a vendor command
    3  0x12  INQUIRY
    2  0xBB  SET CD SPEED
    2  0x5A  MODE SENSE(10)
    2  0x1A  MODE SENSE(6)
    1  0xA8  READ(12)
    1  0x51  READ DISC INFORMATION
    1  0x00  TEST UNIT READY
    1  0x85  ATA PASS-THROUGH(16) -> EPERM without the cap, and IGNORED by aaru5

  NOT ONE opcode >= 0xC0. Only those reach blk_verify_command, which is why
  redumper (Plextor D8 = 0xD8) genuinely needs cap_sys_rawio and aaru5 does not.
  The single cap-gated call is 0x85, issued once, denied, and consequence-free:
  ioctl(182, SG_IO, {... cmd_len=16, cmdp="\x85\x08\x0e\x00\x00\x00\x01\x00\x00
  \x00\x00\x00\x00\x00\xa1\x00" ...}) = -1 EPERM (Operation not permitted)

  Two independent measurements agree: the trace shows no vendor opcode, AND the
  uncapped full dump had 0 unreadable sectors. If a vendor command were needed
  later in the dump, the second one would have failed.

== WHAT IS PROVEN HERE ==
  A user with no group membership and no sudo, on a package installed from the
  real repository, dumps an audio CD completely (299 MB, 0 unreadable sectors).
  The uaccess ACL from our udev rule delivers the node access. That is the
  package's promise, and it is measured, not inferred.

== WHAT IS EXPLICITLY NOT PROVEN ==
  Whether cap_sys_rawio matters for aaru5 on ATA/SATA devices, where
  ATA PASS-THROUGH is the whole point rather than an optional extra. No such
  device was attached. The capability stays in the package for that reason, and
  that obligation is tracked as its own `not-yet` row rather than being quietly
  folded into this one.

== CLEANUP ==
  dnf reinstall aaru5 -> getcap restored to cap_sys_rawio=ep (verified)
  USB device detached --live; `virsh dumpxml --inactive | grep -c hostdev` -> 0
