# Rolling master snapshot. DIC has no semantic source version: its printed
# AppVersion is a build-TIME timestamp (appveyor.yml stamps buildDateTime.h
# from BUILD_DATE/BUILD_TIME) and the GitHub "release" tags (20260101) are
# just YYYYMMDD date labels -- so anchoring to a release tag conveys nothing.
# The package version is therefore simply the pinned commit's UTC timestamp
# plus short SHA: dicsnap = <YYYYMMDDHHMMSS>.<short-SHA>. That is monotonic
# (a later commit has a higher timestamp) and self-sufficient -- it already
# sorts above every prior build, including the old 20260101-N tag builds and
# the short-lived 20260101^<snap> (whose caret release-tag anchor was
# redundant and has been removed). We track master rather than the 20260101
# tag because master carries the Linux fixes -- notably the fd (floppy)
# SIGSEGV fix (#328) -- that the tag lacks. watch-dic-releases.yml rewrites
# dicsnap / diccommit on every new master commit; diccommit is the full SHA
# used for the source archive.
%global dicsnap      20260703121302.efa7d482
%global diccommit    efa7d4826f7e48b50d84cdd2a3d03cfb0321cf6b
%global eccedcver    20240901
%global dvdauthver   1.4
%global unscramblver 0.5.5

%global dicdir       %{_libexecdir}/%{name}

# Release builds are stripped; auto-generated debuginfo/debugsource
# subpackages would be empty / fail.
%global debug_package %{nil}
# No sibling ships this ELF, so this package cannot hit the build-id collision
# that made redumper and redumper732 un-co-installable on EL (see redumper.spec).
# But with debug_package off the links point at debuginfo that does not exist, so
# they are dead weight regardless -- and uniform with every other spec here.
%global _build_id_links none

Name:           discimagecreator
Version:        %{dicsnap}
Release:        5%{?dist}
Summary:        Low-level disc dumper plus EccEdc / DVDAuth / unscrambler helpers
License:        Apache-2.0 AND GPL-3.0-or-later AND GPL-2.0-or-later
URL:            https://github.com/saramibreak/DiscImageCreator
Source0:        %{url}/archive/%{diccommit}.tar.gz#/DiscImageCreator-%{diccommit}.tar.gz
Source1:        https://github.com/saramibreak/EccEdc/archive/refs/tags/%{eccedcver}.tar.gz#/EccEdc-%{eccedcver}.tar.gz
Source2:        https://github.com/saramibreak/DVDAuth/archive/refs/tags/v%{dvdauthver}.tar.gz#/DVDAuth-%{dvdauthver}.tar.gz
Source3:        https://github.com/saramibreak/unscrambler/archive/refs/tags/%{unscramblver}.tar.gz#/unscrambler-%{unscramblver}.tar.gz
Source4:        discimagecreator.1
# udev rule tagging USB and legacy floppy block devices with "uaccess", so
# systemd-logind puts an ACL on the node for whoever is logged in at the local
# desktop seat and DIC's `fd` (floppy dump) command can read floppies with no
# group and no root. Package-unique filename so it never collides with the same
# rule shipped by `aaru` (v6) or `aaru5` (stable), keeping all three
# co-installable.
Source5:        70-discimagecreator-floppy.rules
ExclusiveArch:  x86_64 aarch64

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
passthrough commands work without sudo. A udev rule tags floppy drives with
`uaccess`, so the user logged in at the local desktop seat can use the `fd`
(floppy dump) command without root and without joining any group. Headless,
SSH and cron sessions have no seat and therefore no ACL; dump as root there.
See discimagecreator(1) for details on drive access and runtime data file
locations.

%prep
%setup -q -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 1 -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 2 -n DiscImageCreator-%{diccommit}
%setup -q -T -D -a 3 -n DiscImageCreator-%{diccommit}

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

