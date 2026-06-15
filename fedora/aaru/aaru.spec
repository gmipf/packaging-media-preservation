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
# Epoch bump (0 -> 1) is needed once-only on this rewrite: previous
# build was aaru-6.0.0-0.alpha.19.2 and the new tilde-style Version
# (6.0.0~alpha.19) sorts LOWER than the bare 6.0.0 that prior Release
# claimed (`~` outranks empty string). Without Epoch, dnf would see
# the migration as a downgrade. Epoch stays at 1 from here on — even
# after a future stable 6.0.0 ships, since Epoch is forever.
Epoch:          1
# Tilde-style pre-release (mirrors upstream pkg/rpm/aaru.spec):
#   6.0.0~alpha.19  <  6.0.0  <  6.0.1
# Future stable v6.0.0 will sort higher automatically — no clever
# leading-0 dance in Release needed.
Version:        %{aaruver}~%{aaruprerel}
Release:        1%{?dist}
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
Source2:        aaru.1

ExclusiveArch:  x86_64
BuildRequires:  tar
BuildRequires:  xz

# Native runtime deps that the bundled .NET runtime dynamically links
# to. Mirrors the upstream pkg/rpm/aaru.spec dep set.
Requires:       libicu
Requires:       krb5-libs
Requires:       libunwind
Requires:       openssl-libs
Requires:       zlib

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
commands work without sudo.

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
# Nothing to build — Source0 is the upstream prebuilt self-contained
# .NET single-file binary, repackaged unmodified.

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

# Manpage (handwritten — upstream provides none)
install -D -m 0644 %{SOURCE2} %{buildroot}%{_mandir}/man1/aaru.1

# PATH entry — symlink to the real binary; the kernel follows symlinks
# for cap_sys_rawio inheritance on exec.
install -d %{buildroot}%{_bindir}
ln -sf %{aarudir}/aaru %{buildroot}%{_bindir}/aaru

%files
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

%changelog
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
