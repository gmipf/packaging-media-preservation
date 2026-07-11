%global aaruver       6.0.0
%global aaruprerel    alpha.19
%global aarutag       v%{aaruver}-%{aaruprerel}
%global aarudir       %{_libdir}/aaru

# Don't strip the self-contained .NET single-file launcher / generate
# debug subpackage / produce build-id links — none of those macros
# understand the embedded-runtime ELF layout used by single-file
# .NET publishes.
%global __strip /bin/true
%global _build_id_links none
%global debug_package %{nil}

# The single-file binary embeds shared objects whose names rpm's
# automatic dep scanner can't resolve (Avalonia/SkiaSharp/etc).
# Mirrors the upstream pkg/rpm/aaru.spec convention.
%global __requires_exclude ^lib.*\.so.*$
%global __provides_exclude ^lib.*\.so.*$

Name:           aaru
# Tilde-style pre-release (mirrors upstream pkg/rpm/aaru.spec):
#   6.0.0~alpha.19  <  6.0.0  <  6.0.1
# Future stable v6.0.0 will sort higher automatically — no clever
# leading-0 dance in Release needed. No Epoch field: COPR package
# history was wiped (copr-cli delete-package) before this build, so
# nothing previously published needs to be sort-overridden.
Version:        %{aaruver}~%{aaruprerel}
Release:        7%{?dist}
Summary:        Data preservation suite for optical, magnetic and solid-state media

License:        GPL-3.0-or-later AND LGPL-2.1-or-later AND MIT
URL:            https://github.com/aaru-dps/Aaru

# Two-source layout: the prebuilt linux_amd64 binary tarball gives us
# the self-contained `aaru` executable; the maintainer-signed source
# tarball provides icons, the aaruformat MIME definition, and the
# license/doc tree. Building from source ourselves needs NuGet access
# at build time, which COPR's enable_net=on does not actually grant
# for external hosts like api.nuget.org — so we repackage instead.
Source0:        %{url}/releases/download/%{aarutag}/aaru-%{aaruver}-%{aaruprerel}_linux_amd64.tar.xz
Source1:        %{url}/releases/download/%{aarutag}/aaru-src-%{aaruver}-%{aaruprerel}.tar.xz
# Curated manpage template (.TH/NAME/.../FILES/SEE ALSO) with a marker
# where the build-time generator splices in the live --help reference.
Source2:        aaru.1.in
Source3:        aaru-manpage.sh
# udev rule tagging USB and legacy floppy block devices with "uaccess", so
# systemd-logind puts an ACL on the node for whoever is logged in at the local
# desktop seat and `aaru media dump` can read floppies with no group and no
# root. Package-unique filename so it never collides with the same rule shipped
# by `aaru5` (stable) or `discimagecreator`, keeping all three co-installable.
Source4:        70-aaru-floppy.rules

ExclusiveArch:  x86_64
BuildRequires:  tar
BuildRequires:  xz
# Provides %%{_udevrulesdir}.
BuildRequires:  systemd-rpm-macros
# The aaru(1) manpage is generated at %build time by running the shipped
# binary's `--help` (see %build), so the binary's native runtime deps
# must be present in the build root as well, not just at install time.
BuildRequires:  gawk
BuildRequires:  libicu
# Native runtime libs the prebuilt .NET binary links to (same set as the
# runtime Requires below). openSUSE names them differently: krb5-libs ->
# krb5, openssl-libs -> libopenssl3, zlib -> libz1, and libunwind is
# 'libunwind' on Leap but 'libunwind8' on Tumbleweed, so require it by its
# stable soname. If any are missing the manpage generator self-heals to a
# curated page, but with them the build captures the full --help reference.
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

# Native runtime deps that the bundled .NET runtime dynamically links
# to. Mirrors the upstream pkg/rpm/aaru.spec dep set. `libicu` is portable
# (Fedora ships a package named libicu; every openSUSE ICU runtime package
# provides the virtual `libicu`) -- .NET fatally aborts without it. The
# rest are renamed on openSUSE (see BuildRequires above).
Requires:       libicu
%if 0%{?suse_version}
Requires:       krb5
Requires:       libopenssl3
Requires:       libz1
Requires:       libunwind.so.8()(64bit)
%else
Requires:       krb5-libs
Requires:       libunwind
Requires:       openssl-libs
Requires:       zlib
%endif

