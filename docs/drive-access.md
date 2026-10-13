# Drive access

Back to the [README](../README.md).

## Linux

**Verified on every Linux lane** (2026-07-14, real hardware passed through to a
clean VM per distribution: a Plextor PX-760A USB optical drive and a NEC USB
floppy). A plain desktop user in **no** drive group — not `cdrom`, not `floppy`,
not `disk`, not `plugdev` — dumped both, with `sudo` never invoked. Two
independent mechanisms carry that, and each is delivered differently per
distribution:

| | what it grants | Fedora / EPEL | openSUSE | Ubuntu / Debian |
|---|---|---|---|---|
| `uaccess` ACL on the device node | opening and reading the drive | udev rule | udev rule | udev rule |
| `cap_sys_rawio` on the binary | vendor SCSI commands (Plextor `0xD8` …) | `%caps` in the spec | permissions framework (`permctl`) | `setcap` in the `postinst` |

The ACL is granted by systemd-logind to whoever holds the **active local seat** —
for optical drives (`/dev/sr*`) via systemd's own rule, and for USB or legacy
floppy drives via a udev rule these packages ship. It appears the moment the
package is installed; the drive does not need to be re-plugged.

The capability sits on the **dumping tools** — `redumper`, `redumper-rgui`,
`redumper-mpf`, `aaru`, `aaru5` and DiscImageCreator — and deliberately **not** on
any GUI (`mpf-gui`, `redumper-gui`) or on the MPF frontends, which orchestrate
those tools rather than talk to a drive. A process holding file capabilities is
non-dumpable, and the desktop portal service then refuses to authorise it: giving
a GUI `cap_sys_rawio` breaks every file dialog it opens.

`dreamdump` gets none because it needs none: everything it sends (INQUIRY,
SET CD SPEED, READ CD) is on the kernel's unprivileged SG_IO list, measured as a
plain user on 2026-10-12 ([proof](../proofs/dreamdump-optical-access-MEASURED-x86_64.md)).
Its build fails the day a new SCSI command appears in its source.

Only headless / SSH / cron sessions, which have no seat, need more. For optical
drives, add yourself to the `cdrom` group. A headless floppy dump needs root: the
floppy node stays `root:disk`, and the `disk` group would expose every block
device on the system, so it is not a safe substitute.

> **aarch64 is built and published, but not hardware-tested.** The drive-access
> results above were measured on x86_64 only. Nothing in the packaging is
> architecture-specific — the capability, udev and permissions mechanisms are the
> same files on both — but no one has run a dump from an ARM machine, so this is
> deliberately not claimed as verified. Reports welcome.

## macOS

Name a drive by its BSD name as `diskutil list` shows it, for example
`redumper disc --drive=disk4`. No sudo and no capability is needed, but macOS
refuses drive access to a program working inside Desktop, Documents or
Downloads.

Measured in October 2026 on macOS 26.5 (Intel), from an administrator account,
with a Plextor PX-760A and an audio CD: redumper from the tap read it including
the vendor `D8` read; DiscImageCreator from the tap dumped all seven tracks
(exit 0) through the same `D8` read, found the drive's +30 sample offset and
unmounted the disc itself. Its pregap before track 1 (negative LBAs) was not
readable there, so the combined `(Track all).img` stayed empty; the per-track
files and the full image are complete. Not measured yet: a standard account.
Right after a drive appears, macOS may hold it for a few seconds ("Device
Busy"); try again.

## Two things that look like permission errors and are not

- **The desktop may have auto-mounted the medium** (GNOME does, KDE does not) —
  the dumper then cannot take its exclusive lock. Release it without root:
  `udisksctl unmount -b /dev/sr1` (or the floppy's node). Aaru reports this as
  `Could not open device, error EncodingUnknown`, which names everything except
  the cause.
- **Aaru asks a GDPR consent question on its very first run.** Until it is
  answered once, `aaru media dump` stops there. Run `aaru configure` in a
  terminal, then dump.

## The proof ledger — and how to keep it honest

None of the above is a claim you have to take on trust, and none of it is allowed
to rot quietly. `scripts/proof-ledger.tsv` carries one line per (tool, lane,
mechanism), each with a fingerprint of exactly the recipe fragments that deliver
it — the udev rule, the `%post`/`postinst` body, the `%caps()` directive, the
openSUSE permissions profile. `scripts/proof-status.sh` recomputes that
fingerprint from the live tree and shouts when it moved: touch the scriptlet and
the proof is declared stale. It is keyed on the **mechanism**, never the version,
so a `redumper` b731→b732 bump does not cry wolf.

**Install the hook once per clone** — otherwise the ledger is a script somebody
has to remember to run, which is the failure mode it exists to remove:

```sh
git config core.hooksPath .githooks
```

It blocks a commit on drift, on a missing mechanism line (coverage), and on a
proof whose artifact is missing or does not show its own failure. It deliberately
does **not** block on the open backlog: you must be able to commit a new mechanism
together with the ledger line that admits it is unproven.

Three evidence states, and nothing else: `not-yet` (open), `log:<path>` (measured
red **and** green, artifact saved), and `blocked:<version>:<path>` — red proven,
green blocked by an upstream bug at exactly that version. A blockade passes
through without holding the gate shut, and fails loudly the moment the tool's
version moves, which is the point: marking such a line `proven` instead would sit
green forever and nobody would ever measure it again.

**The artifact is read, not just resolved.** A proof log must contain a RED half,
a GREEN half and a `VERDICT:` line; a blockade must contain a RED half and is not
asked for a GREEN. A run that could not have failed is not evidence — so the
ledger asks each artifact for its failure, rather than trusting that whoever wrote
it remembered to produce one.