# GCC 15 (openSUSE Tumbleweed and, in time, Fedora) no longer pulls
# <limits.h> in transitively, so _external/ps3auth/crypto_backend_openssl.c
# uses UINT_MAX without an explicit include and fails to compile. Prepend
# the header (a no-op everywhere it was already reachable). mv/sed fail
# loudly under set -e if upstream ever drops the file.
sed -i '1i #include <limits.h>' \
    DiscImageCreator/_external/ps3auth/crypto_backend_openssl.c

# Upstream meson.build stages the Release_ANSI data files into the build
# dir "for easier testing" via fs.copyfile(), which needs meson >= 0.64.
# EL9's EPEL ships meson 0.63.x, so those calls abort configure there.
# They are pure build-tree convenience -- redundant with the install_data()
# right below them and with our own install-step copies of the same files --
# so drop them. The installed package is byte-identical on every distro
# (Fedora's newer meson doesn't need them either). grep-guard first so the
# build fails loudly if upstream ever restructures this block.
grep -q 'fs\.copyfile(' meson.build
sed -i '/fs\.copyfile(/d' meson.build

# rpm's %doc copy helper on EL9 (rpm 4.16) doesn't quote filenames, so the
# '&' in upstream's "Firmware&Tool.md" backgrounds the cp and the file never
# reaches the doc dir (works on Fedora / EL10 rpm 4.19+, fails on EL9). Rename
# it to a shell-safe name -- it's pure documentation, nothing references the
# filename. mv fails loudly under set -e if upstream ever renames it.
mv 'Release_ANSI/Doc/Firmware&Tool.md' 'Release_ANSI/Doc/Firmware_and_Tool.md'

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

# udev rule for USB-floppy access (see Source5). See the %%post scriptlet: the
# file trigger shipped by systemd-udev only RELOADS the rule set, which does
# nothing for a drive that is already plugged in.
install -D -m 0644 %{SOURCE5} \
    %{buildroot}%{_udevrulesdir}/70-discimagecreator-floppy.rules

%post
# Make the udev rule take effect on drives that are ALREADY connected. The file
# trigger in systemd-udev only reloads the rule set, and it runs at the very end
# of the transaction, so a floppy plugged in right now would keep its old
# permissions until it is physically unplugged and replugged. Reload the rules
# and re-emit a change event for floppy block devices instead. Measured: after
# the reload alone the node still has no uaccess ACL and reads fail with EACCES;
# the trigger grants it. Best effort - a container or chroot has no udevd.
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --property-match=ID_TYPE=floppy --action=change >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --property-match=ID_USB_TYPE=floppy --action=change >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --sysname-match='fd[0-9]*' --action=change >/dev/null 2>&1 || :

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
* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-5
- Add aarch64 (arm64) support: ExclusiveArch is now x86_64 aarch64. Unlike the
  repackaged tools this one is BUILT FROM SOURCE, so there is no arch-specific
  archive to bundle -- the four upstream sources are simply compiled natively on
  the aarch64 builders. arm64 ships UNTESTED -- no hardware drive-access proof
  exists for it; nothing in the packaging is architecture-specific, but this is
  deliberately not claimed as proven.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-4
- Set %%global _build_id_links none, for uniformity with every other spec here.
  No sibling ships this ELF, so this package cannot hit the build-id collision
  that made redumper and redumper732 un-co-installable on EL -- but with
  debug_package off the links are dead weight regardless (they point at
  debuginfo that does not exist). Measured on CentOS Stream 10, 2026-07-16.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-3
