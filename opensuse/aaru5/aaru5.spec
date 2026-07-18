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
Release:        0
Summary:        Aaru 5.x stable data-preservation CLI (MPF-compatible)

License:        GPL-3.0-or-later AND LGPL-2.1-or-later AND MIT
URL:            https://github.com/aaru-dps/Aaru

# Single-source repackage: the prebuilt linux_amd64 tarball carries the
# self-identifying `aaru` NativeAOT binary, its libe_sqlite3.so sidecar,
# and the LICENSE/README/Changelog. OBS build roots are hermetic (no
# network), so this URL is fetched by the _service (download_files) and
# committed as a package source, not pulled at build time.
Source0:        %{url}/releases/download/%{aarutag}/aaru-%{aaruver}_linux_amd64.tar.xz
# arm64 counterpart of Source0 (the NativeAOT binary + its libe_sqlite3.so
# sidecar, both arch-specific). Bundled so the one package source builds on every
# enabled arch; extracted whole in %%prep via %%ifarch so BOTH the binary and the
# sidecar are swapped. Same version macro => the _service fetches and the watcher
# bumps both in lockstep. Travels the Debian lane as a Debtransform-Files extra.
Source4:        %{url}/releases/download/%{aarutag}/aaru-%{aaruver}_linux_arm64.tar.xz
# Curated manpage template with a marker where the build-time generator splices
# in the live --help reference, plus the generator itself. Same approach as the
# rolling `aaru` (v6) package: a hand-maintained command list goes stale
# silently, a generated one cannot. Aaru 5's CLI is a different generation from
# v6 (System.CommandLine vs Spectre.Console.Cli), so it needs its own parser --
# hence a separate script rather than reuse (see fedora/aaru5 for the details).
Source1:        aaru5.1.in
Source3:        aaru5-manpage.sh
# udev rule tagging USB and legacy floppy block devices with "uaccess", so
# systemd-logind puts an ACL on the node for whoever is logged in at the local
# desktop seat and `aaru5 media dump` can read floppies with no group and no
# root. Package-unique filename so it never collides with the same rule shipped
# by `aaru` (v6) or `discimagecreator`, keeping all three co-installable.
Source2:        70-aaru5-floppy.rules

ExclusiveArch:  x86_64 aarch64
BuildRequires:  tar
BuildRequires:  xz
# Provides %%{_udevrulesdir}.
BuildRequires:  systemd-rpm-macros

# The generator RUNS the shipped binary at %%build time, so its native runtime
# deps must be in the build root, not just at install time. openSUSE names them
# differently from Fedora/EL; libunwind is 'libunwind' on Leap but 'libunwind8'
# on Tumbleweed, so require it by its stable soname.
BuildRequires:  gawk
BuildRequires:  libicu
BuildRequires:  krb5
BuildRequires:  libopenssl3
BuildRequires:  libz1
BuildRequires:  libunwind.so.8()(64bit)
# openSUSE grants file capabilities through the permissions framework
# (chkstat), not a bare %%caps entry (see %%install / %%post).
BuildRequires:  permissions
Requires:       permissions
Requires(post): permissions
Requires(verify): permissions

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

cap_sys_rawio is set on the launcher (via the openSUSE permissions
framework) so vendor SCSI passthrough commands (optical dumping) work
without sudo. A udev rule tags floppy drives with `uaccess`, so the user
logged in at the local desktop seat can dump them without root and without
joining any group. Headless, SSH and cron sessions have no seat and
therefore no ACL; dump as root there.

%prep
# The binary tarball is rootless and drops its files directly into cwd.
%setup -q -c -T
%ifarch aarch64
tar -xJf %{SOURCE4}
%else
tar -xJf %{SOURCE0}
%endif

%build
# Nothing to compile. The manpage's COMMAND REFERENCE section is generated by
# walking the shipped binary's --help tree, so it is the binary's own text and
# cannot drift from the version installed. Stamping .TH from the binary is
# honest here precisely because the content is generated with it -- unlike a
# hand-written page, where a stamped header would keep claiming currency while
# the prose aged (see redumper.spec).
#
# The generator probes first whether the prebuilt binary runs in this build root
# and, if it does not, emits the curated page with a short note in place of the
# reference rather than failing the build.
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

# Manpage (static, stamped at %build).
install -D -m 0644 aaru5.1 %{buildroot}%{_mandir}/man1/aaru5.1

# udev rule for USB-floppy access (see Source2). No scriptlet needed:
# the udev package ships a file trigger on %{_udevrulesdir} that reloads
# rules automatically when this file lands.
install -D -m 0644 %{SOURCE2} \
    %{buildroot}%{_udevrulesdir}/70-aaru5-floppy.rules

# PATH entry — symlink (NOT a wrapper script) so the kernel propagates the
# cap_sys_rawio file capability across exec.
install -d %{buildroot}%{_bindir}
ln -sf %{aarudir}/aaru %{buildroot}%{_bindir}/aaru5

# Permissions framework profile: grant cap_sys_rawio on the real binary for
# sudo-less SCSI passthrough. The capability lives on the continuation line
# beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/aaru5 <<EOF
# aaru5 needs raw SCSI passthrough for vendor drive commands.
%{aarudir}/aaru root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

