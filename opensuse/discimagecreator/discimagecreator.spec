# Rolling master snapshot. DIC has no semantic source version: its printed
# AppVersion is a build-TIME timestamp (appveyor.yml stamps buildDateTime.h
# from BUILD_DATE/BUILD_TIME) and the GitHub "release" tags (20260101) are
# just YYYYMMDD date labels -- so anchoring to a release tag conveys nothing.
# The package version is therefore simply the pinned commit's UTC timestamp
# plus short SHA: dicsnap = <YYYYMMDDHHMMSS>.<short-SHA>. watch-dic-releases
# rewrites dicsnap / diccommit on every new master commit; diccommit is the
# full SHA used for the source archive.
%global dicsnap      20260703121302.efa7d482
%global diccommit    efa7d4826f7e48b50d84cdd2a3d03cfb0321cf6b
%global eccedcver    20240901
%global dvdauthver   1.4
%global unscramblver 0.5.5

%global dicdir       %{_libexecdir}/%{name}

# Release builds are stripped; auto-generated debuginfo/debugsource
# subpackages would be empty / fail.
%global debug_package %{nil}

Name:           discimagecreator
Version:        %{dicsnap}
Release:        0
Summary:        Low-level disc dumper plus EccEdc / DVDAuth / unscrambler helpers
License:        Apache-2.0 AND GPL-3.0-or-later AND GPL-2.0-or-later
URL:            https://github.com/saramibreak/DiscImageCreator
# Source build (unlike the repackage tools). OBS build roots are hermetic
# (no network), so all four upstream archives are fetched by the _service
# (download_url, one per source with an explicit filename because these URLs
# use the `#/rename` convention rpm understands but download_files may not)
# and committed as package sources. The offline build is DIC's hermetic gate.
Source0:        %{url}/archive/%{diccommit}.tar.gz#/DiscImageCreator-%{diccommit}.tar.gz
Source1:        https://github.com/saramibreak/EccEdc/archive/refs/tags/%{eccedcver}.tar.gz#/EccEdc-%{eccedcver}.tar.gz
Source2:        https://github.com/saramibreak/DVDAuth/archive/refs/tags/v%{dvdauthver}.tar.gz#/DVDAuth-%{dvdauthver}.tar.gz
Source3:        https://github.com/saramibreak/unscrambler/archive/refs/tags/%{unscramblver}.tar.gz#/unscrambler-%{unscramblver}.tar.gz
Source4:        discimagecreator.1
# udev rule granting the `cdrom` group access to USB floppy block devices
# so DIC's `fd` (floppy dump) command can read floppies without root.
# Package-unique filename so it never collides with the same rule shipped
# by `aaru` (v6) or `aaru5` (stable), keeping all three co-installable.
Source5:        70-discimagecreator-floppy.rules
ExclusiveArch:  x86_64

BuildRequires:  gcc-c++
BuildRequires:  make
# Provides %%{_udevrulesdir}.
BuildRequires:  systemd-rpm-macros
BuildRequires:  meson
# Fedora/EL call the Ninja build tool 'ninja-build'; openSUSE calls it 'ninja'.
%if 0%{?suse_version}
BuildRequires:  ninja
%else
BuildRequires:  ninja-build
%endif
BuildRequires:  pkgconfig(libarchive)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  pkgconfig(zlib)
# openSUSE grants file capabilities through the permissions framework
# (chkstat), not a bare %%caps entry (see %%install / %%post).
BuildRequires:  permissions
Requires:       permissions
Requires(post): permissions
Requires(verify): permissions

%description
DiscImageCreator (DIC) is a command-line tool for byte-perfect dumping
of optical discs (CD, GD, DVD, HD-DVD, BD, GameCube, Wii, XBOX,
XBOX 360) and various disks (Floppy, MO, USB). It is one of the dumpers
supported by the Redump preservation project.

This RPM bundles four binaries from the same upstream author:

  * discimagecreator: main dumper (real binary in libexec; PATH aliases
                      'dic', 'DiscImageCreator.out' also provided for
                      compatibility with MPF and tooling that calls the
                      original upstream filename)
  * eccedc:           sector ECC/EDC validator/fixer
  * dvdauth:          CSS/CPPM/CPRM DVD authentication tool
  * unscrambler:      brute-force unscramble for non-standard DVD IVs

cap_sys_rawio is set on the main DIC binary and dvdauth (via the openSUSE
permissions framework) so vendor SCSI passthrough commands work without
sudo. A udev rule grants the `cdrom` group access to USB floppy drives so
the `fd` (floppy dump) command works without root too; add yourself with
`usermod -aG cdrom <user>` and re-login. See discimagecreator(1) for
details on drive access and runtime data file locations.

%prep
%setup -q -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 1 -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 2 -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 3 -n DiscImageCreator-%{diccommit}

