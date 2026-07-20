# aaru5 vendor-cap — RETRACTED 2026-07-20: the blockade was MY measurement setup

> 🔴 **THE CENTRAL CLAIM OF THIS FILE IS REFUTED.** It said aaru5 5.4.2 cannot dump
> optical media on Linux — "a pure aaru5 5.4.2 code bug", "green owed by upstream",
> "a different disc will NOT help". None of that is true. aaru5 5.4.2 dumps optical
> media fine. What crashed was the measurement.
>
> **Cause** (found by Boot 6.1, 2026-07-20, hardware A/B on the same drive):
> `Aaru.Progress.ClearCurrentConsoleLine()` builds `new String(' ', Console.WindowWidth - 1)`.
> With stdout redirected there is no terminal, `WindowWidth` is **0**, so the count is
> **-1** and .NET throws `ArgumentOutOfRangeException` — at the FIRST progress bar,
> before the first read. Same disc, same drive, same command, only the terminal
> differs: redirected → crash after ~1 s; `script -qec "stty rows 50 cols 200; ..."`
> → **299,620,893 byte dump**.
>
> ⚠️ A PTY alone is not enough to counter-measure: without an explicitly set window
> size `WindowWidth` stays 0 and the crash reproduces, which would have "confirmed"
> the wrong conclusion a second time.
>
> ⭐ **The evidence was in THIS FILE from the start and I read past it.** The stack
> trace below names `System.String.Ctor(Char c, Int32 count)` with -1 — literally
> `new String(' ', WindowWidth - 1)`. The section below even records "ReadKey
> **without a console**" for the GDPR wizard: I noticed the missing terminal,
> attributed it to the wizard, worked around it, and never connected it to the crash
> three lines further down. And "crashes AS ROOT with ALL capabilities" should have
> been the tell — a privilege-independent crash before any I/O is not a drive
> problem.
>
> ⭐ **Three agreeing measurements on three distributions did not make this safer,
> they made it more convincing.** All three ran the same broken harness. Reproducing
> a result across platforms tests the platforms, not the harness.
>
> **Ledger consequence:** the three `aaru5|*|vendor-cap` rows are back to `not-yet`.
> `blocked` means "red proven, green blocked BY UPSTREAM at one version" — upstream
> never blocked anything, so the state was wrong on its own definition. This is
> deliberately NOT flipped to proven: nobody has yet run the capped/uncapped A/B with
> a real terminal, and a `blocked` row must never be quietly upgraded to a green one.
> The difference now is that the obligation is **closeable** — we know how to measure
> it (TTY with an explicit `stty` size), which is exactly what it was missing.

## What still holds: the RED half

The RED measurement below is **unaffected** by the terminal bug — it is an strace of
the SG_IO layer, taken before any progress output, and it stands on its own: aaru5
issues an `ATA PASS-THROUGH(16)` (0x85) that returns **EPERM without the cap**. The
capability is load-bearing. That was never the disputed part.

## Original text below, kept verbatim as the record of the error

Nothing below this line has been edited. It is preserved because a retraction that
deletes what it retracts teaches nobody anything — and because the true cause is
sitting in it, in plain sight, twice.

---

Status (since 2026-07-17): `aaru5|*|vendor-cap` is **`blocked:5.4.2`** in the ledger —
red proven, green owed by upstream. It passes through without holding the gate shut,
and `proof-status.sh` fails loudly the moment aaru5's Version leaves 5.4.2, so the
blockade cannot quietly outlive its cause. It was `not-yet` before, which made the
backlog permanent and the enforcement gate unreachable.

## What is proven

RED (cap stripped): the capability is load-bearing — aaru5 issues a cap-gated
`ATA PASS-THROUGH(16)` (0x85) SG_IO that returns **EPERM without the cap**
(strace, fedora lane, 2026-07-15). Detail below; this line is the machine-readable
handle `proof-status.sh` looks for, not a new claim.

- The cap IS delivered: `getcap /usr/lib64/aaru5/aaru -> cap_sys_rawio=ep`, owned by
  `aaru5-5.4.2-5.fc44` (fedora). The delivery mechanism (Fedora %caps) is proven
  load-bearing on this exact kernel/drive by redumper/discimagecreator and aaru 6.0.
- strace of the uncapped aaru5 shows it DOES issue a cap-gated opcode: an
  `ATA PASS-THROUGH(16)` (0x85) SG_IO that returns EPERM without the cap. So the cap
  gates real aaru5 drive access.

There is deliberately **no GREEN section**: that is exactly what upstream blocks, and
the ledger does not ask a blockade for one. It only asks for the RED above.

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

Also tested AS ROOT (sudo, ALL capabilities) on the audio CD: crashes identically
(count '-1', right after "Added 4862 CompactDisc read offsets"). So the crash is
privilege-independent too -- not cap_sys_rawio, not any capability, a pure aaru5 5.4.2
code bug in the dump/scan setup. Root buys nothing here.

## To close it later
(a) a fixed aaru5 build whose `media dump`/`scan` does not crash on optical CDs, or
(b) accept aaru5 vendor-cap as delivery-proven (getcap on all 3 lanes + the lane mechanism
proven load-bearing by redumper/dic/aaru + aaru5's own 0x85 gate). A different disc will NOT
help -- tried data, mixed and pure-audio, all crash. Kept **not-yet** to honor "measure,
don't infer". Same blocker confirmed on fedora, opensuse and debian (same aaru5 5.4.2 code).
