%global debug_package %{nil}
# No debuginfo -> the /usr/lib/.build-id/ links rpm still makes on EL are dead
# weight, and they collide: this package ships the SAME upstream binary as the
# rolling `redumper` whenever that reaches this build, so both claim the same
# build-id path and cannot be installed together (measured on EL10 2026-07-16;
# Fedora's rpm drops them with debug_package, EL's does not). See redumper.spec.
%global _build_id_links none

# Compatibility package: the redumper build MPF is version-coupled to.
#
# MPF bundles a SPECIFIC upstream redumper build and is tested only against it.
# A distribution cannot ship a second /usr/bin/redumper, so this package carries
# that pinned build as /usr/bin/redumper-mpf, and MPF depends on it by this FIXED
# name. The rolling `redumper` package is left untouched for CLI users.
#
# The name is fixed; the VERSION tracks the bundled build. %%global rdbuild below
# is that build number (and the Version, and the Source tag), and
# .github/workflows/watch-consumer-pins.yml bumps it hourly from MPF's
# publish-nix.sh. So when MPF moves to b733 this package upgrades in place
# (redumper-mpf 732 -> 733) and every installed machine follows on the next
# upgrade. That is the whole point of keeping the build number OUT of the name:
# `dnf/zypper/apt upgrade` carries an in-place version bump across installs, but
# it does NOT follow a rename -- a build-number name would strand every machine
# on the old pin, silently.
#
# ⚠️ NEVER point MPF at the rolling `redumper`, not even on a day both carry the
# same build. The rolling package moves on its own; MPF has no version check and
# would silently dump with an untested build. This pin always matches what MPF
# bundles, because a watcher keeps its version equal to publish-nix.sh.
%global rdbuild 737

Name:           redumper-mpf
Version:        %{rdbuild}
Release:        0
Obsoletes:      redumper732 < 733
Summary:        redumper b%{rdbuild}, the build pinned by MPF

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

# Our own recipe file, given a URL for the same reason the upstream ones have
# one: download_files fetches whatever a Source: names, so declaring it here is
# what keeps it OUT of _service. That matters because _service lives in OBS and
# only an `osc commit` can change it; no token can. Every recipe file listed
# there makes _service a function of our file list, so adding or removing one
# needs a hand in OBS, and forgetting that hand surfaces as
# `broken: service error: ERROR 404`, which reads like an OBS outage and is our
# own dangling reference.
#
# Measured 2026-07-20 in a throwaway project: download_files follows a URL given
# in Patch: exactly as in Source:. The _service comment claiming a patch "would
# never be fetched" holds only for a patch with NO URL, and the rule that every
# recipe file must be listed in _service had been derived from it.
Source99:       https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/redumper-mpf/redumper-mpf-rpmlintrc

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

This package ships upstream build b%{rdbuild} as /usr/bin/redumper-mpf.
It exists so that tools which are version-coupled to a specific redumper
build get exactly the build they were tested against, no matter which
version the rolling `redumper` package currently carries. It is the build
MPF bundles, and the mpf packages point their configuration at it.

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
    %{buildroot}%{_bindir}/redumper-mpf
%else
install -m 0755 redumper-b%{rdbuild}-linux-x64/bin/redumper \
    %{buildroot}%{_bindir}/redumper-mpf
%endif

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

# Permissions framework profile: grant cap_sys_rawio for sudo-less SCSI
# passthrough (Plextor read method D8, Kreon commands, ...). The capability
# lives on the continuation line beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/redumper-mpf <<'EOF'
# redumper needs raw SCSI passthrough for vendor drive commands.
/usr/bin/redumper-mpf root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

%post
%set_permissions %{_bindir}/redumper-mpf

%verifyscript
%verify_permissions -e %{_bindir}/redumper-mpf

%files
%license LICENSE
%doc README.md
%{_bindir}/redumper-mpf
%{_datadir}/permissions/permissions.d/redumper-mpf

%changelog
* Fri Jul 31 2026 gmipf <gmipf64@gmail.com> - 737-0
- Automated: consumer moved its bundled redumper build b737; the pin follows.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 735-0
- Automated: consumer moved its bundled redumper build b735; the pin follows.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 732-0
- Add aarch64 (arm64) support: bundle the upstream linux-arm64 ZIP alongside
  linux-x64 and pick per build arch via %%ifarch; ExclusiveArch now
  x86_64 aarch64. Ships UNTESTED on arm64 (no hardware drive-access proof);
  the repackage path is architecture-neutral.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 732-3
- Renamed redumper732 -> redumper-mpf. The package name no longer carries the
  build number; the pinned build now lives at a FIXED name (/usr/bin/redumper-mpf)
  with the build number as the Version. When MPF bundles a new redumper build the
  package upgrades in place (732 -> 733) instead of a new redumper<N> appearing
  and the old one being orphaned -- an in-place version bump migrates installed
  machines on `dnf/zypper/apt upgrade`, a rename does not. Obsoletes redumper732
  so existing installs move over. watch-consumer-pins.yml bumps this hourly from
  MPF's publish-nix.sh; no manual step remains.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 732-0
- Set %%global _build_id_links none. With debug_package off these links point at
  debuginfo that does not exist -- and on EL they made this package collide with
  the rolling `redumper`, now also at build 732: both ship the same upstream binary, so both claimed
  /usr/lib/.build-id/db/ea49...ce and `dnf install redumper mpf-cli` (mpf
  recommends redumper732) failed the transaction test. Fedora's rpm drops the
  links together with debug_package, EL's does not -- which is why building and
  testing on Fedora never showed it. Measured on CentOS Stream 10, 2026-07-16.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 732-0
- Initial openSUSE (OBS) packaging. Pinned-build compatibility package carrying
  upstream redumper b732 as /usr/bin/redumper732 -- the build MPF's publish-nix.sh
  bundles. The mpf packages point their configuration at it, so an MPF dump runs
  the dumper build its upstream actually tested with.
- The pin exists even though the rolling `redumper` package carries the very same
  build today. That equality is an accident of timing: the rolling package moves,
  and the day b733 lands, an MPF pointed at it would silently dump with a build it
  was never tested against -- MPF has no version check of any kind to notice.
- Co-installable with the rolling `redumper` and with redumper729 (redumper-gui's
  pin); the build number is in the binary name, so no files overlap.
- cap_sys_rawio granted through the openSUSE permissions framework
  (permissions.d profile + %%set_permissions / %%verify_permissions), the
  distro-native equivalent of the Fedora spec's %%caps entry.
