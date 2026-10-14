# Changelog

Which packages, distributions and architectures this repository ships, and
since when. Newest first. Version updates are not listed; each package keeps
them in its own changelog (`%changelog` in the spec, `debian/changelog`).

A date is the day the first package was built in the public repository (COPR's
build list, OBS's source history), not the day its recipe was committed. Where
that history is gone (the deleted Launchpad PPA, COPR packages that were
removed or renamed), the date comes from the git history.

<!--
scripts/changelog-check.py reads the "Added", "Removed" and "Renamed" lines and
compares them with the recipes in fedora/, opensuse/, ubuntu/ and Formula/; it
runs in scripts/lint.sh, so in CI and in the pre-commit hook. Their form:

  - Added `pkg`, `pkg` and `pkg` on Fedora, EPEL, openSUSE, Debian and Ubuntu. Free text.
  - Removed `pkg` on Fedora. Free text.
  - Renamed `old` to `new` on Fedora and EPEL. Free text.

Distributions: Fedora and EPEL (fedora/), openSUSE (opensuse/), Debian and
Ubuntu (ubuntu/), macOS (Formula/). A line may wrap; continuation lines are
indented. Every other line is free text and is not checked.
-->

## 2026-10-13

- Added `redumper` and `discimagecreator` on macOS. A Homebrew tap in this
  repository, for Apple silicon and Intel: `redumper` is upstream's macOS
  build, `discimagecreator` is built from source (optical drives only).

## 2026-10-12

- Added `dreamdump` on Fedora, EPEL, openSUSE, Debian and Ubuntu. The
  Dreamcast GD-ROM dumper that MPF starts; x86_64 and aarch64.

## 2026-07-18

- aarch64 for every package on every Linux distribution: COPR (Fedora, EPEL)
  and OBS (openSUSE Leap 16.0 and Tumbleweed, Debian, Ubuntu).
- First Fedora 45 builds. COPR's `fedora-all` and `epel-all` targets add and
  drop releases on their own; this log notes the first build.

## 2026-07-17

- Renamed `redumper732` to `redumper-mpf` and `redumper729` to `redumper-rgui`
  on Fedora, EPEL, openSUSE, Debian and Ubuntu. The names stay; the version
  follows the redumper build that MPF and Redumper-GUI pin.

## 2026-07-15

- Added `redumper-gui` on Debian. Debian 13 only, with Rust from
  trixie-backports; Debian 12 has no Rust new enough.

## 2026-07-14

- Ubuntu moved from the Launchpad PPA to OBS: 22.04, 24.04 and 26.04, built
  from the same recipe as Debian. The PPA is deleted.
- Added `redumper`, `aaru`, `aaru5`, `mpf`, `discimagecreator` and
  `redumper729` on Debian. Debian 12 and 13, on OBS.
- Added `redumper-gui` and `redumper729` on openSUSE.
- Added `redumper732` on Fedora, EPEL, openSUSE, Debian and Ubuntu. The
  redumper build that MPF bundles.

## 2026-07-13

- Added `redumper-gui` and `redumper729` on Fedora, EPEL and Ubuntu. Ubuntu
  through the Launchpad PPA, 26.04 only. `redumper729` is the redumper build
  that Redumper-GUI pins.

## 2026-07-12

- Ubuntu 26.04 added to the Launchpad PPA.

## 2026-07-11

- Added `redumper`, `aaru`, `aaru5`, `mpf` and `discimagecreator` on openSUSE.
  OBS project `home:gmipf:media-preservation`: Leap 16.0 and Tumbleweed.

## 2026-07-05

- Added `redumper`, `aaru`, `aaru5`, `mpf` and `discimagecreator` on Ubuntu.
  A Launchpad PPA, Ubuntu 22.04 and 24.04.

## 2026-07-04

- openSUSE Leap 15.6 and Tumbleweed tried on COPR and dropped the same day;
  openSUSE has been built on OBS since 2026-07-11.

## 2026-07-03

- Added `redumper`, `aaru`, `aaru5`, `mpf` and `discimagecreator` on EPEL.
  EPEL 8, 9 and 10.

## 2026-07-02

- Added `aaru5` on Fedora. Aaru 5.4, the stable series that MPF drives,
  installable next to `aaru`.

## 2026-06-15

- Added `discimagecreator`, `aaru` and `mpf` on Fedora.
- Removed `mpf-check` on Fedora. It became a subpackage of `mpf` and installs
  under the same name.

## 2026-06-14

- The COPR repository `gmipf/media-preservation` starts: Fedora 43, 44 and
  rawhide, x86_64.
- Added `redumper` and `mpf-check` on Fedora.
