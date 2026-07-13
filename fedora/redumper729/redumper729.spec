%global debug_package %{nil}

# Pinned-build compatibility package. Consumers of redumper (redumper-gui,
# MPF) bundle a SPECIFIC upstream build and are only tested against it --
# redumper-gui's upstream states plainly that "changing the bundled version
# of redumper is not recommended as it may not be supported by the GUI".
# A distribution cannot ship a second /usr/bin/redumper, so instead of
# bundling the binary inside every consumer, each pinned build gets its own
# package named after the build number: redumper729 here, redumper726 for
# MPF. Consumers depend on the one they were tested with, share it when they
# agree, and the rolling `redumper` package stays untouched for CLI users.
#
# Naming follows the same pattern as `aaru5` next to the rolling `aaru`
# (and gcc12 / python3.9 / libicu74 in the wider distro world): the build
# number is IN the name, so the package's contents can never silently change
# under a consumer that pinned it.
%global rdbuild 729

Name:           redumper%{rdbuild}
Version:        %{rdbuild}
Release:        1%{?dist}
Summary:        redumper b%{rdbuild}, the build pinned by redumper-gui

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP -- the exact same
# artifact the rolling `redumper` package repackages, only at a pinned tag.
Source0:        %{url}/releases/download/b%{rdbuild}/redumper-b%{rdbuild}-linux-x64.zip
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/README.md

ExclusiveArch:  x86_64
BuildRequires:  unzip

# Co-installable with the rolling `redumper` by construction: the binary is
# /usr/bin/redumper%{rdbuild}, never /usr/bin/redumper. No Conflicts needed.

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray, used by the Redump and No-Intro preservation projects.

This package ships upstream build b%{rdbuild} as /usr/bin/redumper%{rdbuild}.
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
unzip -q %{SOURCE0}

%build
# Self-contained statically linked binary; nothing to compile.

%install
install -d %{buildroot}%{_bindir}
install -m 0755 redumper-b%{rdbuild}-linux-x64/bin/redumper \
    %{buildroot}%{_bindir}/redumper%{rdbuild}

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

%files
%license LICENSE
%doc README.md
%caps(cap_sys_rawio=ep) %{_bindir}/redumper%{rdbuild}

%changelog
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
