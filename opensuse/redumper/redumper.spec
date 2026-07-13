%global debug_package %{nil}

Name:           redumper
Version:        732
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
Source3:        redumper.1

ExclusiveArch:  x86_64
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
unzip -q %{SOURCE0}

%build
# Self-contained statically linked binary; nothing to compile, and the manpage
# is installed verbatim (see Source3) rather than stamped.

%install
install -d %{buildroot}%{_bindir}
install -m 0755 redumper-b%{version}-linux-x64/bin/redumper %{buildroot}%{_bindir}/redumper

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
