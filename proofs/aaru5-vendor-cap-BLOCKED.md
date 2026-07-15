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

## To close it later
Either (a) a data+audio disc that aaru5 5.4.2 can dump (reaching its Plextor D8 offset
detection), or (b) a fixed aaru5 build, or (c) accept aaru5 vendor-cap as
delivery-proven (getcap + fedora mechanism proven by siblings + the 0x85 gate above).
Decision deferred to the maintainer; kept **not-yet** to honor "measure, don't infer".

Same blocker is expected on the opensuse and debian aaru5 lanes (same aaru5 5.4.2 code).
