# packaging-media-preservation

Packages for optical-disc preservation tools, built straight from upstream:

- **Fedora and EPEL** (RHEL, CentOS Stream, AlmaLinux, Rocky, Oracle Linux 8–10)
  in the [`gmipf/media-preservation`][copr] COPR repository
- **openSUSE, Debian and Ubuntu** in the [`home:gmipf:media-preservation`][obs]
  OBS project
- **macOS** in a Homebrew tap in this repository

The Linux packages are built for x86_64 and aarch64. This repository holds only
the recipes; the tools come from their upstream projects, and nothing is
re-hosted.

## Tools

| Tool | What it is | Fedora / EPEL | openSUSE | Ubuntu | Debian | macOS |
|---|---|:-:|:-:|:-:|:-:|:-:|
| [redumper](https://github.com/superg/redumper) | disc dumper | ✅ | ✅ | ✅ | ✅ | ✅ |
| [DiscImageCreator](https://github.com/saramibreak/DiscImageCreator) | disc and floppy dumper | ✅ | ✅ | ✅ | ✅ | ✅ ¹ |
| [Aaru](https://github.com/aaru-dps/Aaru) | dumper and image toolkit (v6 beta, with GUI) | ✅ | ✅ | ✅ | ✅ | — |
| [Aaru 5.4](https://github.com/aaru-dps/Aaru) (`aaru5`) | the stable Aaru CLI that MPF drives | ✅ | ✅ | ✅ | ✅ | — |
| [MPF](https://github.com/SabreTools/MPF) | dumping frontend: GUI, CLI and log checker | ✅ | ✅ | ✅ | ✅ | — |
| [Redumper-GUI](https://github.com/Deterous/Redumper-GUI) | graphical frontend for redumper | ✅ | ✅ | 26.04 | 13 | — |
| [dreamdump](https://codeberg.org/MoriGM/dreamdump) | Dreamcast GD-ROM dumper | ✅ | ✅ | ✅ | ✅ | — |
| `redumper-mpf`, `redumper-rgui` | the redumper builds MPF and Redumper-GUI bundle | ✅ | ✅ | ✅ | ✅ | — |

¹ optical drives only; no tool reaches a floppy drive on macOS.

A watcher checks every upstream hourly, and new releases are packaged for all
lanes automatically (`aaru5` is bumped by hand on purpose). What each package
tracks and how it is built: [docs/how-it-works.md](docs/how-it-works.md).

[copr]: https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/
[obs]: https://build.opensuse.org/project/show/home:gmipf:media-preservation

## Install

### Fedora, and RHEL / CentOS Stream / AlmaLinux / Rocky / Oracle Linux 8–10

```sh
sudo dnf install epel-release    # enterprise Linux only, not on Fedora
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper discimagecreator aaru aaru5 mpf redumper-gui dreamdump
```

### openSUSE Leap 16.0 and Tumbleweed

```sh
sudo zypper addrepo https://download.opensuse.org/repositories/home:gmipf:media-preservation/16.0/home:gmipf:media-preservation.repo
sudo zypper refresh
sudo zypper install redumper discimagecreator aaru aaru5 mpf redumper-gui dreamdump
```

For Tumbleweed, replace `16.0` with `openSUSE_Tumbleweed` in the repository URL
(`openSUSE_Tumbleweed_ARM` on aarch64).

### Ubuntu 22.04, 24.04, 26.04 and Debian 12, 13

```sh
. /etc/os-release
case "$ID" in ubuntu) DIST="xUbuntu_$VERSION_ID" ;; debian) DIST="Debian_$VERSION_ID" ;; esac
REPO="https://download.opensuse.org/repositories/home:/gmipf:/media-preservation/$DIST"

curl -fsSL "$REPO/Release.key" | sudo gpg --dearmor -o /usr/share/keyrings/media-preservation.gpg
echo "deb [signed-by=/usr/share/keyrings/media-preservation.gpg] $REPO/ /" \
  | sudo tee /etc/apt/sources.list.d/media-preservation.list

sudo apt update
sudo apt install redumper discimagecreator aaru aaru5 mpf dreamdump
```

On Ubuntu 26.04 and Debian 13, `redumper-gui` is available too.

### macOS (Homebrew, Apple Silicon and Intel)

```sh
brew tap gmipf/media-preservation https://github.com/gmipf/packaging-media-preservation
brew install gmipf/media-preservation/redumper gmipf/media-preservation/discimagecreator
```

The full names are needed because Homebrew loads nothing from a third-party tap
it has not been told to trust ([Tap Trust](https://docs.brew.sh/Tap-Trust));
after `brew trust gmipf/media-preservation` the short names work too.

## Drive access

At a local desktop session on Linux you need **no sudo and no drive group** to
dump, measured on real hardware on every distribution: the packages ship the
udev rules and set `cap_sys_rawio` on the dumping tools for vendor commands such
as Plextor `D8`. A headless or SSH session has no seat and needs the `cdrom`
group for optical drives. On macOS, name the drive by its BSD name from
`diskutil list` and work outside Desktop, Documents and Downloads.

Two things look like permission errors and are not: a desktop that auto-mounted
the disc (`udisksctl unmount -b /dev/sr0` releases it), and Aaru's one-time
consent question on the first run (`aaru configure`).

Mechanisms per distribution, the macOS measurement and how the proofs are kept
honest: [docs/drive-access.md](docs/drive-access.md).

## Status

Unsupported third-party recipes. Personal hobby project, not affiliated with
any of the distributions it targets, with Redump or No-Intro, or with any
upstream tool author.
