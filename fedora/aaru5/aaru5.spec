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
Release:        2%{?dist}
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
# Static, hand-curated manpage (upstream ships none). @VERSION@/@DATE@ are
# stamped from %%{version} and the build date at %%build, so the .TH line
# always matches the shipped version without running the binary.
Source1:        aaru5.1
# udev rule granting the `cdrom` group access to USB floppy block devices
# so `aaru5 media dump` can read floppies without root. Package-unique
# filename so it never collides with the same rule shipped by `aaru`
# (v6) or `discimagecreator`, keeping all three co-installable.
Source2:        70-aaru5-floppy.rules

ExclusiveArch:  x86_64
BuildRequires:  tar
BuildRequires:  xz
# Provides %%{_udevrulesdir}.
BuildRequires:  systemd-rpm-macros

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
(optical dumping) work without sudo. A udev rule grants the `cdrom`
group access to USB floppy drives so floppy dumping works without root
too; add yourself with `usermod -aG cdrom <user>` and re-login.

%prep
# The binary tarball is rootless and drops its files directly into cwd.
%setup -q -c -T
tar -xJf %{SOURCE0}

%build
# Nothing to compile. Stamp the manpage's .TH version/date from the spec
# so it matches the shipped build (no binary execution — robust on every
# chroot including rawhide).
sed -e 's/@VERSION@/%{version}/g' \
    -e "s/@DATE@/$(date -u +%Y-%m-%d)/g" \
    %{SOURCE1} > aaru5.1

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

%files
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
