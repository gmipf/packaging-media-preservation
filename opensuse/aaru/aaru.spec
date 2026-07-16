%global aaruver       6.0.0
%global aaruprerel    beta.1
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
Version:        %{aaruver}~%{aaruprerel}
Release:        0
Summary:        Data preservation suite for optical, magnetic and solid-state media

License:        GPL-3.0-or-later AND LGPL-2.1-or-later AND MIT
URL:            https://github.com/aaru-dps/Aaru

# Two-source layout: the prebuilt linux_amd64 binary tarball gives us the
# self-contained `aaru` executable; the maintainer-signed source tarball
# provides icons, the aaruformat MIME definition, and the license/doc tree.
# OBS build roots are hermetic (no network), so both are fetched by the
# _service (download_files) and committed as package sources.
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
# Renders the small hicolor sizes upstream does not ship (see %%install).
BuildRequires:  ImageMagick
# The aaru(1) manpage is generated at %build time by running the shipped
# binary's `--help` (see %build), so the binary's native runtime deps
# must be present in the build root as well, not just at install time.
BuildRequires:  gawk
BuildRequires:  libicu
# openSUSE grants file capabilities through the permissions framework
# (chkstat), not a bare %%caps entry (see %%install / %%post).
BuildRequires:  permissions
# hicolor-icon-theme owns /usr/share/icons/hicolor/**; it is a runtime Requires
# below, but it must ALSO be in the build root: openSUSE's 50-check-filelist
# post-build check fails the build on directories that no *installed* package
# owns, and it only sees BuildRequires. (Fedora does not run this check.)
BuildRequires:  hicolor-icon-theme
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

# Native runtime deps that the bundled .NET runtime dynamically links to.
# `libicu` is portable (openSUSE's ICU packages all provide the virtual
# `libicu`) -- .NET fatally aborts without it. The rest are renamed on
# openSUSE (see BuildRequires above).
Requires:       libicu
Requires:       permissions
Requires(post): permissions
Requires(verify): permissions
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

# Desktop integration — openSUSE also ships file triggers that auto-refresh
# the MIME, desktop and icon-cache databases when something installs into
# their tree, so no explicit %post scriptlets are needed for those.
Requires:       shared-mime-info
Requires:       desktop-file-utils
Requires:       hicolor-icon-theme

# The same `aaru` binary serves CLI and Avalonia GUI (`aaru gui`).
# Avalonia.Desktop 11.x targets X11; this set covers both pure X11
# sessions and Wayland-via-XWayland sessions. Headless installs skip
# them with `--no-recommends` and the CLI still works.
#
# Expressed as SONAMEs rather than package names. These are weak deps and
# never enter the build root, so a wrong name breaks nothing loudly — it just
# silently resolves to nothing, which is what the fedora spellings (libX11,
# mesa-libGL, ...) did here: they do not exist on openSUSE, so a GUI install
# pulled none of them. Sonames are distro-agnostic and survive renames.
# Verified against the Leap 16.0 and Tumbleweed repodata: each of these is a
# real 64-bit Provides, coming from libX11-6, libICE6, libSM6, libXext6,
# libXi6, libXrandr2, libXcursor1, libglvnd, libfontconfig1 and libfreetype6.
# Note libGL.so.1 is provided by libglvnd, NOT by Mesa-libGL1.
Recommends:     libX11.so.6()(64bit)
Recommends:     libICE.so.6()(64bit)
Recommends:     libSM.so.6()(64bit)
Recommends:     libXext.so.6()(64bit)
Recommends:     libXi.so.6()(64bit)
Recommends:     libXrandr.so.2()(64bit)
Recommends:     libXcursor.so.1()(64bit)
Recommends:     libGL.so.1()(64bit)
Recommends:     libfontconfig.so.1()(64bit)
Recommends:     libfreetype.so.6()(64bit)

%description
Aaru is a data preservation suite for optical, magnetic and solid-state
media. It dumps discs (CD/DVD/HD-DVD/BD/UMD/Floppy/MO) to byte-perfect
images, decodes filesystems, validates checksums and produces metadata
in the CICM format used by preservation projects.

