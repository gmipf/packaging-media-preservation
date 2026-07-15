# Cargo's release profile already sets strip = true, so an auto-generated
# debuginfo/debugsource pair would be empty and the build would fail on it.
%global debug_package %{nil}

# The redumper build this GUI is tested against. Upstream pins it in its own
# CI (REDUMPER_VERSION: b729 in .github/workflows/build.yml) and bundles the
# binary in every release archive, with the README stating that changing it
# "is not recommended as it may not be supported by the GUI". A distribution
# cannot ship that bundled copy -- it would be a second /usr/bin/redumper --
# so the pinned build lives in its own package and we link it in below.
%global rdpin   729

%global guidir  %{_libdir}/%{name}

Name:           redumper-gui
Version:        1.0.1
Release:        0
Summary:        Desktop frontend for the redumper optical-disc dumper

# Upstream ships the plain GPL-3.0 text with no per-file headers and no
# license field in Cargo.toml, so there is nothing that says "or later".
# Packaged as the narrower GPL-3.0-only; asking upstream to declare the
# license in Cargo.toml is part of the packaging PR.
License:        GPL-3.0-only
URL:            https://github.com/Deterous/Redumper-GUI

# Source0 is a REPACKAGED tarball, not the upstream release archive:
# upstream's release archive ships a prebuilt binary (glibc 2.39, so it is
# unusable on EL8/EL9 and jammy), and Rust needs its dependency crates
# present at build time while the OBS build root, the COPR chroot and the
# and OBS build roots have no network. scripts/rust-vendor-tarball.sh
# therefore takes the upstream git tag, pins a Cargo.lock, vendors the crates
# filtered to x86_64-linux (cargo-vendor-filterer, which drops the windows-*
# trees: 546 MB -> 178 MB) and commits the result to an orphan `vendored` branch
# of the redumper-gui fork (gmipf/Redumper-GUI). Both lanes -- COPR and OBS --
# fetch that one file via raw.githubusercontent, so they build from
# byte-identical sources.
#
# Fetched by the _service (download_files) and committed as a package source,
# because the OBS build root is hermetic.
Source0:        https://raw.githubusercontent.com/gmipf/Redumper-GUI/vendored/%{name}-%{version}-vendored.tar.xz
Source1:        redumper-gui.desktop
Source2:        redumper-gui.1

# Upstream puts the default dump folder next to the executable, which is right
# for the portable build it ships and wrong for every packaged one: here the
# executable sits in %%{guidir}, owned by root, and the user cannot create the
# folder there. Measured on a clean install (mkdir: Permission denied), and
# dump.rs throws the error away, so the dump does not stop with a plain
# "permission denied" -- it runs on and fails later for a reason that never
# names the cause. The patch falls back to a Dumps folder in the user's HOME
# when the executable's directory is not writable -- upstream's own macOS branch
# already does exactly this (the .app bundle is the same predicament), and it is
# left alone there, keeping the download folder its users expect. Home is the
# Linux convention for a tool like this, and it is what our mpf package already
# does (DefaultOutputPath = $HOME/ISO): a browser empties Downloads, and nobody
# looks for disc images in it. Byte-identical to the copy in the Fedora and
# Debian lanes, and offered upstream.
Patch0:         0001-default-dump-folder-must-be-writable.patch

ExclusiveArch:  x86_64

# The real MSRV is 1.92, NOT the 1.85 that `edition = "2024"` alone implies:
# eframe/egui 0.35 pull it up. Measured, not inferred -- and upstream declares no
# `rust-version` in Cargo.toml, so nothing states this except the build breaking
# (asked for the declaration in Deterous/Redumper-GUI#2). Both openSUSE targets
# clear it with room to spare: Leap 16.0 and Tumbleweed both carry rustc 1.96.
BuildRequires:  rust >= 1.92
BuildRequires:  cargo
# zstd-sys compiles the bundled C and x86-64 assembly sources of libzstd.
BuildRequires:  gcc
BuildRequires:  desktop-file-utils
# Renders the hicolor icon sizes from upstream's single 512x512 PNG (see
# %%install). ImageMagick 7 on both openSUSE targets, so `magick` is the CLI.
BuildRequires:  ImageMagick
# NOT redundant with the Requires below. openSUSE's 50-check-filelist post-build
# check FAILS the build on any directory no installed package owns, where Fedora
# merely warns -- so the hicolor directory tree has to exist in the BUILD ROOT,
# not just on the user's machine. This is the exact bug the openSUSE lane already
# surfaced in aaru and mpf, which Fedora had silently tolerated (see
# opensuse/README.md).
BuildRequires:  hicolor-icon-theme

# Both of these are here to make the two symlinks in %%install RESOLVE at build
# time. openSUSE's brp-25-symlink (from brp-check-suse) FAILS the build on a
# symlink whose target exists "neither in build root nor in installed system" --
# Fedora ships the identical dangling symlinks with no complaint. Measured: the
# first OBS build died on exactly this, for both links.
#
# redumper729 is a hard runtime Requires anyway (below), so this changes nothing
# about the shipped package. mpf-check is deliberately only a weak Recommends at
# runtime -- the GUI tests whether MPF.Check sits next to it and skips the step if
# it does not -- but the LINK still has to resolve while rpm inspects the build
# root, so the package has to be there for the build and only for the build. That
# asymmetry is intentional, not an oversight: on a user's machine without
# mpf-check the link dangles, which is precisely the state the GUI checks for.
BuildRequires:  redumper%{rdpin}
BuildRequires:  mpf-check

