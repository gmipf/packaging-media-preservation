%global dicver       20260101
%global dicdir       %{_libdir}/%{name}

# Repackage — nothing to strip, nothing to debug-split.
%global debug_package %{nil}
%global __strip      /bin/true
%global __os_install_post %{nil}

Name:           discimagecreator
Version:        %{dicver}
Release:        3%{?dist}
Summary:        Low-level disc dumper plus EccEdc / DVDAuth / unscrambler helpers
License:        Apache-2.0 AND GPL-3.0-or-later AND GPL-2.0-or-later
URL:            https://github.com/saramibreak/DiscImageCreator

# Upstream Linux release tarball: all 4 binaries (DIC main + EccEdc +
# DVDAuth + unscrambler), all runtime data files, LICENSE, README and
# the full Doc/ collection pre-laid-out in a single directory. URL is
# from the release body (sarami links binaries inline in markdown
# rather than uploading them as proper release assets);
# watch-dic-releases.yml polls daily and rewrites this URL on a tag bump.
Source0:        https://github.com/user-attachments/files/24401509/DiscImageCreator_%{dicver}.tar.gz

# Handwritten manpage (upstream provides none); pinned to %%{dicver}.
Source1:        discimagecreator.1

ExclusiveArch:  x86_64
BuildRequires:  tar
BuildRequires:  gzip

%description
DiscImageCreator (DIC) is a command-line tool for byte-perfect dumping
of optical discs (CD, GD, DVD, HD-DVD, BD, GameCube, Wii, XBOX,
XBOX 360) and various disks (Floppy, MO, USB). It is one of the dumpers
supported by the Redump preservation project.

This RPM bundles four binaries from the same upstream author:

  * discimagecreator: main dumper (PATH aliases 'dic',
                      'DiscImageCreator.out' also provided for
                      compatibility with MPF and tooling that calls the
                      original upstream filename)
  * eccedc:           sector ECC/EDC validator/fixer
  * dvdauth:          CSS/CPPM/CPRM DVD authentication tool
  * unscrambler:      brute-force unscramble for non-standard DVD IVs

cap_sys_rawio is set on the main DIC binary and dvdauth so vendor SCSI
passthrough commands work without sudo. See discimagecreator(1) for
details on drive access and runtime data file locations.

Repackaged unmodified from the upstream linux_amd64 release tarball.

%prep
%setup -q -c -T
tar -xzf %{SOURCE0}

%build
# Self-contained binaries; nothing to compile.

%install
# All binaries, runtime data and docs are pre-laid-out by upstream in
# the DiscImageCreator/ tarball directory — we mirror that into %{dicdir}.
# DIC's GetCmd() resolves the three helpers via readlink(/proc/self/exe),
# so all four .out binaries MUST live in the same directory. Co-locating
# the data files there too means the binary's primary "next-to-exe"
# probe path finds them and the hardcoded /usr/share/DiscImageCreator/
# fallback in upstream get.cpp / xml.cpp never runs (no sed patch
# required, unlike the source build).
install -d %{buildroot}%{dicdir}
install -m 0755 DiscImageCreator/DiscImageCreator.out %{buildroot}%{dicdir}/DiscImageCreator.out
install -m 0755 DiscImageCreator/EccEdc.out           %{buildroot}%{dicdir}/EccEdc.out
install -m 0755 DiscImageCreator/DVDAuth.out          %{buildroot}%{dicdir}/DVDAuth.out
install -m 0755 DiscImageCreator/unscrambler.out      %{buildroot}%{dicdir}/unscrambler.out

install -m 0644 DiscImageCreator/C2ErrorProtect.txt   %{buildroot}%{dicdir}/
install -m 0644 DiscImageCreator/ReadErrorProtect.txt %{buildroot}%{dicdir}/
install -m 0644 DiscImageCreator/default.dat          %{buildroot}%{dicdir}/
install -m 0644 DiscImageCreator/driveOffset.txt      %{buildroot}%{dicdir}/
install -m 0644 "DiscImageCreator/DVDRawBruteforce - Drive Sheet - Sheet1.tsv" \
                                                      %{buildroot}%{dicdir}/

# /usr/bin/ symlinks — canonical lowercase, the 'dic' short alias and
# the upstream-name DiscImageCreator.out for MPF.Frontend compatibility
# (MPF defaults DiscImageCreatorPath to exactly that filename on Unix).
# Three lowercase helper aliases follow the same pattern.
install -d %{buildroot}%{_bindir}
ln -s ../%{_lib}/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/%{name}
ln -s ../%{_lib}/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/dic
ln -s ../%{_lib}/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/DiscImageCreator.out
ln -s ../%{_lib}/%{name}/EccEdc.out           %{buildroot}%{_bindir}/eccedc
ln -s ../%{_lib}/%{name}/DVDAuth.out          %{buildroot}%{_bindir}/dvdauth
ln -s ../%{_lib}/%{name}/unscrambler.out      %{buildroot}%{_bindir}/unscrambler

