%global debug_package %{nil}

# Pinned-build compatibility package -- this one is MPF's.
#
# Consumers of redumper bundle a SPECIFIC upstream build and are tested against
# that one. A distribution cannot ship a second /usr/bin/redumper, so instead of
# bundling the binary inside every consumer, each pinned build gets its own
# package named after the build number: redumper732 here for MPF, redumper729 for
# redumper-gui. Consumers depend on the one they were tested with, share it when
# they agree, and the rolling `redumper` package stays untouched for CLI users.
#
# ⚠️ POINTING MPF AT THE ROLLING `redumper` IS NOT AN OPTION, even on a day when
# the rolling package happens to carry the very same build (it does right now:
# both are b732). The rolling package MOVES. The moment redumper releases b733,
# the watcher bumps it and every MPF dump silently runs a dumper build MPF was
# never tested against -- and MPF has no version check of any kind to notice: it
# reads whatever version it finds out of the log and writes it into the
# submission. Today's equality is an accident of timing, not a property to rely
# on. That mistake was made once already (redumper726 was deleted instead of
# being advanced to 732); the rule is that the pin FOLLOWS MPF, it never
# dissolves into the rolling package.
#
# So: when MPF's publish-nix.sh moves to a new redumper build, a new
# redumper<N> package is generated and MPF is repointed at it. scripts/status.sh
# checks exactly that and goes red when it is not true.
#
# Naming follows the same pattern as `aaru5` next to the rolling `aaru`
# (and gcc12 / python3.9 / libicu74 in the wider distro world): the build
# number is IN the name, so the package's contents can never silently change
# under a consumer that pinned it.
%global rdbuild 732

Name:           redumper%{rdbuild}
Version:        %{rdbuild}
Release:        1%{?dist}
Summary:        redumper b%{rdbuild}, the build pinned by MPF

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
# /usr/bin/redumper%%{rdbuild}, never /usr/bin/redumper. No Conflicts needed.
# (%%%% because rpm expands macros inside comments too -- a bare %%{rdbuild} here
# is not documentation, it is a substitution that happens to look like one.)

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray, used by the Redump and No-Intro preservation projects.

This package ships upstream build b%{rdbuild} as /usr/bin/redumper%{rdbuild}.
It exists so that tools which are version-coupled to a specific redumper
build get exactly the build they were tested against, no matter which
version the rolling `redumper` package currently carries. It is the build
MPF bundles, and the mpf packages point their configuration at it.

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
* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 732-1
- Initial build. Pinned-build compatibility package carrying upstream redumper
  b732 as /usr/bin/redumper732 -- the build MPF's publish-nix.sh bundles. The mpf
  packages point their configuration at it, so an MPF dump runs the dumper build
  its upstream actually tested with.
- Replaces the never-published redumper726: MPF has moved its bundled build from
  b726 to b732, so the pin moves with it. The pin ALWAYS exists, even while the
  rolling `redumper` package happens to carry the same build (it does today).
  The rolling package moves -- the day b733 lands, an MPF that pointed at it
  would silently dump with an untested build, and MPF has no version check to
  notice.
- Co-installable with the rolling `redumper` and with redumper729 (redumper-gui's
  pin); the build number is in the binary name, so no files overlap.