# The pinned dumper -- a hard dependency: without it the GUI has nothing to
# drive. Not the rolling `redumper` package, deliberately (see rdpin above).
Requires:       redumper%{rdpin}

# Post-processing is optional: the GUI checks whether MPF.Check sits next to
# its own executable and silently skips the step if it does not. The symlink
# we install for it dangles until mpf-check is there, which is exactly what
# that check tests for.
Recommends:     mpf-check

# GUI libraries are dlopen'd at run time (winit for X11/Wayland, glutin for
# GL/EGL), so they never appear in the binary's DT_NEEDED and rpm's automatic
# dependency extraction cannot see a single one of them -- the same trap as
# with mpf-gui. Declared by SONAME, never by package name: the Fedora spellings
# (mesa-libGL, libX11) do not exist on openSUSE, and a Requires that resolves to
# nothing makes the package uninstallable. Each of these was checked against the
# Leap 16.0 and Tumbleweed repodata and is a real 64-bit Provides -- from
# libglvnd (libGL/libEGL), libX11-6, libX11-xcb1, libXi6, libXcursor1,
# libXrender1, libxkbcommon0, libxkbcommon-x11-0, libwayland-client0,
# libwayland-egl1 and libdbus-1-3.
Requires:       libGL.so.1()(64bit)
Requires:       libEGL.so.1()(64bit)
Requires:       libX11.so.6()(64bit)
Requires:       libX11-xcb.so.1()(64bit)
Requires:       libXi.so.6()(64bit)
Requires:       libXcursor.so.1()(64bit)
Requires:       libXrender.so.1()(64bit)
Requires:       libxkbcommon.so.0()(64bit)
Requires:       libxkbcommon-x11.so.0()(64bit)
Requires:       libwayland-client.so.0()(64bit)
Requires:       libwayland-egl.so.1()(64bit)
Requires:       libdbus-1.so.3()(64bit)

Requires:       hicolor-icon-theme

%description
Redumper GUI is a graphical frontend for redumper, the low-level disc
dumper used by the Redump preservation project. It lists the optical
drives on the system, runs the dump, streams redumper's log into the
window, and afterwards compresses the logs into a submission-ready ZIP.

Unlike the upstream release archive, this package does not bundle its own
copy of redumper. It depends on redumper%{rdpin} -- a package carrying
exactly the build upstream tests the GUI against -- and executes that one.
The rolling `redumper` package can be installed next to it for command-line
use; the two do not conflict.

If mpf-check is installed, the GUI runs MPF.Check on the finished dump to
generate Redump submission info. Without it the dump still completes and
that step is skipped.

Both X11 and Wayland are supported natively.

Built from source against the distribution's Rust toolchain -- the upstream
release binary is compiled on Ubuntu 24.04 and requires glibc 2.39.

%prep
# -p1 is not the default: without it %%autosetup calls patch with no -p at all,
# which leaves the a/ b/ prefixes in place and fails with "No file to patch".
%autosetup -n %{name}-%{version} -p1

%build
# Crates come from the vendored tree in the tarball (.cargo/config.toml
# redirects crates-io at it), so the build must never reach for the network:
# the OBS build root is hermetic, and so is COPR's chroot -- neither has a
# builders have any network either.
export CARGO_NET_OFFLINE=true
cargo build --release --offline

%install
# The real binary lives in a private directory, and /usr/bin gets a symlink
# rather than a wrapper script. That is not cosmetic: the GUI locates its
# helpers with std::env::current_exe(), which on Linux reads /proc/self/exe
# and therefore RESOLVES the symlink. Invoked as /usr/bin/redumper-gui, the
# process still sees itself in %{guidir} and looks for its siblings there --
# which is where we put them.
install -D -m 0755 target/release/%{name} %{buildroot}%{guidir}/%{name}

# The two siblings the GUI looks for, by the exact filenames it expects.
# It runs `dirname(current_exe())/redumper` and `dirname(current_exe())/
# MPF.Check` -- no PATH fallback (a packaging PR upstream proposes one).
ln -s %{_bindir}/redumper%{rdpin}      %{buildroot}%{guidir}/redumper
ln -s %{_libdir}/mpf-check/MPF.Check   %{buildroot}%{guidir}/MPF.Check

install -d %{buildroot}%{_bindir}
ln -s ../%{_lib}/%{name}/%{name} %{buildroot}%{_bindir}/%{name}

# The manpage is installed VERBATIM, with the version marker its author wrote
# into it -- never stamped with %%{version}. The content is hand-written and does
# not move when the package does; stamping the shipped release into the header
# would make an aging page keep claiming currency. A fixed marker lets a reader
# see that the page predates their binary. (Generated pages are the opposite
# case: there, content and version move together, so stamping is honest --
# that is why aaru's generated page does it and this one does not.)
install -D -m 0644 %{SOURCE2} %{buildroot}%{_mandir}/man1/%{name}.1