# Manpage + alias symlinks for every binary name a user might type.
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE1} %{buildroot}%{_mandir}/man1/%{name}.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/dic.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/eccedc.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/dvdauth.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/unscrambler.1

# License + README staged at the top level for %license / %doc.
install -p -m 0644 DiscImageCreator/LICENSE LICENSE
install -p -m 0644 DiscImageCreator/README.md README.md

%files
%license LICENSE
%doc README.md
%doc DiscImageCreator/Doc/Reference.md
%doc DiscImageCreator/Doc/TestedDrive.txt
%doc DiscImageCreator/Doc/KnownIssue.txt
%doc DiscImageCreator/Doc/ChangeLog.txt
%doc DiscImageCreator/Doc/Todo.txt
%doc "DiscImageCreator/Doc/Firmware&Tool.md"
%dir %{dicdir}
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{dicdir}/DiscImageCreator.out
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{dicdir}/DVDAuth.out
%{dicdir}/EccEdc.out
%{dicdir}/unscrambler.out
%{dicdir}/C2ErrorProtect.txt
%{dicdir}/ReadErrorProtect.txt
%{dicdir}/default.dat
%{dicdir}/driveOffset.txt
%{dicdir}/DVDRawBruteforce*.tsv
%{_bindir}/%{name}
%{_bindir}/dic
%{_bindir}/DiscImageCreator.out
%{_bindir}/eccedc
%{_bindir}/dvdauth
%{_bindir}/unscrambler
%{_mandir}/man1/%{name}.1*
%{_mandir}/man1/dic.1*
%{_mandir}/man1/eccedc.1*
%{_mandir}/man1/dvdauth.1*
%{_mandir}/man1/unscrambler.1*

%changelog
* Tue Jun 16 2026 gmipf <gmipf64@gmail.com> - 20260101-3
- Switch from 4-source-archive source build (DIC + EccEdc + DVDAuth +
  unscrambler) to repackage of the upstream linux_amd64 release
  tarball, which ships all four binaries plus runtime data and Doc/
  pre-laid-out in a single directory.
- Drops BuildRequires on gcc-c++, make, meson, ninja-build,
  libarchive-devel, openssl-devel, zlib-devel; build time per chroot
  drops from minutes to seconds. Removes the GCC-14 <cstdint> patch on
  EccEdc and the PIE makefile patches on the three helpers, since we
  no longer compile them.
- Removes the upstream-CamelCase data-dir probe-path sed patch. The
  binary's primary lookup is relative to /proc/self/exe, which now
  resolves to %{dicdir} where the data files live; the hardcoded
  /usr/share/DiscImageCreator/ fallback in upstream get.cpp / xml.cpp
  never fires.
- Source0 is sarami's release-body-linked Linux tarball
  (github.com/user-attachments/files/<id>/DiscImageCreator_<tag>.tar.gz);
  watch-dic-releases.yml parses the release body markdown and rewrites
  the URL on tag bumps.
- Layout migrates from %{_libexecdir}/discimagecreator/ to
  %{_libdir}/discimagecreator/ for consistency with the other binary-
  repackage RPMs in this project (mpf-*, aaru).
- Doc files now live under DiscImageCreator/Doc/ instead of
  Release_ANSI/Doc/ — upstream changed the bundle layout.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 20260101-2
- Manpage: add NOTES section pinning the manpage to DiscImageCreator
  tag 20260101 (helpers have effectively frozen syntax, not pinned),
  so staleness is obvious if upstream DIC syntax drifts

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 20260101-1
- Initial COPR build of DiscImageCreator suite (Phase 3.5)
- Bundles DiscImageCreator (Apache-2.0) plus three helper tools:
  EccEdc (GPL-3.0+), DVDAuth (GPL-2.0+), unscrambler (GPL-2.0+)
- Source builds for all four binaries; no upstream binary blobs
- Main DIC builds via meson against system libarchive/zlib/openssl
- Helper tools build via their bundled makefiles
- Real binaries live in %{_libexecdir}/discimagecreator/; /usr/bin/
  has lowercase aliases (discimagecreator, eccedc, dvdauth, unscrambler)
  plus dic short-form and DiscImageCreator.out for MPF compatibility
- cap_sys_rawio set on the main binary and DVDAuth.out for vendor SCSI
  passthrough commands without sudo
- Hardcoded /usr/share/DiscImageCreator/ probe path patched to lowercase
  /usr/share/discimagecreator/ in %prep
- Includes discimagecreator(1) manpage with symlinks for every alias