The single `aaru` binary handles both modes:
  * `aaru` ............ command-line entry point (default)
  * `aaru gui` ........ launches the Avalonia desktop UI

cap_sys_rawio is set on the launcher binary (via the openSUSE permissions
framework) so vendor SCSI passthrough commands work without sudo. A udev
rule tags floppy drives with `uaccess`, so the user logged in at the local
desktop seat can dump them without root and without joining any group.
Headless, SSH and cron sessions have no seat and therefore no ACL; dump as
root there.

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
# Source0 is the upstream prebuilt self-contained .NET single-file binary,
# repackaged unmodified — nothing to compile. We do generate the manpage
# here: the generator runs the extracted ./aaru binary's `--help` across
# its whole command tree and splices it into the curated aaru.1.in
# template. Runs offline against bundled data (no network needed).
#
# The generator is self-healing: on a build root where the prebuilt binary
# can't start (runtime-library SONAME drift), it ships the curated page
# with a short note instead of failing the build. %{version} is the .TH
# version fallback for that degraded case. The prebuilt binary is known to
# run on both Leap and Tumbleweed build roots (verified via mock).
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

# --- Icons ---
#
# Upstream ships five sizes: 32, 64, 128, 256, 512. Those are installed
# BYTE-FOR-BYTE below -- they are upstream's own files and may be hand-tuned; we
# do not second-guess them by re-rendering what already exists.
#
# What upstream does NOT ship is 16, 22, 24 and 48 -- precisely the sizes a
# desktop reaches for most: panel, dock, menu and the file-manager list view.
# Missing them, the theme has to downscale the 32 (or, worse, the 512) on the fly
# into a 16px slot, every time it draws one. Render them once here instead, with
# a proper Lanczos filter, from src/icons/aaru.png: upstream's 862x862 master,
# the largest and least resampled source in the tarball (measured, not assumed --
# it is bigger than the 512 they ship).
if command -v magick >/dev/null 2>&1; then IM=magick; else IM=convert; fi
for sz in 16 22 24 48; do
    install -d %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps
    $IM src/icons/aaru.png -filter Lanczos -resize ${sz}x${sz} \
        %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/aaru.png
done

# Upstream's own sizes, untouched.
install -D -m 0644 src/icons/32x32/aaru.png    %{buildroot}%{_datadir}/icons/hicolor/32x32/apps/aaru.png
install -D -m 0644 src/icons/64x64/aaru.png    %{buildroot}%{_datadir}/icons/hicolor/64x64/apps/aaru.png
install -D -m 0644 src/icons/128x128/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/aaru.png
install -D -m 0644 src/icons/256x256/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/aaru.png
install -D -m 0644 src/icons/512x512/aaru.png  %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/aaru.png

# A hicolor directory that exists but holds no icon is worse than none: the
# launcher silently comes up blank. Fail the build instead of shipping that.
for sz in 16 22 24 32 48 64 128 256 512; do
    test -s %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/aaru.png \
        || { echo "icon ${sz}x${sz} missing or empty"; exit 1; }
done

# Manpage (generated from the binary at %build time — see above)
install -D -m 0644 aaru.1 %{buildroot}%{_mandir}/man1/aaru.1

# udev rule for USB-floppy access (see Source4). No scriptlet needed:
# the udev package ships a file trigger on %{_udevrulesdir} that reloads
# rules automatically when this file lands.
install -D -m 0644 %{SOURCE4} \
    %{buildroot}%{_udevrulesdir}/70-aaru-floppy.rules

# PATH entry — symlink to the real binary; the kernel follows symlinks
# for cap_sys_rawio inheritance on exec.
install -d %{buildroot}%{_bindir}
ln -sf %{aarudir}/aaru %{buildroot}%{_bindir}/aaru