desktop-file-install --dir=%{buildroot}%{_datadir}/applications %{SOURCE1}

# Upstream ships exactly ONE raster icon: assets/icon/icon.png at 512x512 (the
# .ico next to it is Windows-only and carries just 16px and 24px). Shipping only
# the 512 and letting the desktop downscale it is what we did first, and it is
# wrong for THIS icon: it is a finely detailed disc sector -- thin grid lines and
# hairline spokes -- and a naive on-the-fly downscale to a 24px panel slot turns
# that into mush. Render the standard hicolor sizes here instead, once, with a
# proper Lanczos filter.
#
# Generated from the upstream asset rather than checked into this repo as
# pre-rendered PNGs: nothing is duplicated, and the packaged icon therefore
# cannot drift from the one upstream actually ships.
#
# Both openSUSE targets carry ImageMagick 7, whose CLI is `magick` (`convert` is
# deprecated there). The probe is kept so this spec stays interchangeable with
# the Fedora one, which must also serve EL8's ImageMagick 6.
if command -v magick >/dev/null 2>&1; then IM=magick; else IM=convert; fi
for px in 16 22 24 32 48 64 128 256; do
    install -d %{buildroot}%{_datadir}/icons/hicolor/${px}x${px}/apps
    $IM assets/icon/icon.png -filter Lanczos -resize ${px}x${px} \
        %{buildroot}%{_datadir}/icons/hicolor/${px}x${px}/apps/%{name}.png
done
# The 512 is the upstream file itself, installed byte-for-byte (no resample).
install -D -m 0644 assets/icon/icon.png \
    %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/%{name}.png

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop

# Every size the desktop will look for must actually be there -- a hicolor dir
# that exists but is empty is worse than none. Fail the build, don't ship a
# launcher with a missing icon.
for px in 16 22 24 32 48 64 128 256 512; do
    test -s %{buildroot}%{_datadir}/icons/hicolor/${px}x${px}/apps/%{name}.png \
        || { echo "icon ${px}x${px} missing or empty"; exit 1; }
done

# DO NOT grant cap_sys_rawio here -- not through %%caps, and not through a
# permissions.d profile either. A dumping frontend looks like it ought to have
# raw drive access, but it must not:
#
#   * Unnecessary: the GUI never talks to the drive. It runs redumper, and
#     redumper%%{rdpin} carries the capability on its own binary -- the kernel
#     grants file capabilities from the EXECUTED FILE, so the dumper is fully
#     privileged no matter who starts it.
#
#   * Harmful: executing a file with capabilities makes the process
#     non-dumpable (AT_SECURE), which flips /proc/<pid>/root to root:root.
#     xdg-desktop-portal reads exactly that path to identify the calling app,
#     fails, and refuses with "Portal operation not allowed" -- so every file
#     dialog blows up. Not theory: that is precisely what shipping
#     cap_sys_rawio on MPF.Avalonia did to mpf-gui. Measured on one and the same
#     binary: capability set -> portal denies; capability removed -> accepts.
#
# This is also why this package needs no rpmlintrc: with no permissions.d
# profile there is no permissions-file-unauthorized finding to demote.
%files
%license LICENSE
%doc README.md
%dir %{guidir}
%{guidir}/%{name}
%{guidir}/redumper
# Dangles until mpf-check is installed -- deliberate, see Recommends above.
%{guidir}/MPF.Check
%{_bindir}/%{name}
%{_mandir}/man1/%{name}.1*
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.png

%changelog
* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 1.0.1-0
- Initial openSUSE (OBS) packaging of Redumper GUI v1.0.1 (Rust / egui).
- Built from source against the distribution's Rust toolchain, from the same
  vendored crate tarball the Fedora and Ubuntu lanes consume, so all three build
  byte-identical sources. Leap 16.0 and Tumbleweed both carry rustc 1.96, well
  clear of the real 1.92 floor that eframe/egui 0.35 imposes.
- Does not bundle redumper. Upstream's archives ship a pinned b729 next to the
  GUI executable and the GUI runs its sibling by that name; a package cannot add
  a second /usr/bin/redumper, so the pinned build is packaged separately as
  redumper729 and symlinked into the GUI's private directory. Same for MPF.Check,
  whose symlink dangles harmlessly until mpf-check is installed -- the GUI tests
  for exactly that.
- Carries the same default-dump-folder patch as the other two lanes: upstream
  puts the dump folder next to the executable, which in a packaged install is a
  root-owned system directory the user cannot write to.
- All GUI libraries are dlopen'd (winit, glutin) and thus invisible to rpm's
  automatic dependency extraction; declared by soname by hand, and every one of
  them verified to be a real Provides on both openSUSE targets -- a hard Requires
  that resolves to nothing would make the package uninstallable while the build
  stayed green.
- No capability on this binary, by design: the dumper it drives carries it, and a
  file capability would make the process non-dumpable and kill every file dialog
  through xdg-desktop-portal.