# Desktop integration — the three packages also provide Fedora file
# triggers that auto-refresh the MIME, desktop and icon-cache databases
# whenever something installs into their respective tree, so no
# explicit %post / %posttrans scriptlets are needed.
Requires:       shared-mime-info
Requires:       desktop-file-utils
Requires:       hicolor-icon-theme

# The same `aaru` binary serves CLI and Avalonia GUI (`aaru gui`).
# Avalonia.Desktop 11.x targets X11; this set covers both pure X11
# sessions and Wayland-via-XWayland sessions. Headless installs skip
# them with `--setopt=install_weak_deps=False` and the CLI still works.
Recommends:     libX11
Recommends:     libICE
Recommends:     libSM
Recommends:     libXext
Recommends:     libXi
Recommends:     libXrandr
Recommends:     libXcursor
Recommends:     mesa-libGL
Recommends:     fontconfig
Recommends:     freetype

%description
Aaru is a data preservation suite for optical, magnetic and solid-state
media. It dumps discs (CD/DVD/HD-DVD/BD/UMD/Floppy/MO) to byte-perfect
images, decodes filesystems, validates checksums and produces metadata
in the CICM format used by preservation projects.

The single `aaru` binary handles both modes:
  * `aaru` ............ command-line entry point (default)
  * `aaru gui` ........ launches the Avalonia desktop UI

cap_sys_rawio is set on the launcher binary so vendor SCSI passthrough
commands work without sudo. A udev rule tags floppy drives with `uaccess`,
so the user logged in at the local desktop seat can dump them without root
and without joining any group. Headless, SSH and cron sessions have no seat
and therefore no ACL; dump as root there.

%prep
# Two tarballs, manually extracted side-by-side. The binary tarball
# is rootless (drops aaru + docs in cwd); the source tarball is also
# rootless and gets extracted into a `src/` subdir so the two file
# sets don't collide.
%setup -q -c -T
tar -xJf %{SOURCE0}
mkdir -p src
tar -xJf %{SOURCE1} -C src

%build
# Source0 is the upstream prebuilt self-contained .NET single-file
# binary, repackaged unmodified — nothing to compile. We do generate the
# manpage here: the generator runs the extracted ./aaru binary's `--help`
# across its whole command tree and splices it into the curated aaru.1.in
# template, so the command/option reference always matches the binary
# that ships. Upstream provides no manpage and no native man generator;
# this keeps the reference from drifting without asking upstream for
# anything. Runs offline against bundled data (no network needed).
#
# The generator is self-healing: on a build root where the prebuilt
# binary can't start (e.g. a newer Fedora whose libicu/openssl SONAMEs
# the self-contained .NET bundle was not linked against — currently
# rawhide), it ships the curated page with a short note in place of the
# generated reference instead of failing the build. %{version} is passed
# as the .TH version fallback for that degraded case.
sh %{SOURCE3} ./aaru %{SOURCE2} %{version} > aaru.1

%install
install -D -m 0755 aaru %{buildroot}%{aarudir}/aaru

install -D -m 0644 LICENSE        %{buildroot}%{aarudir}/LICENSE
install -D -m 0644 LICENSE.MIT    %{buildroot}%{aarudir}/LICENSE.MIT
install -D -m 0644 LICENSE.LGPL   %{buildroot}%{aarudir}/LICENSE.LGPL
install -D -m 0644 README.md      %{buildroot}%{aarudir}/README.md
install -D -m 0644 Changelog.md   %{buildroot}%{aarudir}/Changelog.md
install -D -m 0644 CONTRIBUTING.md %{buildroot}%{aarudir}/CONTRIBUTING.md

# MIME type (.aif / .aaruformat / .dicf / .dicformat / .aaruf)
install -D -m 0644 src/Aaru/aaruformat.xml \
    %{buildroot}%{_datadir}/mime/packages/aaruformat.xml

# Desktop entry (we use the one from the source tarball — same content
# as the one in the binary tarball, but kept consistent with icons)
install -D -m 0644 src/Aaru/aaru.desktop \
    %{buildroot}%{_datadir}/applications/aaru.desktop