- Apply the udev rule in %%post to drives that are ALREADY connected. The file
  trigger in systemd-udev only reloads the rule set, and only at the end of the
  transaction, which does nothing for a floppy that is plugged in at install
  time: measured, the node kept root:disk with no uaccess ACL and reads failed
  with EACCES until it was physically unplugged and replugged. %%post now
  reloads the rules and re-emits a change event for floppy block devices, so
  the drive is usable right after installing.

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-2
- Fix 70-discimagecreator-floppy.rules, which never fired. It matched
  ENV{ID_DRIVE_FLOPPY}, a property 80-udisks2.rules only sets at priority
  80 - after this rule runs at priority 70, and after 73-seat-late.rules
  has already applied the device ACL. Neither the GROUP="cdrom"/MODE=0660
  grant nor a uaccess tag could take effect at that point. The rule now
  matches ID_TYPE and ID_USB_TYPE (set by usb_id at priority 60) and tags
  the node "uaccess", so systemd-logind grants an ACL to the user at the
  local desktop seat.
- The fd (floppy dump) command now needs no group membership at all.
  Headless and SSH sessions have no seat and must run it as root: the
  node stays root:disk.
- Drop the false "add yourself to the cdrom group for floppy access"
  advice from the package description. The cdrom-group note for optical
  drives is a separate, still-correct mechanism and stays.

* Fri Jul 03 2026 gmipf <gmipf64@gmail.com> - 20260703121302.efa7d482-1
- Automated master-snapshot sync to upstream DiscImageCreator commit
  efa7d482 (committed 20260703121302 UTC); Release reset to 1.
- Portability for RHEL/EPEL (el8/el9/el10) and CentOS Stream. Drop upstream
  meson.build's fs.copyfile() asset-staging lines (they need meson >= 0.64;
  EL8/EL9 ship 0.58/0.63): those only copy Release_ANSI data into the build
  tree for local testing and are redundant with install_data and the spec's
  own install step. Rename the bundled doc that upstream ships with an
  ampersand in its filename to a shell-safe name, so the older rpm doc-copy
  helper on EL8/EL9 (unquoted) does not choke on it. The installed binary and
  data files are byte-identical on every distro; on EL8 meson links the
  vendor-maintained system openssl 1.1.1k (DIC uses openssl only for dump
  hashing, not TLS).
- Portability for openSUSE (Leap 15.6 + Tumbleweed): BuildRequire the Ninja
  build tool under its openSUSE name `ninja` (Fedora/EL call it ninja-build),
  and prepend <limits.h> to _external/ps3auth/crypto_backend_openssl.c so it
  compiles under GCC 15 (Tumbleweed), which no longer pulls that header in
  transitively. Both are no-ops on Fedora/EL. Verified with mock on both
  openSUSE chroots.

* Fri Jul 03 2026 gmipf <gmipf64@gmail.com> - 20260703012003.df4abb11-1
- Drop the redundant `20260101^` release-tag anchor from the version. DIC has
  no semantic source version -- its AppVersion is a build-time timestamp
  (appveyor.yml stamps buildDateTime.h) and the GitHub "release" tags are
  bare YYYYMMDD date labels -- so pinning a master snapshot to a stale release
  tag was meaningless. The version is now just the commit's UTC timestamp plus
  short SHA (<YYYYMMDDHHMMSS>.<short-SHA>), matching DIC's own date/time
  identity while staying pinned and reproducible. Sorts above the previous
  20260101^... build, so it is a normal dnf upgrade; Release stays 1.

* Fri Jul 03 2026 gmipf <gmipf64@gmail.com> - 20260101^20260703012003.df4abb11-1
- Switch Source0 from the 20260101 release tarball to a pinned master commit
  (df4abb11, committed 2026-07-03), 19 commits ahead of the last release. This
  brings the accumulated Linux fixes (#310-#324) and, above all, the fd
  (floppy) SIGSEGV fix plus the write-protected-media read-only fallback
  (#328): DIC's `fd` floppy-dump command no longer crashes on Linux.
- Version scheme is now an mpf-style rolling snapshot pinned to the upstream
  commit SHA: 20260101^<UTC-commit-TS>.<short-SHA>. The caret (post-
  release) sorts the snapshot after the 20260101 release -- and above the
  shipped 20260101-6 -- but below the next release tag; Release reset to 1.
  watch-dic-releases.yml now tracks master HEAD instead of releases/latest.

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