# Permissions framework profile: grant cap_sys_rawio on the real binary for
# sudo-less SCSI passthrough. The capability lives on the continuation line
# beginning with " +capabilities".
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/aaru <<EOF
# aaru needs raw SCSI passthrough for vendor drive commands.
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
# %doc/%license MARK these as documentation instead of merely shipping them, so
# `rpm -qd` lists them and --excludedocs can drop them. On an ABSOLUTE path the
# marker only tags: the files stay in %{aarudir} beside the binary — upstream's
# own spec keeps them next to it too (in /opt/Aaru) — they are NOT relocated to
# %{_docdir}. Same intent as the Debian lane, where debhelper picks Changelog.md
# up as the package's upstream changelog.
%doc %{aarudir}/README.md
%doc %{aarudir}/Changelog.md
%doc %{aarudir}/CONTRIBUTING.md
%license %{aarudir}/LICENSE
%license %{aarudir}/LICENSE.MIT
%license %{aarudir}/LICENSE.LGPL
%{_bindir}/aaru
%{_datadir}/mime/packages/aaruformat.xml
%{_datadir}/applications/aaru.desktop
%{_datadir}/icons/hicolor/*/apps/aaru.png
%{_mandir}/man1/aaru.1*
%{_udevrulesdir}/70-aaru-floppy.rules
%{_datadir}/permissions/permissions.d/aaru

%changelog
* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 6.0.0~beta.1-0
- Mark README.md, Changelog.md and CONTRIBUTING.md as %%doc. They were already
  installed, but unmarked, so rpm did not know they were documentation: `rpm -qd
  aaru` came back empty and --excludedocs kept them. The files do not move --
  %%doc on an absolute path only tags. Inherited from upstream's own spec, which
  ships all three unmarked in /opt/Aaru; the Debian lane already had it right,
  where debhelper installs Changelog.md as the package's upstream changelog.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 6.0.0~beta.1-0
- Automated sync to upstream Aaru v6.0.0-beta.1.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-0
- Ship the launcher icon in the four small hicolor sizes upstream does not
  provide (16, 22, 24, 48), rendered at build time from upstream's 862x862
  master with a Lanczos filter. Those four are the sizes a desktop actually
  draws most -- panel, dock, menu, file-manager list -- and without them the
  theme had to downscale the 32 (or the 512) on the fly for every one of them.
  Upstream's own five sizes (32-512) are still installed byte-for-byte.
- %%install now fails the build if any of the nine sizes is missing or empty.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-0
- Apply the udev rule in %%post to drives that are ALREADY connected. The file
  trigger shipped by udev only reloads the rule set, and only at the end of the
  transaction, which does nothing for a floppy that is plugged in at install
  time: measured, the node kept root:disk with no uaccess ACL and reads failed
  with EACCES until it was physically unplugged and replugged. %%post now
  reloads the rules and re-emits a change event for floppy block devices, so
  the drive is usable right after installing.

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-0
- Fix 70-aaru-floppy.rules before it is ever published. It matched
  ENV{ID_DRIVE_FLOPPY}, a property 80-udisks2.rules only sets at priority
  80 - after this rule runs at priority 70, and after 73-seat-late.rules
  has already applied the device ACL, so it never fired. It now matches
  ID_TYPE and ID_USB_TYPE (set by usb_id at priority 60) and tags the node
  "uaccess", letting systemd-logind grant an ACL to the local-seat user.
- Floppy dumping needs no group membership. This also sidesteps openSUSE
  Leap 16 having no floppy group at all. Headless sessions have no seat
  and must dump as root: the node stays root:disk.
- Drop the false "add yourself to the cdrom group for floppy access"
  advice from the package description and aaru(1).

* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 6.0.0~alpha.19-0
- Initial openSUSE (OBS) packaging of Aaru v6.0.0-alpha.19 as `aaru`.
- Repackage of the upstream prebuilt linux_amd64 self-contained .NET
  single-file binary; the source tarball supplies icons, the aaruformat
  MIME definition and the desktop entry. Both fetched via the _service
  (download_files) and committed, since OBS build roots have no network.
- .NET runtime Requires mapped to openSUSE names under %%if 0%%{?suse_version}
  (krb5, libopenssl3, libz1, libunwind.so.8; libicu portable). aaru(1)
  generated at build time from the binary's --help (self-healing).
- cap_sys_rawio granted through the openSUSE permissions framework
  (permissions.d profile + %%set_permissions / %%verify_permissions), the
  distro-native equivalent of the Fedora spec's %%caps entry.