%post
%set_permissions %{aarudir}/aaru
# Make the udev rule take effect on drives that are ALREADY connected. The file
# trigger shipped by udev only reloads the rule set, and it runs at the very end
# of the transaction, so a floppy plugged in right now would keep its old
# permissions until it is physically unplugged and replugged. Reload the rules
# and re-emit a change event for floppy block devices instead. Measured: after
# the reload alone the node still has no uaccess ACL and reads fail with EACCES;
# the trigger grants it. Best effort - a container or chroot has no udevd.
udevadm control --reload-rules >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --property-match=ID_TYPE=floppy --action=change >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --property-match=ID_USB_TYPE=floppy --action=change >/dev/null 2>&1 || :
udevadm trigger --subsystem-match=block --sysname-match='fd[0-9]*' --action=change >/dev/null 2>&1 || :

%verifyscript
%verify_permissions -e %{aarudir}/aaru

%files
%dir %{aarudir}
%attr(0755,root,root) %{aarudir}/aaru
%{aarudir}/libe_sqlite3.so
# %%doc/%%license MARK these as documentation instead of merely shipping them, so
# `rpm -qd` lists them and --excludedocs can drop them. On an ABSOLUTE path the
# marker only tags: the files stay in %%{aarudir} beside the binary — upstream's
# own spec keeps them next to it too (in /opt/Aaru) — they are NOT relocated to
# %%{_docdir}. Same intent as the Debian lane, where debhelper picks Changelog.md
# up as the package's upstream changelog.
%doc %{aarudir}/README.md
%doc %{aarudir}/Changelog.md
%doc %{aarudir}/CONTRIBUTING.md
%license %{aarudir}/LICENSE.LGPL
%license %{aarudir}/LICENSE.MIT
%{_bindir}/aaru5
%{_mandir}/man1/aaru5.1*
%{_udevrulesdir}/70-aaru5-floppy.rules
%{_datadir}/permissions/permissions.d/aaru5

%changelog
* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 5.4.2-0
- Add aarch64 (arm64) support: bundle the upstream linux_arm64 tarball (NativeAOT
  binary + its libe_sqlite3.so sidecar) alongside linux_amd64 and extract the
  matching one whole per build arch via %%ifarch; ExclusiveArch now x86_64
  aarch64. The build-time manpage generator runs the arm64 binary natively on the
  aarch64 builder (the hard guard below still fails loudly on any silent
  fallback). Ships UNTESTED on arm64 (no hardware drive-access proof); the
  repackage path is architecture-neutral.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 5.4.2-0
- Mark README.md, Changelog.md and CONTRIBUTING.md as %%doc. They were already
  installed, but unmarked, so rpm did not know they were documentation: `rpm -qd
  aaru5` came back empty and --excludedocs kept them. The files do not move --
  %%doc on an absolute path only tags. Inherited from upstream's own spec, which
  ships all three unmarked in /opt/Aaru; the Debian lane already had it right,
  where debhelper installs Changelog.md as the package's upstream changelog.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 5.4.2-0
- Apply the udev rule in %%post to drives that are ALREADY connected. The file
  trigger shipped by udev only reloads the rule set, and only at the end of the
  transaction, which does nothing for a floppy that is plugged in at install
  time: measured, the node kept root:disk with no uaccess ACL and reads failed
  with EACCES until it was physically unplugged and replugged. %%post now
  reloads the rules and re-emits a change event for floppy block devices, so
  the drive is usable right after installing.

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 5.4.2-0
- Fix 70-aaru5-floppy.rules before it is ever published. It matched
  ENV{ID_DRIVE_FLOPPY}, a property 80-udisks2.rules only sets at priority
  80 - after this rule runs at priority 70, and after 73-seat-late.rules
  has already applied the device ACL, so it never fired. It now matches
  ID_TYPE and ID_USB_TYPE (set by usb_id at priority 60) and tags the node
  "uaccess", letting systemd-logind grant an ACL to the local-seat user.
- Floppy dumping needs no group membership. This also sidesteps openSUSE
  Leap 16 having no floppy group at all. Headless sessions have no seat
  and must dump as root: the node stays root:disk.
- Correct aaru5(1): it claimed logind does not apply a uaccess ACL to
  block devices. It does - /dev/sr* is one and is tagged by default. Also
  drop the false cdrom-group advice for floppies from the description.

* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 5.4.2-0
- Initial openSUSE (OBS) packaging of Aaru 5.4.2 stable as `aaru5`.
- Repackage of the upstream prebuilt linux_amd64 NativeAOT binary plus its
  libe_sqlite3.so sidecar (identical artifact to the Fedora/COPR lane);
  Source0 fetched via the _service (download_files) and committed, since
  OBS build roots have no network. Native runtime deps resolve from the ELF.
- cap_sys_rawio granted through the openSUSE permissions framework
  (permissions.d profile + %%set_permissions / %%verify_permissions), the
  distro-native equivalent of the Fedora spec's %%caps entry.
- udev rule (70-aaru5-floppy.rules) grants the cdrom group access to USB
  floppy block devices; package-unique so aaru/aaru5/discimagecreator stay
  co-installable.
