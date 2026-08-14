%global debug_package %{nil}
# ...and with debuginfo off, the /usr/lib/.build-id/ links rpm still makes on EL
# point at debuginfo that does not exist. Worse, they COLLIDE: `redumper` and
# `redumper<N>` ship the same upstream binary whenever the rolling build equals a
# pinned one, so both claim the same build-id path and stop being co-installable.
# Measured 2026-07-16 on EL10 with rolling == 732: `dnf install redumper mpf-cli`
# (mpf recommends redumper732) died on "/usr/lib/.build-id/db/ea49...ce
# kollidiert". EL ONLY -- Fedora's rpm drops the links together with
# debug_package, EL's does not, which is exactly why building and testing on
# Fedora never showed it. aaru/aaru5/mpf already set this; these did not.
%global _build_id_links none

Name:           redumper
Version:        743
Release:        0
Summary:        A low-level byte-perfect CD disc dumper

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP. The binary
# inside is a single statically linked ELF (clang + libc++ + -static),
# built by upstream's own CI. Identical artifact to the Fedora/COPR lane.
#
# OBS builds are hermetic (no network in the build root), so these URLs are
# NOT fetched at build time - the _service (download_files, mode="manual")
# downloads them by basename and they are committed as package sources.
# rpmbuild then resolves each Source: to its basename in SOURCES.
Source0:        %{url}/releases/download/b%{version}/redumper-b%{version}-linux-x64.zip

# arm64 counterpart of Source0. Both arch ZIPs are bundled and the matching
# one is picked per build arch via %%ifarch (see %%prep / %%install). OBS builds
# ONE package source across every enabled arch, so an arch-conditional Source:
# would commit only one arch's binary; carrying both keeps the aarch64 build
# honest. Same %%{version} macro => the _service fetches and the watcher bumps
# both in lockstep.
Source4:        %{url}/releases/download/b%{version}/redumper-b%{version}-linux-arm64.zip

# LICENSE + README aren't shipped in the release zip; fetched separately
# from the same tag so %%license / %%doc work without a full source clone.
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{version}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{version}/README.md

# Handwritten manpage (upstream provides none), installed VERBATIM. It carries a
# FIXED marker naming the build its prose was written against (b724) and is
# deliberately NOT stamped with %%{version}: the text is maintained by hand and
# does not move when the package does, so a header that always named the shipped
# release would let an aging page keep claiming currency. A fixed marker lets the
# reader see their binary is newer. (Generated pages are the opposite case and do
# stamp -- see aaru, whose page is produced from --help at build time.)
# Local source, left alone by the service.
# The recipe files below carry a URL for the same reason the upstream sources do:
# download_files fetches whatever a Source: names, and that is what keeps them OUT
# of _service. _service lives in OBS and only an `osc commit` can change it, so
# every file listed there would make it a function of our file list. See
# opensuse/redumper-mpf/redumper-mpf.spec for the measurement behind this.
Source3:        https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/redumper/redumper.1

Source99:       https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/redumper/redumper-rpmlintrc

ExclusiveArch:  x86_64 aarch64
BuildRequires:  unzip

# openSUSE grants file capabilities through the permissions framework
# (chkstat), not a bare %%caps entry - the post-build permissions check
# rejects capabilities set outside it. We ship a permissions.d profile and
# apply/verify it via the standard scriptlet macros.
BuildRequires:  permissions
Requires(post): permissions
Requires(verify): permissions

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray. It supports advanced Plextor features (negative lead-in, read
method D8) and Xbox/Xbox 360 (XGD) dumping via Kreon firmware drives.
Primarily used by the Redump and No-Intro preservation projects.

This package grants the redumper binary the cap_sys_rawio file capability
(via the openSUSE permissions framework) so vendor SCSI passthrough commands
work without sudo.

%prep
%setup -q -c -T
%ifarch aarch64
unzip -q %{SOURCE4}
%else
unzip -q %{SOURCE0}
%endif

%build
# Self-contained statically linked binary; nothing to compile, and the manpage
# is installed verbatim (see Source3) rather than stamped.

%install
install -d %{buildroot}%{_bindir}
%ifarch aarch64
install -m 0755 redumper-b%{version}-linux-arm64/bin/redumper %{buildroot}%{_bindir}/redumper
%else
install -m 0755 redumper-b%{version}-linux-x64/bin/redumper %{buildroot}%{_bindir}/redumper
%endif

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

install -D -m 0644 %{SOURCE3} %{buildroot}%{_mandir}/man1/redumper.1

# Permissions framework profile: grant cap_sys_rawio for sudo-less SCSI
# passthrough (Plextor read method D8, Kreon commands, ...). The capability
# lives on the continuation line beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/redumper <<'EOF'
# redumper needs raw SCSI passthrough for vendor drive commands.
/usr/bin/redumper root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

%post
%set_permissions %{_bindir}/redumper

%verifyscript
%verify_permissions -e %{_bindir}/redumper

%files
%license LICENSE
%doc README.md
%{_bindir}/redumper
%{_datadir}/permissions/permissions.d/redumper
%{_mandir}/man1/redumper.1*

%changelog
* Fri Aug 14 2026 gmipf <gmipf64@gmail.com> - 743-0
- Automated sync to upstream redumper release b743.

* Tue Aug 11 2026 gmipf <gmipf64@gmail.com> - 742-0
- Automated sync to upstream redumper release b742.

* Fri Aug 07 2026 gmipf <gmipf64@gmail.com> - 741-0
- Automated sync to upstream redumper release b741.

* Tue Aug 04 2026 gmipf <gmipf64@gmail.com> - 740-0
- Automated sync to upstream redumper release b740.

* Fri Jul 31 2026 gmipf <gmipf64@gmail.com> - 739-0
- Automated sync to upstream redumper release b739.

* Thu Jul 30 2026 gmipf <gmipf64@gmail.com> - 737-0
- Automated sync to upstream redumper release b737.

* Mon Jul 27 2026 gmipf <gmipf64@gmail.com> - 736-0
- Automated sync to upstream redumper release b736.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 735-0
- Automated sync to upstream redumper release b735.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 734-0
- Automated sync to upstream redumper release b734.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 733-0
- Add aarch64 (arm64) support: bundle the upstream linux-arm64 ZIP alongside
  linux-x64 and pick per build arch via %%ifarch; ExclusiveArch now
  x86_64 aarch64. Ships UNTESTED on arm64 (no hardware drive-access proof);
  the repackage path is architecture-neutral.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 733-0
- Automated sync to upstream redumper release b733.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 732-0
- Set %%global _build_id_links none. With debug_package off these links point at
  debuginfo that does not exist -- and on EL they made this package collide with
  the redumper732 pin: both ship the same upstream binary, so both claimed
  /usr/lib/.build-id/db/ea49...ce and `dnf install redumper mpf-cli` (mpf
  recommends redumper732) failed the transaction test. Fedora's rpm drops the
  links together with debug_package, EL's does not -- which is why building and
  testing on Fedora never showed it. Measured on CentOS Stream 10, 2026-07-16.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 732-0
- Automated sync to upstream redumper release b732.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 731-0
- Initial openSUSE (OBS) packaging of redumper b731.
- Repackage of the upstream prebuilt static linux-x64 binary (identical
  artifact to the Fedora/COPR lane); sources fetched via the _service
  (download_files) and committed, since OBS build roots have no network.
- cap_sys_rawio granted through the openSUSE permissions framework
  (permissions.d profile + %%set_permissions / %%verify_permissions), the
  distro-native equivalent of the Fedora spec's %%caps entry.
