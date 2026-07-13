%global aaruver       5.4.2
%global aarutag       v%{aaruver}
%global aarudir       %{_libdir}/aaru5

# Prebuilt upstream binary, repackaged unmodified — nothing to compile,
# so no separate debug package / build-id links, and don't let rpm strip
# the shipped ELF (it is already stripped upstream).
%global debug_package %{nil}
%global __strip /bin/true
%global _build_id_links none

# Aaru 5.4.x ships the native SQLite provider libe_sqlite3.so alongside
# the executable; the app loads it from its own directory via .NET's
# NativeLibrary resolution (not the system linker). It is private to this
# package, so don't advertise it as a system-wide Provides.
%global __provides_exclude ^libe_sqlite3\.so

Name:           aaru5
Version:        5.4.2
Release:        6%{?dist}
Summary:        Aaru 5.x stable data-preservation CLI (MPF-compatible)

License:        GPL-3.0-or-later AND LGPL-2.1-or-later AND MIT
URL:            https://github.com/aaru-dps/Aaru

# Single-source repackage: the prebuilt linux_amd64 tarball carries the
# self-identifying `aaru` NativeAOT binary, its libe_sqlite3.so sidecar,
# and the LICENSE/README/Changelog. Building from source needs NuGet at
# build time, which COPR's build chroot cannot reach — so we repackage
# the upstream signed release binary instead. No source tarball is pulled
# because this package ships no icons/desktop/MIME integration (it is a
# headless CLI backend for MPF), unlike the rolling `aaru` (v6) package.
Source0:        %{url}/releases/download/%{aarutag}/aaru-%{aaruver}_linux_amd64.tar.xz
# Curated manpage template (upstream ships none) with a marker where the
# build-time generator splices in the live --help reference, plus the generator
# itself. Same approach as the rolling `aaru` (v6) package: a hand-maintained
# command list goes stale silently, a generated one cannot.
#
# The Aaru 5 CLI is a different generation from v6 (System.CommandLine vs
# Spectre.Console.Cli), so it needs its own parser -- "Commands:" not
# "COMMANDS:", two-space entries not four, comma-separated aliases, and an XML
# settings file instead of JSON. Hence a separate script rather than reuse.
Source1:        aaru5.1.in
Source3:        aaru5-manpage.sh
# udev rule tagging USB and legacy floppy block devices with "uaccess", so
# systemd-logind puts an ACL on the node for whoever is logged in at the local
# desktop seat and `aaru5 media dump` can read floppies with no group and no
# root. Package-unique filename so it never collides with the same rule shipped
# by `aaru` (v6) or `discimagecreator`, keeping all three co-installable.
Source2:        70-aaru5-floppy.rules

ExclusiveArch:  x86_64
BuildRequires:  tar
BuildRequires:  xz
# Provides %%{_udevrulesdir}.
BuildRequires:  systemd-rpm-macros

# The aaru5(1) command reference is generated at %%build time by RUNNING the
# shipped binary's `--help` (see %%build), so whatever the binary needs in order
# to start must be in the build root -- not merely at install time.
#
# The NativeAOT ELF's DT_NEEDED lists nothing exotic (libc, libstdc++, libz), so
# rpm's automatic dependency generator sees no runtime deps to declare. But the
# binary DLOPENS libicui18n/libicuuc (measured with `strings`), which no
# dependency scanner can see -- the same trap as with the GUI packages. libicu
# is therefore a genuine build requirement here, not a copy-paste from the v6
# spec. If any of these are ever missing the generator self-heals to the curated
# page with a note in place of the reference rather than failing the build, so a
# green build does NOT prove the reference was captured -- check the shipped page.
BuildRequires:  gawk
BuildRequires:  libicu
%if 0%{?suse_version}
BuildRequires:  krb5
BuildRequires:  libopenssl3
BuildRequires:  libz1
BuildRequires:  libunwind.so.8()(64bit)
%else
BuildRequires:  krb5-libs
BuildRequires:  libunwind
BuildRequires:  openssl-libs
BuildRequires:  zlib
%endif

# Aaru 5.4.x is a NativeAOT executable dynamically linked only against the
# standard C/C++ runtime (libc, libstdc++, libz, ...), so rpm's automatic
# dependency generator resolves every runtime dependency straight from the
# ELF — no hand-maintained Requires for a bundled .NET runtime are needed
# (that is a v6 self-contained-single-file concern; this build has none).

%description
Aaru is a cross-platform data-preservation suite: it dumps optical and
removable media (CD/DVD/HD-DVD/Blu-ray/UMD/floppy/magneto-optical) to
byte-perfect images, decodes filesystems, validates checksums and writes
CICM metadata.

