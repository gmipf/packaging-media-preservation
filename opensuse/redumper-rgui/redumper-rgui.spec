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
%global rdbuild 734

Name:           redumper-rgui
Version:        %{rdbuild}
Release:        0
Obsoletes:      redumper729 < 730
Summary:        redumper b%{rdbuild}, the build pinned by redumper-gui

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP -- the exact same
# artifact the rolling `redumper` package repackages, only at a pinned tag.
# The binary inside is a single statically linked ELF (clang + libc++ +
# -static), built by upstream's own CI. Identical artifact to the Fedora/COPR
# and Debian/Ubuntu lanes.
#
# OBS build roots are hermetic (no network), so these URLs are NOT fetched at
# build time -- the _service (download_files) downloads them by basename and
# they are committed as package sources. rpmbuild then resolves each Source:
# to its basename in SOURCES.
Source0:        %{url}/releases/download/b%{rdbuild}/redumper-b%{rdbuild}-linux-x64.zip

# arm64 counterpart of Source0. Both arch ZIPs are bundled and the matching one
# is picked per build arch via %%ifarch (see %%prep / %%install). OBS builds ONE
# package source across every enabled arch, so an arch-conditional Source: would
# commit only one arch's binary; carrying both keeps the aarch64 build honest.
# Same %%{rdbuild} macro => the _service fetches and the watcher bumps both in
# lockstep. It also travels the Debian lane as a Debtransform-Files extra.
Source4:        %{url}/releases/download/b%{rdbuild}/redumper-b%{rdbuild}-linux-arm64.zip
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{rdbuild}/README.md

# The recipe files below carry a URL for the same reason the upstream sources do:
# download_files fetches whatever a Source: names, and that is what keeps them OUT
# of _service. _service lives in OBS and only an `osc commit` can change it, so
# every file listed there would make it a function of our file list. See
# opensuse/redumper-mpf/redumper-mpf.spec for the measurement behind this.
Source99:       https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/redumper-rgui/redumper-rgui-rpmlintrc

ExclusiveArch:  x86_64 aarch64
BuildRequires:  unzip

# openSUSE grants file capabilities through the permissions framework
# (permctl/chkstat), not a bare %%caps entry -- the post-build permissions
# check rejects capabilities set outside it. We ship a permissions.d profile
# and apply/verify it via the standard scriptlet macros, exactly as the
# rolling redumper package does.
BuildRequires:  permissions
Requires(post): permissions
Requires(verify): permissions

# Deliberately NO manpage. The rolling `redumper` package carries redumper(1),
# and its text describes the command-line tool, not this build number. Shipping
# a second copy under a different name would either duplicate that page or
# invite it to drift. This package exists for consumers, not for reading.

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

This package grants the binary the cap_sys_rawio file capability (via the
openSUSE permissions framework) so vendor SCSI passthrough commands work
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

# Permissions framework profile: grant cap_sys_rawio for sudo-less SCSI
# passthrough (Plextor read method D8, Kreon commands, ...). The capability
# lives on the continuation line beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/redumper-rgui <<'EOF'
# redumper needs raw SCSI passthrough for vendor drive commands.
/usr/bin/redumper-rgui root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

%post
%set_permissions %{_bindir}/redumper-rgui

%verifyscript
%verify_permissions -e %{_bindir}/redumper-rgui

%files
%license LICENSE
%doc README.md
%{_bindir}/redumper-rgui
%{_datadir}/permissions/permissions.d/redumper-rgui

%changelog
* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 734-0
- Automated: consumer moved its bundled redumper build b734; the pin follows.

* Sun Jul 19 2026 gmipf <gmipf64@gmail.com> - 733-0
- Automated: consumer moved its bundled redumper to b733; the pin follows.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 729-0
- Add aarch64 (arm64) support: bundle the upstream linux-arm64 ZIP alongside
  linux-x64 and pick per build arch via %%ifarch; ExclusiveArch now
  x86_64 aarch64. Ships UNTESTED on arm64 (no hardware drive-access proof);
  the repackage path is architecture-neutral.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 729-3
- Renamed redumper729 -> redumper-rgui. The package name no longer carries the
  build number; the pinned build now lives at a FIXED name (/usr/bin/redumper-rgui)
  with the build number as the Version. When Redumper-GUI bundles a new redumper
  build the package upgrades in place instead of a new redumper<N> appearing and
  the old one being orphaned -- an in-place version bump migrates installed
  machines, a rename does not. Obsoletes redumper729 so existing installs move
  over. watch-consumer-pins.yml bumps this hourly; no manual step remains.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 729-0
- Set %%global _build_id_links none. With debug_package off these links point at
  debuginfo that does not exist -- and on EL they made this package collide with
  the rolling `redumper` when it reaches build 729: both ship the same upstream binary, so both claimed
  /usr/lib/.build-id/db/ea49...ce and `dnf install redumper mpf-cli` (mpf
  recommends redumper732) failed the transaction test. Fedora's rpm drops the
  links together with debug_package, EL's does not -- which is why building and
  testing on Fedora never showed it. Measured on CentOS Stream 10, 2026-07-16.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 729-0
- Initial openSUSE (OBS) packaging. Pinned-build compatibility package carrying
  upstream redumper b729 as /usr/bin/redumper729, for consumers coupled to that
  exact build. redumper-gui is the first: its upstream bundles b729 and states
  that other versions may not be supported, and it invokes redumper as a sibling
  of its own executable -- which a distribution package cannot honor by shipping
  a second /usr/bin/redumper.
- Co-installable with the rolling `redumper` package; no file overlaps, so a user
  can have the newest redumper on PATH and still run the GUI against the build it
  was tested with.
- cap_sys_rawio granted through the openSUSE permissions framework
  (permissions.d profile + %%set_permissions / %%verify_permissions), the
  distro-native equivalent of the Fedora spec's %%caps entry.
