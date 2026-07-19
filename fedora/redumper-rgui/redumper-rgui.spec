%global debug_package %{nil}
# No debuginfo -> the /usr/lib/.build-id/ links rpm still makes on EL are dead
# weight, and they collide: this package ships the SAME upstream binary as the
# rolling `redumper` whenever that reaches this build, so both claim the same
# build-id path and cannot be installed together (measured on EL10 2026-07-16;
# Fedora's rpm drops them with debug_package, EL's does not). See redumper.spec.
%global _build_id_links none

# Compatibility package: the redumper build Redumper-GUI is version-coupled to.
#
# Redumper-GUI bundles a SPECIFIC upstream redumper build and its upstream states
# plainly that "changing the bundled version of redumper is not recommended as it
# may not be supported by the GUI". A distribution cannot ship a second
# /usr/bin/redumper, so this package carries that pinned build as
# /usr/bin/redumper-rgui, and redumper-gui hard-depends on it by this FIXED name.
# The rolling `redumper` package is left untouched for CLI users.
#
# The name is fixed; the VERSION tracks the bundled build. %%global rdbuild below
# is that build number (and the Version, and the Source tag), and
# .github/workflows/watch-consumer-pins.yml bumps it hourly from Redumper-GUI's
# upstream. So when the GUI moves to a new bundled build this package upgrades in
# place and every installed machine follows on the next upgrade. That is the
# whole point of keeping the build number OUT of the name: `dnf/zypper/apt
# upgrade` carries an in-place version bump across installs, but it does NOT
# follow a rename -- a build-number name would strand every machine on the old
# pin, silently.
%global rdbuild 733

Name:           redumper-rgui
Version:        %{rdbuild}
Release:        1%{?dist}
Obsoletes:      redumper729 < 730
Summary:        redumper b%{rdbuild}, the build pinned by redumper-gui

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP -- the exact same
# artifact the rolling `redumper` package repackages, only at a pinned tag.
Source0:        %{url}/releases/download/b%{rdbuild}/redumper-b%{rdbuild}-linux-x64.zip

# arm64 counterpart of Source0. Both arch ZIPs are bundled and the matching one
# is picked per build arch via %%ifarch (see %%prep / %%install). packit/OBS build
# ONE package source across every enabled arch chroot, so an arch-conditional
# Source: would bake one arch's binary into it and the aarch64 build would ship
# the x86 binary. Carrying both keeps the aarch64 build honest. Same %%{rdbuild}
# macro => the watcher bumps both URLs in lockstep.
Source4:        %{url}/releases/download/b%{rdbuild}/redumper-b%{rdbuild}-linux-arm64.zip
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/README.md

ExclusiveArch:  x86_64 aarch64
BuildRequires:  unzip

# Co-installable with the rolling `redumper` by construction: the binary is
# /usr/bin/redumper%%{rdbuild}, never /usr/bin/redumper. No Conflicts needed.
# (%%%% because rpm expands macros inside comments too -- a bare %%{rdbuild} here
# is not documentation, it is a substitution that happens to look like one.)

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray, used by the Redump and No-Intro preservation projects.

This package ships upstream build b%{rdbuild} as /usr/bin/redumper-rgui.
It exists so that tools which are version-coupled to a specific redumper
build get exactly the build they were tested against, no matter which
version the rolling `redumper` package currently carries. redumper-gui
depends on it and calls it directly.

It installs alongside the rolling `redumper` package without conflicting.
For interactive use prefer that one -- it tracks upstream and carries the
redumper(1) manpage; this package is a compatibility build, not a
replacement.

cap_sys_rawio is set on the binary so vendor SCSI passthrough commands work
without sudo, exactly as in the rolling package.

%prep
%setup -q -c -T
%ifarch aarch64
unzip -q %{SOURCE4}
%else
unzip -q %{SOURCE0}
%endif

%build
# Self-contained statically linked binary; nothing to compile.

%install
install -d %{buildroot}%{_bindir}
%ifarch aarch64
install -m 0755 redumper-b%{rdbuild}-linux-arm64/bin/redumper \
    %{buildroot}%{_bindir}/redumper-rgui
%else
install -m 0755 redumper-b%{rdbuild}-linux-x64/bin/redumper \
    %{buildroot}%{_bindir}/redumper-rgui
%endif

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

%files
%license LICENSE
%doc README.md
%caps(cap_sys_rawio=ep) %{_bindir}/redumper-rgui

%changelog
* Sun Jul 19 2026 gmipf <gmipf64@gmail.com> - 733-1
- Automated: consumer moved its bundled redumper to b733; the pin follows. Release reset to 1.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 729-4
- Add aarch64 (arm64) support. Bundle the upstream linux-arm64 release ZIP
  alongside linux-x64 (both carry the same %%{rdbuild} macro, so the watcher
  bumps them in lockstep) and pick the matching binary per build arch via
  %%ifarch. ExclusiveArch is now x86_64 aarch64. packit builds ONE SRPM that
  COPR/OBS build across every arch chroot, so an arch-conditional Source: would
  bake one arch's binary into the SRPM; bundling both and selecting at %%install
  is the only correct way. arm64 ships UNTESTED -- no hardware drive-access proof
  exists for it; the repackaging path is architecture-neutral but this is
  deliberately not claimed as proven.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 729-3
- Renamed redumper729 -> redumper-rgui. The package name no longer carries the
  build number; the pinned build now lives at a FIXED name (/usr/bin/redumper-rgui)
  with the build number as the Version. When Redumper-GUI bundles a new redumper
  build the package upgrades in place instead of a new redumper<N> appearing and
  the old one being orphaned -- an in-place version bump migrates installed
  machines, a rename does not. Obsoletes redumper729 so existing installs move
  over. watch-consumer-pins.yml bumps this hourly; no manual step remains.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 729-2
- Set %%global _build_id_links none. With debug_package off these links point at
  debuginfo that does not exist -- and on EL they made this package collide with
  the rolling `redumper` when it reaches build 729: both ship the same upstream binary, so both claimed
  /usr/lib/.build-id/db/ea49...ce and `dnf install redumper mpf-cli` (mpf
  recommends redumper732) failed the transaction test. Fedora's rpm drops the
  links together with debug_package, EL's does not -- which is why building and
  testing on Fedora never showed it. Measured on CentOS Stream 10, 2026-07-16.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 729-1
- Initial build. Pinned-build compatibility package carrying upstream
  redumper b729 as /usr/bin/redumper729, for consumers that are coupled to
  that exact build. redumper-gui is the first: its upstream bundles b729 and
  states that other versions may not be supported, and it invokes redumper as
  a sibling of its own executable -- which a distribution package cannot honor
  by shipping a second /usr/bin/redumper.
- Co-installable with the rolling `redumper` package (currently b731); no file
  overlaps, so a user can have the newest redumper on PATH and still run the
  GUI against the build it was tested with.