# Patch hardcoded data-directory probe paths from upstream's CamelCase
# convention (/usr/share/DiscImageCreator/) to lowercase, so the binary
# finds its data files at /usr/share/discimagecreator/.
sed -i \
    -e 's|/usr/local/share/DiscImageCreator/|/usr/local/share/discimagecreator/|g' \
    -e 's|/usr/share/DiscImageCreator/|/usr/share/discimagecreator/|g' \
    DiscImageCreator/get.cpp \
    DiscImageCreator/xml.cpp

# GCC 15 (openSUSE Tumbleweed) no longer pulls <limits.h> in transitively,
# so _external/ps3auth/crypto_backend_openssl.c uses UINT_MAX without an
# explicit include and fails to compile. Prepend the header (a no-op
# everywhere it was already reachable).
sed -i '1i #include <limits.h>' \
    DiscImageCreator/_external/ps3auth/crypto_backend_openssl.c

# Upstream meson.build stages the Release_ANSI data files into the build
# dir "for easier testing" via fs.copyfile(), which needs meson >= 0.64.
# Older meson (e.g. EPEL 0.63.x) aborts configure there. They are pure
# build-tree convenience -- redundant with the install_data() below them
# and with our own install-step copies -- so drop them. grep-guard first so
# the build fails loudly if upstream ever restructures this block.
grep -q 'fs\.copyfile(' meson.build
sed -i '/fs\.copyfile(/d' meson.build

# Rename the bundled doc that upstream ships with an ampersand in its
# filename to a shell-safe name so older rpm doc-copy helpers don't choke.
mv 'Release_ANSI/Doc/Firmware&Tool.md' 'Release_ANSI/Doc/Firmware_and_Tool.md'

# EccEdc upstream 20240901 predates GCC 14's stricter transitive header
# rules — _external/ecm.cpp uses uint32_t without including <cstdint>.
sed -i '1i #include <cstdint>' \
    EccEdc-%{eccedcver}/EccEdc/_external/ecm.cpp

# All three helper makefiles omit -fPIE; the default ld invokes -pie (PIE
# hardening), which then rejects non-PIC relocations. Append -fPIE to the
# first CFLAGS/CXXFLAGS assignment in each makefile. LDFLAGS=-pie is added
# at make-invocation time in %build.
sed -i -e '0,/^CFLAGS\s*:=/{/^CFLAGS\s*:=/s/$/ -fPIE/}' \
       -e '0,/^CXXFLAGS\s*:=/{/^CXXFLAGS\s*:=/s/$/ -fPIE/}' \
    EccEdc-%{eccedcver}/EccEdc/makefile \
    DVDAuth-%{dvdauthver}/DVDAuth/makefile \
    unscrambler-%{unscramblver}/makefile

%build
# Main DiscImageCreator via meson against system openssl/zlib/libarchive
%meson
%meson_build

# Three helper tools via their bundled makefiles. CXX=g++ forces the
# compiler; LDFLAGS=-pie pairs with the -fPIE injection in %prep so the
# default PIE-hardened linker accepts the final binary.
make -C EccEdc-%{eccedcver}/EccEdc       CXX=g++ LDFLAGS=-pie %{?_smp_mflags}
make -C DVDAuth-%{dvdauthver}/DVDAuth    CXX=g++ LDFLAGS=-pie %{?_smp_mflags}
make -C unscrambler-%{unscramblver}      CXX=g++ LDFLAGS=-pie %{?_smp_mflags}

%install
# meson installs binary to %{_bindir}/DiscImageCreator and data files
# to %{_datadir}/DiscImageCreator/ (CamelCase project_name as subdir).
%meson_install

# Move binary into libexec under its upstream-original filename
# (DiscImageCreator.out — same .out convention as the helpers). All
# /usr/bin/ entries are symlinks added below.
install -d %{buildroot}%{dicdir}
mv %{buildroot}%{_bindir}/DiscImageCreator %{buildroot}%{dicdir}/DiscImageCreator.out

# Helper binaries land in libexec next to main DIC, with their original
# upstream filenames intact. DIC's GetCmd() uses readlink(/proc/self/exe)
# to find its own directory and then looks for ./EccEdc.out, ./DVDAuth.out,
# ./unscrambler.out — those exact filenames are mandatory here.
install -m 0755 EccEdc-%{eccedcver}/EccEdc/EccEdc.out         %{buildroot}%{dicdir}/EccEdc.out
install -m 0755 DVDAuth-%{dvdauthver}/DVDAuth/DVDAuth.out     %{buildroot}%{dicdir}/DVDAuth.out
install -m 0755 unscrambler-%{unscramblver}/unscrambler.out   %{buildroot}%{dicdir}/unscrambler.out

# Move meson-installed data dir from CamelCase to lowercase (matches the
# patched probe paths in get.cpp / xml.cpp).
mv %{buildroot}%{_datadir}/DiscImageCreator %{buildroot}%{_datadir}/%{name}