This package ships the stable 5.4.x command-line release under the name
%{name} (binary /usr/bin/aaru5), the Aaru series that the Media
Preservation Frontend (MPF) drives for floppy and optical dumping. It
installs alongside the rolling `aaru` (v6 alpha) package without
conflict: separate binary name, library directory and manpage. Point
MPF's Aaru path at /usr/bin/aaru5.

cap_sys_rawio is set on the launcher so vendor SCSI passthrough commands
(optical dumping) work without sudo. A udev rule tags floppy drives with
`uaccess`, so the user logged in at the local desktop seat can dump them
without root and without joining any group. Headless, SSH and cron sessions
have no seat and therefore no ACL; dump as root there.

%prep
# The binary tarball is rootless and drops its files directly into cwd.
%setup -q -c -T
tar -xJf %{SOURCE0}

%build
# Nothing to compile. The manpage's COMMAND REFERENCE section is generated by
# walking the shipped binary's --help tree, so it is the binary's own text and
# cannot drift from the version installed. Stamping .TH from the binary is
# honest here precisely because the content is generated with it -- unlike a
# hand-written page, where a stamped header would keep claiming currency while
# the prose aged (see redumper.spec).
#
# The generator probes first whether the prebuilt binary runs in this build
# root; if it does not (a newer distro can ship runtime SONAMEs this .NET 5
# NativeAOT binary was never linked against), it emits the curated page with a
# short note instead of the reference and passes %{version} through, rather
# than failing the build.
sh %{SOURCE3} ./aaru %{SOURCE1} %{version} > aaru5.1

# ...and here we make sure that rescue path can never ship unnoticed. On OBS it
# fired SILENTLY (2026-07-13): the build went green while the packaged manpage
# carried no command reference at all, because Aaru read XDG_CONFIG_HOME instead
# of HOME, missed the generator's seeded GDPR settings, and died in its consent
# wizard for want of a TTY. Nobody inspects a green build. So: the page MUST
# contain the generated sub-command sections, or the build fails here.
grep -q '^\.SS aaru5 device' aaru5.1 || {
    echo "aaru5.1 has no generated command reference -- the generator fell back."
    echo "The build root could not run the binary; see its WARNINGs above."
    exit 1
}

%install
install -D -m 0755 aaru            %{buildroot}%{aarudir}/aaru
install -D -m 0755 libe_sqlite3.so %{buildroot}%{aarudir}/libe_sqlite3.so

install -D -m 0644 LICENSE.LGPL    %{buildroot}%{aarudir}/LICENSE.LGPL
install -D -m 0644 LICENSE.MIT     %{buildroot}%{aarudir}/LICENSE.MIT
install -D -m 0644 README.md       %{buildroot}%{aarudir}/README.md
install -D -m 0644 Changelog.md    %{buildroot}%{aarudir}/Changelog.md
install -D -m 0644 CONTRIBUTING.md %{buildroot}%{aarudir}/CONTRIBUTING.md

# Manpage (generated at %%build from the binary's own --help tree).
install -D -m 0644 aaru5.1 %{buildroot}%{_mandir}/man1/aaru5.1

# udev rule for USB-floppy access (see Source2). See the %%post scriptlet: the
# file trigger shipped by systemd-udev only RELOADS the rule set, which does
# nothing for a drive that is already plugged in.
install -D -m 0644 %{SOURCE2} \
    %{buildroot}%{_udevrulesdir}/70-aaru5-floppy.rules

# PATH entry — symlink (NOT a wrapper script) so the kernel propagates the
# cap_sys_rawio file capability across exec.
install -d %{buildroot}%{_bindir}
ln -sf %{aarudir}/aaru %{buildroot}%{_bindir}/aaru5

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
%dir %{aarudir}
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{aarudir}/aaru
%{aarudir}/libe_sqlite3.so
%{aarudir}/README.md
%{aarudir}/Changelog.md
%{aarudir}/CONTRIBUTING.md
%license %{aarudir}/LICENSE.LGPL
%license %{aarudir}/LICENSE.MIT
%{_bindir}/aaru5
%{_mandir}/man1/aaru5.1*
%{_udevrulesdir}/70-aaru5-floppy.rules

%changelog
* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 5.4.2-6
- Generate the aaru5(1) command reference from the shipped binary at build time
  instead of carrying a hand-written command list. A new generator
  (aaru5-manpage.sh) walks `aaru5 --help` across the full command tree (33
  sub-commands) and splices the verbatim reference into the curated aaru5.1.in
  template, so it can no longer drift from the installed version. Same approach
  the rolling `aaru` (v6) package already uses.