# Icons — five hicolor sizes shipped upstream
install -D -m 0644 src/icons/32x32/aaru.png    %{buildroot}%{_datadir}/icons/hicolor/32x32/apps/aaru.png
install -D -m 0644 src/icons/64x64/aaru.png    %{buildroot}%{_datadir}/icons/hicolor/64x64/apps/aaru.png
install -D -m 0644 src/icons/128x128/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/aaru.png
install -D -m 0644 src/icons/256x256/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/aaru.png
install -D -m 0644 src/icons/512x512/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/aaru.png

# Manpage (generated from the binary at %build time — see above)
install -D -m 0644 aaru.1 %{buildroot}%{_mandir}/man1/aaru.1

# udev rule for USB-floppy access (see Source4). See the %%post scriptlet: the
# file trigger shipped by systemd-udev only RELOADS the rule set, which does
# nothing for a drive that is already plugged in.
install -D -m 0644 %{SOURCE4} \
    %{buildroot}%{_udevrulesdir}/70-aaru-floppy.rules

# PATH entry — symlink to the real binary; the kernel follows symlinks
# for cap_sys_rawio inheritance on exec.
install -d %{buildroot}%{_bindir}
ln -sf %{aarudir}/aaru %{buildroot}%{_bindir}/aaru

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
%{aarudir}/README.md
%{aarudir}/Changelog.md
%{aarudir}/CONTRIBUTING.md
%license %{aarudir}/LICENSE
%license %{aarudir}/LICENSE.MIT
%license %{aarudir}/LICENSE.LGPL
%{_bindir}/aaru
%{_datadir}/mime/packages/aaruformat.xml
%{_datadir}/applications/aaru.desktop
%{_datadir}/icons/hicolor/32x32/apps/aaru.png
%{_datadir}/icons/hicolor/64x64/apps/aaru.png
%{_datadir}/icons/hicolor/128x128/apps/aaru.png
%{_datadir}/icons/hicolor/256x256/apps/aaru.png
%{_datadir}/icons/hicolor/512x512/apps/aaru.png
%{_mandir}/man1/aaru.1*
%{_udevrulesdir}/70-aaru-floppy.rules

%changelog
* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-7
- Apply the udev rule in %%post to drives that are ALREADY connected. The file
  trigger in systemd-udev only reloads the rule set, and only at the end of the
  transaction, which does nothing for a floppy that is plugged in at install
  time: measured, the node kept root:disk with no uaccess ACL and reads failed
  with EACCES until it was physically unplugged and replugged. %%post now
  reloads the rules and re-emits a change event for floppy block devices, so
  the drive is usable right after installing.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-6
- Own the private %{aarudir} directory in %%files. It was previously left
  unowned, so uninstalling the package orphaned /usr/lib64/aaru. Surfaced by
  openSUSE's stricter 50-check-filelist post-build check (which fails the build
  on unowned directories, where Fedora only warns).

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-5
- Fix 70-aaru-floppy.rules, which never fired. It matched
  ENV{ID_DRIVE_FLOPPY}, a property 80-udisks2.rules only sets at priority
  80 - after this rule runs at priority 70, and after 73-seat-late.rules
  has already applied the device ACL. Neither the GROUP="cdrom"/MODE=0660
  grant nor a uaccess tag could take effect at that point. The rule now
  matches ID_TYPE and ID_USB_TYPE (set by usb_id at priority 60) and tags
  the node "uaccess", so systemd-logind grants an ACL to the user at the
  local desktop seat.
- Floppy dumping now needs no group membership at all. Headless and SSH
  sessions have no seat and must dump as root: the node stays root:disk.
- Drop the false "add yourself to the cdrom group for floppy access"
  advice from the package description and aaru(1). The cdrom-group note
  for optical drives is a separate, still-correct mechanism and stays.

* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-4
- Ship a udev rule (70-aaru-floppy.rules) that grants the cdrom group
  read/write on USB floppy block devices (ENV{ID_DRIVE_FLOPPY}) and the
  legacy /dev/fd* controller nodes, so `aaru media dump` can read
  floppies without root. Package-unique filename so it does not collide
  with the equivalent rule in `aaru5` (stable) or `discimagecreator` and
  all three stay co-installable. Group cdrom is Fedora-native (no
  sysusers.d needed); users still add themselves with
  `usermod -aG cdrom <user>`.