# Extra Release_ANSI data files referenced by the binary at runtime
# (default.dat + driveOffset.txt are already installed by meson).
install -m 0644 Release_ANSI/C2ErrorProtect.txt   %{buildroot}%{_datadir}/%{name}/
install -m 0644 Release_ANSI/ReadErrorProtect.txt %{buildroot}%{_datadir}/%{name}/
install -m 0644 "Release_ANSI/DVDRawBruteforce - Drive Sheet - Sheet1.tsv" \
                                                  %{buildroot}%{_datadir}/%{name}/

# /usr/bin/ symlinks. Three for the main binary (canonical lowercase,
# the 'dic' short alias, plus the upstream-name DiscImageCreator.out for
# MPF compatibility). Three lowercase helper aliases follow the same
# {alias -> upstream-name.out} pattern.
install -d %{buildroot}%{_bindir}
ln -s ../libexec/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/%{name}
ln -s ../libexec/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/dic
ln -s ../libexec/%{name}/DiscImageCreator.out %{buildroot}%{_bindir}/DiscImageCreator.out
ln -s ../libexec/%{name}/EccEdc.out           %{buildroot}%{_bindir}/eccedc
ln -s ../libexec/%{name}/DVDAuth.out          %{buildroot}%{_bindir}/dvdauth
ln -s ../libexec/%{name}/unscrambler.out      %{buildroot}%{_bindir}/unscrambler

# Static handwritten manpage (Source4) with symlink aliases for each
# binary name a user might type.
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE4} %{buildroot}%{_mandir}/man1/%{name}.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/dic.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/eccedc.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/dvdauth.1
ln -s %{name}.1 %{buildroot}%{_mandir}/man1/unscrambler.1

# udev rule for USB-floppy access (see Source5). No scriptlet needed: the
# udev package ships a file trigger on %{_udevrulesdir} that reloads rules
# automatically when this file lands.
install -D -m 0644 %{SOURCE5} \
    %{buildroot}%{_udevrulesdir}/70-discimagecreator-floppy.rules

# Permissions framework profile: grant cap_sys_rawio on the main dumper and
# DVDAuth for sudo-less SCSI passthrough. Each capability lives on the
# continuation line beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/discimagecreator <<EOF
# DIC main dumper and DVDAuth need raw SCSI passthrough for vendor commands.
%{dicdir}/DiscImageCreator.out root:root 0755
 +capabilities cap_sys_rawio=ep
%{dicdir}/DVDAuth.out root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

%post
%set_permissions %{dicdir}/DiscImageCreator.out %{dicdir}/DVDAuth.out

%verifyscript
%verify_permissions -e %{dicdir}/DiscImageCreator.out
%verify_permissions -e %{dicdir}/DVDAuth.out

%files
%license LICENSE
%doc README.md
%doc Release_ANSI/Doc/Reference.md
%doc Release_ANSI/Doc/TestedDrive.txt
%doc Release_ANSI/Doc/KnownIssue.txt
%doc Release_ANSI/Doc/ChangeLog.txt
%doc Release_ANSI/Doc/Todo.txt
%doc Release_ANSI/Doc/Firmware_and_Tool.md
%dir %{dicdir}
%attr(0755,root,root) %{dicdir}/DiscImageCreator.out
%attr(0755,root,root) %{dicdir}/DVDAuth.out
%{dicdir}/EccEdc.out
%{dicdir}/unscrambler.out
%{_bindir}/%{name}
%{_bindir}/dic
%{_bindir}/DiscImageCreator.out
%{_bindir}/eccedc
%{_bindir}/dvdauth
%{_bindir}/unscrambler
%{_datadir}/%{name}/
%{_mandir}/man1/%{name}.1*
%{_mandir}/man1/dic.1*
%{_mandir}/man1/eccedc.1*
%{_mandir}/man1/dvdauth.1*
%{_mandir}/man1/unscrambler.1*
%{_udevrulesdir}/70-discimagecreator-floppy.rules
%{_datadir}/permissions/permissions.d/discimagecreator

%changelog
* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-0
- Initial openSUSE (OBS) packaging of the DiscImageCreator suite
  (discimagecreator + EccEdc / DVDAuth / unscrambler helpers) from the
  pinned master commit efa7d482.
- Source build (DIC's hermetic gate): main dumper via meson against the
  system libarchive/openssl/zlib, three helpers via their makefiles. All
  four archives fetched by the _service (download_url, explicit filenames)
  and committed, since OBS build roots have no network. The %%prep source
  fix-ups (limits.h/cstdint prepends, meson fs.copyfile drop, -fPIE
  injection, data-dir lowercasing) are the same portability set proven
  under mock on Leap 15.6 + Tumbleweed; ninja is BuildRequired under its
  openSUSE name.
- cap_sys_rawio granted on the main dumper and DVDAuth through the openSUSE
  permissions framework (permissions.d profile + %%set_permissions /
  %%verify_permissions), the distro-native equivalent of the Fedora spec's
  %%caps entries.