- The v6 generator could not simply be reused: Aaru 5 is a different CLI
  generation (System.CommandLine, not Spectre.Console.Cli). Its help says
  "Commands:" not "COMMANDS:", indents entries by two spaces not four, lists
  comma-separated aliases ("fi, filesystem, fs"), and stores settings as XML
  (Aaru.xml) rather than JSON -- so it needs its own parser and its own seeded
  config. On a fresh HOME the binary otherwise opens its interactive GDPR
  consent dialog and, with no TTY, aborts with SIGABRT.
- The generator picks the LONGEST alias for each command, because upstream is
  inconsistent about ordering: taking the first field would have produced
  `aaru5 fi info` in one place and `aaru5 database stats` in another.
- The .TH header keeps its build-time version stamp, and here that is honest:
  the reference is generated from the very binary being packaged, so content and
  version move together. (Hand-written pages get a FIXED marker instead -- see
  redumper 731-2 -- because there a stamped header would keep claiming currency
  while the prose aged.)
- BuildRequires the .NET native runtime libs (libicu, krb5, openssl, zlib,
  libunwind), since the generator now RUNS the binary in the build root. If they
  are ever missing the generator falls back to the curated page with a note in
  place of the reference rather than failing the build.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 5.4.2-5
- Apply the udev rule in %%post to drives that are ALREADY connected. The file
  trigger in systemd-udev only reloads the rule set, and only at the end of the
  transaction, which does nothing for a floppy that is plugged in at install
  time: measured, the node kept root:disk with no uaccess ACL and reads failed
  with EACCES until it was physically unplugged and replugged. %%post now
  reloads the rules and re-emits a change event for floppy block devices, so
  the drive is usable right after installing.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 5.4.2-4
- Own the private %{aarudir} directory in %%files. It was previously left
  unowned, so uninstalling the package orphaned /usr/lib64/aaru5. Surfaced by
  openSUSE's stricter 50-check-filelist post-build check (which fails the build
  on unowned directories, where Fedora only warns).

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 5.4.2-3
- Fix 70-aaru5-floppy.rules, which never fired. It matched
  ENV{ID_DRIVE_FLOPPY}, a property 80-udisks2.rules only sets at priority
  80 - after this rule runs at priority 70, and after 73-seat-late.rules
  has already applied the device ACL. Neither the GROUP="cdrom"/MODE=0660
  grant nor a uaccess tag could take effect at that point. The rule now
  matches ID_TYPE and ID_USB_TYPE (set by usb_id at priority 60) and tags
  the node "uaccess", so systemd-logind grants an ACL to the user at the
  local desktop seat.
- Floppy dumping now needs no group membership at all. Headless and SSH
  sessions have no seat and must dump as root: the node stays root:disk.
- Correct aaru5(1): it claimed logind does not apply a uaccess ACL to
  block devices. It does - /dev/sr* is one and is tagged by default. Also
  drop the false "add yourself to the cdrom group for floppy access"
  advice from the package description. The cdrom-group note for optical
  drives is a separate, still-correct mechanism and stays.

* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 5.4.2-2
- Ship a udev rule (70-aaru5-floppy.rules) that grants the cdrom group
  read/write on USB floppy block devices (ENV{ID_DRIVE_FLOPPY}) and the
  legacy /dev/fd* controller nodes, so `aaru5 media dump` can read
  floppies without root. Package-unique filename so it does not collide
  with the equivalent rule in `aaru` (v6) or `discimagecreator` and all
  three stay co-installable. Group cdrom is Fedora-native (no sysusers.d
  needed); users still add themselves with `usermod -aG cdrom <user>`.

* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 5.4.2-1
- Initial COPR build of Aaru 5.4.2 stable as a separate `aaru5` package.
  The Media Preservation Frontend (MPF) supports only the latest stable
  Aaru; the rolling v6 alpha shipped as `aaru` has an incompatible
  command interface and does not work in MPF. This package installs
  alongside `aaru` (separate binary /usr/bin/aaru5, libdir %{_libdir}/aaru5,
  manpage aaru5.1) so the rolling standalone build stays untouched.
- Repackage of the upstream prebuilt linux_amd64 NativeAOT binary plus its
  libe_sqlite3.so sidecar; no source tarball is pulled since this backend
  ships no icons/desktop/MIME integration. Native runtime deps resolve
  automatically from the ELF (NativeAOT links only standard libraries).
- Static, hand-curated manpage with build-time .TH version/date stamping;
  no binary execution at build time, so the build is robust on all chroots.