- Portability for openSUSE (Leap 15.6 + Tumbleweed): the .NET runtime libs
  are renamed under a %if 0%{?suse_version} guard (krb5-libs->krb5,
  openssl-libs->libopenssl3, zlib->libz1, libunwind required by its stable
  soname since Leap ships `libunwind` and Tumbleweed `libunwind8`); `libicu`
  stays portable (openSUSE's ICU packages all provide the virtual `libicu`,
  and .NET fatally aborts without ICU). Fedora/EL names are unchanged. The
  prebuilt binary runs at %build on both openSUSE chroots, so the full
  generated manpage reference is captured there too; verified via mock.

* Tue Jun 30 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-3
- Make the manpage generator self-healing: when the prebuilt aaru binary
  cannot start in the build root (newer-Fedora runtime-library SONAME
  drift — observed on rawhide/f45, where libicu moved past what the
  self-contained .NET bundle links), ship the curated page with a short
  note in place of the auto-generated command reference instead of
  failing the whole build. Stable Fedora (43/44) still gets the full
  generated reference. %{version} is passed to the generator as the .TH
  version fallback for that degraded case.

* Mon Jun 29 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-2
- Generate the aaru(1) manpage from the shipped binary at build time
  instead of carrying a handwritten, hand-maintained command list. A new
  generator (aaru-manpage.sh) walks `aaru --help` across the full command
  tree and splices the verbatim reference into the curated aaru.1.in
  template, so the command/option reference can no longer drift from the
  installed version. Upstream ships no manpage and has no native man
  generator, so this is done entirely on the packaging side.
- Pin LC_ALL=C while harvesting help so the captured text is the English
  invariant resources and width-stable (80 columns) regardless of the
  build host locale; runs offline against bundled data.
- Add BuildRequires for the .NET native runtime libraries (libicu,
  krb5-libs, libunwind, openssl-libs, zlib) and gawk so the binary can
  run during %build.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-1
- Wipe COPR package history (copr-cli delete-package aaru) and
  rebuild fresh under the tilde-style convention without an Epoch
  field. The earlier Epoch=1 bump documented below was an artifact
  of the format migration from 0.alpha.NN.M-style Release; clearing
  the COPR side first lets us go back to implicit Epoch=0.
- Same upstream payload and install layout as the previous .2 build,
  only the NEVRA presentation changes.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 1:6.0.0~alpha.19-1
- Migrate to upstream-style tilde versioning (Version: 6.0.0~alpha.19,
  Release: 1). Matches the upstream pkg/rpm/aaru.spec convention and
  removes the leading-0.Release hack now that ~ does the pre-release
  sort cleanly. Future bumps will just edit %{aaruprerel}.
- Bump Epoch to 1 (was implicit 0): the new Version sorts LOWER than
  the previous Release form (6.0.0~alpha.19 < 6.0.0), so without Epoch
  the format switch would look like a downgrade to dnf. Epoch=1 is
  permanent from here on out.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 6.0.0-0.alpha.19.2
- Move install layout from /opt/Aaru to %{_libdir}/aaru — Fedora
  packaging guidelines disallow /opt for hosted-COPR packages
- Drop %post / %postun / %posttrans GTK / MIME / desktop-database
  refresh scriptlets; Fedora 26+ ships file triggers in
  hicolor-icon-theme / desktop-file-utils / shared-mime-info that
  refresh those caches automatically when files land in their tree

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 6.0.0-0.alpha.19.1
- Initial COPR build of Aaru v6.0.0-alpha.19
- Repackage of the upstream prebuilt linux_amd64 self-contained .NET
  single-file binary (api.nuget.org is unreachable from COPR's build
  chroot even with enable_net=on, so source-build isn't viable)
- Source tarball is consumed for icons, aaruformat MIME definition,
  and the desktop entry; binary tarball provides the executable and
  the LICENSE/README/Changelog
- Handwritten aaru(1) manpage (upstream provides none)
- X11 library stack in Recommends so headless installs stay lean
