## Install

```sh
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper discimagecreator aaru aaru5 mpf redumper-gui dreamdump
```

**On Enterprise Linux (RHEL, CentOS Stream, AlmaLinux, Rocky, Oracle Linux 8/9/10), enable EPEL first:**

```sh
sudo dnf install epel-release
```

`aaru` and `mpf-gui` need `libunwind`, which Enterprise Linux ships in EPEL rather than in BaseOS/AppStream. Without EPEL those two packages cannot be resolved (verified on AlmaLinux 9). Fedora needs no extra repository.

`mpf` is a meta-package; it pulls in `mpf-check` (log validator + Redump !submissionInfo.txt writer), `mpf-cli` (headless dump orchestrator) and `mpf-gui` (Avalonia desktop frontend). Install the individual subpackages if you only need part of it, e.g. `sudo dnf install mpf-check`. Launch the GUI via `mpf-gui` or the **MPF** desktop entry.

`aaru5` is the version-pinned stable Aaru 5.4 CLI that MPF drives; it installs as `/usr/bin/aaru5` and co-exists with the rolling `aaru` v6.

`dreamdump` dumps the high-density area of Sega Dreamcast GD-ROMs and follows the release MPF bundles; the packaged MPF finds it on its own. It needs a drive that can read that area: upstream's record of tested drives is in `man dreamdump`.

`aaru` ships both CLI and Avalonia GUI in one binary — launch the GUI via `aaru gui` or via the **Aaru** desktop entry. `redumper` and `discimagecreator` are CLI-only.

## Drive access

`cap_sys_rawio` is preset on the dumping tools (`redumper`, `redumper-rgui`, `redumper-mpf`, `aaru`, `aaru5`, DiscImageCreator; `dreamdump` needs none) so vendor SCSI passthrough commands (Plextor `0xD8`, etc.) work without `sudo` — and deliberately **not** on the GUIs or the MPF frontends, which drive those tools rather than a drive: a process holding file capabilities is non-dumpable, so the desktop portal refuses to authorise it and every file dialog it opens breaks.

Logged in at a local desktop seat you need **no group membership and no root** to read the drives either: systemd-logind grants a `uaccess` ACL to the device node automatically — for optical drives (`/dev/sr*`) via systemd's own rule, and for USB or legacy floppy drives via a udev rule these packages ship.

Only headless / SSH / cron sessions, which have no seat, need more. For optical drives, add yourself to the `cdrom` group:

```sh
sudo usermod -aG cdrom $USER
# log out and back in
```

A headless floppy dump needs root: the floppy node stays `root:disk`, and the `disk` group would expose every block device on the system, so it is not a safe substitute.

## Upstream

- redumper — https://github.com/superg/redumper
- DiscImageCreator — https://github.com/saramibreak/DiscImageCreator
- Aaru — https://github.com/aaru-dps/Aaru
- MPF — https://github.com/SabreTools/MPF
- Redumper-GUI — https://github.com/Deterous/Redumper-GUI
- dreamdump — https://codeberg.org/MoriGM/dreamdump

## Packaging recipes

Spec files and build configuration live at https://github.com/gmipf/packaging-media-preservation. Hobby project, unsupported third-party recipes, not affiliated with any upstream tool author.
