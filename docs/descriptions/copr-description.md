Optical-disc preservation tools for Fedora 43+ and Enterprise Linux 8/9/10 (RHEL, CentOS Stream, AlmaLinux, Rocky, Oracle Linux; enable EPEL there), on **x86_64 and aarch64**: **redumper**, **DiscImageCreator** (DIC + EccEdc + DVDAuth + unscrambler), **Aaru** (v6 plus the version-pinned stable **aaru5**), **MPF** (mpf-check + mpf-cli + mpf-gui), **Redumper-GUI**, and **dreamdump** (Sega Dreamcast GD-ROMs; one of the four programs MPF starts itself, at the release MPF bundles).

**redumper-mpf** and **redumper-rgui** are version pins, not alternatives: they carry the redumper build that MPF (`redumper-mpf`) and Redumper-GUI (`redumper-rgui`) bundle. Install one only if you use that frontend — the rolling **redumper** is what you want otherwise. They have fixed names and a moving version, so they upgrade in place; `redumper-mpf` tracks MPF automatically.

## Drive access — verified on real hardware

Measured on 2026-07-14 with a Plextor PX-760A USB optical drive and a NEC USB floppy in a clean Fedora VM: a plain desktop user in **no** drive group — not cdrom, not floppy, not disk, not plugdev — dumped both media, and sudo was never invoked.

Two mechanisms carry that. `cap_sys_rawio` is preset (via %caps) on the **dumping tools** — redumper, redumper-rgui, redumper-mpf, aaru, aaru5, DiscImageCreator — so vendor SCSI commands (Plextor 0xD8, etc.) work without root. **dreamdump** gets none because it needs none: it sends only INQUIRY, SET CD SPEED and READ CD, which the kernel allows anyone who can open the drive (measured on 2026-10-12 as a plain user in a Fedora VM: drive opened, commands accepted, sectors read). And systemd-logind grants a `uaccess` ACL on the device node to whoever holds the active local seat: for optical drives (/dev/sr*) via systemd's own rule, and for USB or legacy floppy drives via a udev rule these packages ship. The ACL appears the moment the package is installed — the drive does not need to be re-plugged.

The capability deliberately sits on **no GUI** and on none of the MPF frontends, which orchestrate the dumpers rather than talk to a drive: a process holding file capabilities is non-dumpable, so the desktop portal refuses to authorise it and every file dialog it opens breaks.

Only headless / SSH / cron sessions, which have no seat, need more: the cdrom group for optical drives, or root for floppies (the floppy node stays root:disk, and the disk group would expose every block device on the system, so it is not a safe substitute).

**aarch64 / arm64 is built and published, but not hardware-tested.** The drive-access results above were measured on x86_64 only. Nothing in the packaging is architecture-specific -- the capability, udev and permissions mechanisms are the same files on both arches -- but nobody has run a dump from an ARM machine, so it is deliberately not claimed as verified. Reports welcome.

Two things that look like permission errors and are not: the desktop may have **auto-mounted** the medium (GNOME does, KDE does not) — release it without root via `udisksctl unmount -b /dev/sr1`; and **Aaru asks a one-time GDPR consent question on its first run**, so run `aaru configure` once in a terminal before dumping.

Unofficial third-party packaging — a hobby project, not affiliated with any upstream tool author. Packaging recipes: https://github.com/gmipf/packaging-media-preservation
