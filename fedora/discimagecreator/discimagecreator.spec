%global dicver       20260101
%global eccedcver    20240901
%global dvdauthver   1.4
%global unscramblver 0.5.5

%global dicdir       %{_libexecdir}/%{name}

# Release builds are stripped; auto-generated debuginfo/debugsource
# subpackages would be empty / fail.
%global debug_package %{nil}

Name:           discimagecreator
Version:        %{dicver}
Release:        6%{?dist}
Summary:        Low-level disc dumper plus EccEdc / DVDAuth / unscrambler helpers
License:        Apache-2.0 AND GPL-3.0-or-later AND GPL-2.0-or-later
URL:            https://github.com/saramibreak/DiscImageCreator
Source0:        https://github.com/saramibreak/DiscImageCreator/archive/refs/tags/%{dicver}.tar.gz#/DiscImageCreator-%{dicver}.tar.gz
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
BuildRequires:  ninja-build
BuildRequires:  pkgconfig(libarchive)
BuildRequires:  pkgconfig(openssl)
BuildRequires:  pkgconfig(zlib)

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

cap_sys_rawio is set on the main DIC binary and dvdauth so vendor SCSI
passthrough commands work without sudo. A udev rule grants the `cdrom`
group access to USB floppy drives so the `fd` (floppy dump) command works
without root too; add yourself with `usermod -aG cdrom <user>` and
re-login. See discimagecreator(1) for details on drive access and
runtime data file locations.

%prep
%setup -q -n DiscImageCreator-%{dicver}
%setup -q -T -D -a 1 -n DiscImageCreator-%{dicver}
%setup -q -T -D -a 2 -n DiscImageCreator-%{dicver}
%setup -q -T -D -a 3 -n DiscImageCreator-%{dicver}

# Patch hardcoded data-directory probe paths from upstream's CamelCase
# convention (/usr/share/DiscImageCreator/) to lowercase, so the binary
# finds its data files at /usr/share/discimagecreator/ which matches the
# Fedora packaging convention used here. Touches two source files; if
# upstream ever moves these strings the patch fails loudly.
sed -i \
    -e 's|/usr/local/share/DiscImageCreator/|/usr/local/share/discimagecreator/|g' \
    -e 's|/usr/share/DiscImageCreator/|/usr/share/discimagecreator/|g' \
    DiscImageCreator/get.cpp \
    DiscImageCreator/xml.cpp

# EccEdc upstream 20240901 predates GCC 14's stricter transitive header
# rules — _external/ecm.cpp uses uint32_t without including <cstdint>.
# Prepend the include so Fedora 43+ (GCC 14) builds.
sed -i '1i #include <cstdint>' \
    EccEdc-%{eccedcver}/EccEdc/_external/ecm.cpp

# All three helper makefiles omit -fPIE; Fedora's default ld invokes -pie
# (PIE hardening), which then rejects non-PIC relocations from the .o
# files. Append -fPIE to the first CFLAGS/CXXFLAGS assignment in each
# makefile so the implicit %.o rules pick it up. LDFLAGS=-pie is added
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
# compiler (the makefiles default to $(CXX) which may not be set in COPR
# clean chroots). LDFLAGS=-pie pairs with the -fPIE injection in %prep
# so Fedora's default PIE-hardened linker accepts the final binary.
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
# MPF compatibility — MPF.Frontend defaults DiscImageCreatorPath to
# exactly that filename on Unix). Three lowercase helper aliases follow
# the same {alias → upstream-name.out} pattern.
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

%files
%license LICENSE
%doc README.md
%doc Release_ANSI/Doc/Reference.md
%doc Release_ANSI/Doc/TestedDrive.txt
%doc Release_ANSI/Doc/KnownIssue.txt
%doc Release_ANSI/Doc/ChangeLog.txt
%doc Release_ANSI/Doc/Todo.txt
%doc Release_ANSI/Doc/Firmware&Tool.md
%dir %{dicdir}
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{dicdir}/DiscImageCreator.out
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{dicdir}/DVDAuth.out
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

%changelog
* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 20260101-6
- Ship a udev rule (70-discimagecreator-floppy.rules) that grants the
  cdrom group read/write on USB floppy block devices
  (ENV{ID_DRIVE_FLOPPY}) and the legacy /dev/fd* controller nodes, so
  DIC's `fd` floppy-dump command can read floppies without root.
  Package-unique filename so it does not collide with the equivalent rule
  in `aaru` (v6) or `aaru5` (stable) and all three stay co-installable.
  Group cdrom is Fedora-native (no sysusers.d needed); users still add
  themselves with `usermod -aG cdrom <user>`.

* Sat Jun 27 2026 gmipf <gmipf64@gmail.com> - 20260101-5
- Manpage: reword NOTES to state plainly that the page is handwritten and
  intentionally static (not generated or build-time stamped), based on
  upstream tag 20260101; a fixed version marker rather than a dynamic one
  that would imply per-release freshness the body does not have
- Manpage: correct a stale "--help" reference (DIC has no --help; its
  usage prints when the binary is run with no arguments)
- Manpage: drop an inaccurate pointer that cited Release_ANSI/Doc/
  Reference.md (a list of disc-format spec links, not a command
  reference) as authoritative for commands

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
