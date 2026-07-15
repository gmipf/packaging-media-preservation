# aaru5 vendor-cap — BLOCKED on the empirical A/B (not a packaging defect)

Status: `aaru5|*|vendor-cap` stays **not-yet** in the ledger — but for a reason worth
recording, so nobody re-litigates it blindly.

## What is proven
- The cap IS delivered: `getcap /usr/lib64/aaru5/aaru -> cap_sys_rawio=ep`, owned by
  `aaru5-5.4.2-5.fc44` (fedora). The delivery mechanism (Fedora %caps) is proven
  load-bearing on this exact kernel/drive by redumper/discimagecreator and aaru 6.0.
- strace of the uncapped aaru5 shows it DOES issue a cap-gated opcode: an
  `ATA PASS-THROUGH(16)` (0x85) SG_IO that returns EPERM without the cap. So the cap
  gates real aaru5 drive access.

## Why the clean D8 A/B could not be run (2026-07-15, mixed CD)
aaru5 5.4.2 **crashes** on the mixed-mode CD (track1 data + track2 audio) BEFORE it
reaches the Plextor D8 read — with AND without the cap (so the crash is cap-independent,
an upstream bug):

    Unhandled exception. System.ArgumentOutOfRangeException: count ('-1') must be a
    non-negative value.  ... at System.String.Ctor(Char c, Int32 count)
    ... at Aaru.Commands.Media.DumpMediaCommand.Invoke(...)

- Reproduced with default options and with `--fix-offset false`.
- strace: only 6 SG_IO before the crash (INQUIRY 0x12, GET CONFIGURATION 0x46,
  ATA PASS-THROUGH 0x85) — **no 0xD8 ever emitted**.
- First run also hit the GDPR/configure wizard (ReadKey without a console); worked
  around by setting `~/.config/Aaru.xml` `<GdprCompliance>1</GdprCompliance>`. The
  crash above persists after that.

## Pure audio CD tried too (2026-07-15) -- still blocked
A pure 20-track audio CD (TRACK_COUNT_AUDIO=20, no data track) was inserted to force
aaru5's Plextor D8 audio path. Result:
- `aaru5 media dump` -> SAME crash (count '-1' in DumpMediaCommand.Invoke), before any read.
- `aaru5 media scan` -> SAME crash (count '-1' in Aaru.Core.Devices.Scanning.MediaScan.Scsi()).
- strace of `media scan` (uncapped): 50 SG_IO, opcodes 0x00/08/0b/12/25/28/2b/46/85/88/a8 --
  standard reads (READ 6/10/12/16), **no 0xD8 at all**; 2 EPERM (incl. 0x85 ATA passthrough).
So the crash is disc-type- AND command-independent, and aaru5 5.4.2 does not even emit the
Plextor D8 for audio via scan. The cap is still demonstrably load-bearing (0x85 EPERM), but
there is no clean GREEN state (aaru5 crashes with the cap too).

## To close it later
(a) a fixed aaru5 build whose `media dump`/`scan` does not crash on optical CDs, or
(b) accept aaru5 vendor-cap as delivery-proven (getcap on all 3 lanes + the lane mechanism
proven load-bearing by redumper/dic/aaru + aaru5's own 0x85 gate). A different disc will NOT
help -- tried data, mixed and pure-audio, all crash. Kept **not-yet** to honor "measure,
don't infer". Same blocker confirmed on fedora, opensuse and debian (same aaru5 5.4.2 code).
