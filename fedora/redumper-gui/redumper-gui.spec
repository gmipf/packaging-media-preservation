# Cargo's release profile already sets strip = true, so an auto-generated
# debuginfo/debugsource pair would be empty and the build would fail on it.
%global debug_package %{nil}
# No sibling ships this ELF, so this package cannot hit the build-id collision
# that made redumper and redumper732 un-co-installable on EL (see redumper.spec).
# But with debug_package off the links point at debuginfo that does not exist, so
# they are dead weight regardless -- and uniform with every other spec here.
%global _build_id_links none

# The redumper build this GUI is tested against. Upstream pins it in its own CI
# (REDUMPER_VERSION in .github/workflows/build.yml -- the number is deliberately
# NOT repeated here: a build number in a comment is a second place to forget it,
# and this one already went stale once) and bundles the
# binary in every release archive, with the README stating that changing it
# "is not recommended as it may not be supported by the GUI". A distribution
# cannot ship that bundled copy -- it would be a second /usr/bin/redumper --
# so the pinned build lives in its own package and we link it in below.

%global guidir  %{_libdir}/%{name}

Name:           redumper-gui
Version:        1.0.4
Release:        1%{?dist}
Summary:        Desktop frontend for the redumper optical-disc dumper

# Upstream ships the plain GPL-3.0 text with no per-file headers, so there is
# nothing that says "or later" -- packaged as the narrower GPL-3.0-only. As of
# 1.0.2 upstream declares `license = "GPL-3.0-only"` in Cargo.toml as well (the
# packaging PR asked for it), so this now agrees with the crate's own metadata
# instead of resting on our reading of a bare LICENSE file.
License:        GPL-3.0-only
URL:            https://github.com/Deterous/Redumper-GUI

# Source0 is a REPACKAGED tarball, not the upstream release archive: upstream's
# release archive ships a prebuilt binary (glibc 2.39, unusable on EL8/EL9 and
# jammy), and Rust needs every dependency crate present at build time while no
# build root -- COPR's mock chroot or OBS's -- has network.
# scripts/rust-vendor-tarball.sh therefore takes the upstream git tag, keeps
# upstream's Cargo.lock (committed as of 1.0.2), vendors the crates filtered to
# x86_64-linux (cargo-vendor-filterer drops the windows-* trees: 546 MB -> 178 MB)
# and uploads the result as a RELEASE ASSET on the packaging repo. Both lanes --
# COPR and OBS -- fetch that one file, so they build from byte-identical sources.
#
# It used to live on an orphan `vendored` branch of our fork of the tool, served
# by raw.githubusercontent. That cost a cross-repo write credential, grew the
# branch by ~15 MB per release forever, and served branch URLs through a
# ~5 minute CDN cache -- so re-publishing the SAME version with different bytes
# handed the build farms the old blob under the new name, with no error anywhere.
# A release asset has an immutable per-tag URL, no documented bandwidth limit,
# and the built-in GITHUB_TOKEN can write it in its own repo.
Source0:        https://github.com/gmipf/packaging-media-preservation/releases/download/%{name}-vendored-%{version}/%{name}-%{version}-vendored.tar.xz
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
# looks for disc images in it.
#
# DROPPED in 1.0.2 -- upstream now does this itself. It closed our PR #3
# unmerged and then implemented the same fix its own way: effective_output_dir()
# in src/app/logic.rs falls back to download_dir/home_dir + "Dumps" and does not
# touch current_exe at all. Verified by reading the 1.0.2 source, not inferred
# from the PR being closed -- the two say different things, and only the source
# is binding. The patch is therefore gone rather than rebased; do not re-add it.
# (current_exe still appears in dump.rs and postprocess.rs, but for finding the
# redumper and MPF.Check binaries, which is PR #4's subject, not this one.)

ExclusiveArch:  x86_64 aarch64

# The real MSRV is 1.92, NOT the 1.85 that `edition = "2024"` alone implies:
# eframe/egui 0.35 pull it up. Measured, not inferred -- and as of 1.0.2 upstream
# STATES it, `rust-version = "1.92"` in Cargo.toml, which Deterous/Redumper-GUI#2
# asked for. Before that nothing declared it except the build breaking, and our
# vendoring script had to inject the floor itself to keep cargo's resolver honest.
#
# 1.92 is what rules the target list, and it is tight on EL. The table below is a
# READING COPY for whoever has only the SRPM; scripts/rust-targets.tsv in the
# packaging repo is authoritative and carries the `measured` date per row. When
# the two disagree, the TSV is right and this comment is stale -- say so out loud,
# because on 2026-07-20 ubuntu/README.md still claimed "Debian 13 ships 1.85, only
# 26.04 clears the floor" months after the re-measurement had landed in the TSV.
# Nothing marked the prose as subordinate, so the superseded number outlived the
# note that superseded it.
#
#   Fedora 43+                      1.96   ok
#   EL 8 / 9 / 10                   1.92   ok -- EXACTLY the floor, zero headroom
#   Leap 16.0 / Tumbleweed          1.96   ok
#   Debian 13 (trixie)              1.85   -> needs rustc 1.94 from trixie-backports
#   Debian 12                       1.63   OUT (backports carries no rustc at all)
#   Ubuntu 22.04 / 24.04            1.75   OUT (rustc-1.91 is the newest available)
#   Ubuntu 26.04                    1.93   ok
#
# The version below is NOT a reading copy -- it is load-bearing, and rpm cannot
# read the TSV. status.sh therefore compares it against the floor derived from the
# `ship` rows and fails if they drift apart.
BuildRequires:  rust >= 1.92
BuildRequires:  cargo
# zstd-sys compiles the bundled C and x86-64 assembly sources of libzstd.
BuildRequires:  gcc
BuildRequires:  desktop-file-utils
# Renders the hicolor icon sizes from upstream's single 512x512 PNG (see
# %%install). Resolvable on every chroot we build -- verified on fedora-43,
# epel-8 and epel-10; on EL it comes from EPEL, which the buildroot has.
BuildRequires:  ImageMagick

# The pinned dumper -- a hard dependency: without it the GUI has nothing to
# drive. Not the rolling `redumper` package, deliberately (see the header above).
Requires:       redumper-rgui

# Post-processing is optional: the GUI checks whether MPF.Check sits next to
# its own executable and silently skips the step if it does not. The symlink
# we install for it dangles until mpf-check is there, which is exactly what
# that check tests for.
Recommends:     mpf-check

# GUI libraries are dlopen'd at run time (winit for X11/Wayland, glutin for
# GL/EGL), so they never appear in the binary's DT_NEEDED and rpm's automatic
# dependency extraction cannot see a single one of them -- the same trap as
# with mpf-gui. Declared by soname, which resolves on Fedora, EL and openSUSE
# alike without per-distro package-name conditionals.
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
copy of redumper. It depends on redumper-rgui -- a package carrying
exactly the build upstream tests the GUI against -- and executes that one.
The rolling `redumper` package can be installed next to it for command-line
use; the two do not conflict.

If mpf-check is installed, the GUI runs MPF.Check on the finished dump to
generate Redump submission info. Without it the dump still completes and
that step is skipped.

Both X11 and Wayland are supported natively.

Built from source against the distribution's Rust toolchain -- the upstream
release binary is compiled on Ubuntu 24.04 and requires glibc 2.39, which
rules out EL8, EL9 and Ubuntu 22.04.

%prep
# -p1 is not the default: without it %%autosetup calls patch with no -p at all,
# which leaves the a/ b/ prefixes in place and fails with "No file to patch".
%autosetup -n %{name}-%{version} -p1

%build
# Crates come from the vendored tree in the tarball (.cargo/config.toml
# redirects crates-io at it), so the build must never reach for the network:
# no build root has any: not COPR's chroot, not OBS's.
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
ln -s %{_bindir}/redumper-rgui      %{buildroot}%{guidir}/redumper
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
# ImageMagick 7 renamed the CLI to `magick` and deprecated `convert`; EL8 still
# carries ImageMagick 6, which has only `convert`. Pick whichever exists in the
# buildroot rather than assuming a version.
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

# DO NOT add %%caps(cap_sys_rawio=ep) here. A dumping frontend looks like it
# ought to have raw drive access, but it must not:
#
#   * Unnecessary: the GUI never talks to the drive. It runs redumper, and
#     redumper-rgui carries the capability on its own binary -- the kernel
#     grants file capabilities from the EXECUTED FILE, so the dumper is fully
#     privileged no matter who starts it.
#
#   * Harmful: executing a file with capabilities makes the process
#     non-dumpable (AT_SECURE), which flips /proc/<pid>/root to root:root.
#     xdg-desktop-portal reads exactly that path to identify the calling app,
#     fails, and refuses with "Portal operation not allowed" -- so every file
#     dialog blows up. Not theory: that is precisely what shipping
#     cap_sys_rawio on MPF.Avalonia did to mpf-gui (fixed in
#     mpf-3.8.3~20260707133302.e1081655-2). Measured on one and the same
#     binary: capability set -> portal denies; capability removed -> accepts.
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
* Tue Jul 28 2026 gmipf <gmipf64@gmail.com> - 1.0.4-1
- Automated sync to upstream redumper-gui release v1.0.4. Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 1.0.3-1
- Automated sync to upstream redumper-gui release v1.0.3. Release reset to 1.

* Sun Jul 19 2026 gmipf <gmipf64@gmail.com> - 1.0.2-1
- Update to upstream 1.0.2. It carries the three things the packaging PR asked
  for and upstream granted: a committed Cargo.lock, rust-version = "1.92" and
  a license field in Cargo.toml. The vendoring script therefore keeps upstream's
  lockfile now instead of resolving one itself, so the dependency set is theirs.
- Source0 moves from an orphan branch of the tool's fork to a release asset on
  the packaging repo; see the comment above it for why.
- The bundled redumper this release is tested against moved b729 -> b733, so
  redumper-rgui advances in the same change.
- Drop 0001-default-dump-folder-must-be-writable.patch: upstream closed PR #3
  unmerged and then implemented the same fix its own way in 1.0.2, so the patch
  no longer applies and is no longer needed. Confirmed against the 1.0.2 source
  rather than assumed from the PR's state.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 1.0.1-7
- Add aarch64 (arm64) support: ExclusiveArch is now x86_64 aarch64. This package
  is BUILT FROM SOURCE (Rust, from the vendored crate tarball), so there is no
  arch-specific archive to bundle -- cargo compiles natively on the aarch64
  builders. arm64 ships UNTESTED -- no hardware drive-access proof exists for it;
  nothing in the packaging is architecture-specific, but this is deliberately not
  claimed as proven.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 1.0.1-6
- Set %%global _build_id_links none, for uniformity with every other spec here.
  No sibling ships this ELF, so this package cannot hit the build-id collision
  that made redumper and redumper732 un-co-installable on EL -- but with
  debug_package off the links are dead weight regardless (they point at
  debuginfo that does not exist). Measured on CentOS Stream 10, 2026-07-16.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 1.0.1-4
- Put the fallback dump folder in the user's HOME (~/Dumps), not in ~/Downloads.
  Home is the Linux convention for a tool like this, and it is what our own mpf
  package already does (DefaultOutputPath = $HOME/ISO) -- two disc dumpers from
  one repository should not disagree about where a dump goes. Downloads is the
  folder a browser empties; nobody looks for disc images there. Upstream's macOS
  branch keeps the download folder it has always used, untouched.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 1.0.1-3
- Patch the default dump folder so a packaged install can actually dump. It
  pointed at a Dumps subfolder beside the executable -- /usr/lib64/redumper-gui
  /Dumps here, owned by root: measured on a clean install, the user cannot
  create it (mkdir: Permission denied). Worse, dump.rs discards the error from
  create_dir_all(), so pressing DUMP did not stop with "permission denied"; the
  dump ran on and failed later for a reason that never named the cause. The
  patch keeps that folder wherever it IS writable (upstream's portable build)
  and otherwise falls back to a folder the user owns -- which is what upstream's
  own macOS branch has always done, the .app bundle being the very same
  predicament. Offered upstream.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 1.0.1-2
- Ship the launcher icon in all standard hicolor sizes (16-512), rendered at
  build time from upstream's single 512x512 PNG with a Lanczos filter. Before
  this only the 512 was installed and every desktop had to downscale it itself
  for panels and docks -- and this icon is a finely detailed disc sector, so a
  naive downscale to 24px turned it to mush. Generated rather than pre-rendered
  into this repo, so the packaged icon cannot drift from upstream's.
- %%check now fails the build if any icon size is missing or empty: a launcher
  with no icon is not something to discover after shipping.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 1.0.1-1
- Initial build of Redumper GUI v1.0.1 (Rust / egui), suggested by its author
  in the VGPC preservation community.
- Built from source rather than repackaging the upstream release binary: that
  binary is compiled on Ubuntu 24.04 and needs GLIBC_2.39, which would have
  left out EL8, EL9 and Ubuntu 22.04. Building from source covers every target
  instead -- Rust 1.85+ (edition 2024) is available on all of them.
- Crates are vendored into the source tarball and the build runs --offline,
  because no build root has network: not COPR's chroot, not OBS's.
- Does not bundle redumper. Upstream's archives ship a pinned b729 next to the
  GUI executable and the GUI runs its sibling by that name; a package cannot
  add a second /usr/bin/redumper, so the pinned build is packaged separately as
  redumper729 and symlinked into the GUI's private directory. Same for
  MPF.Check, whose symlink dangles harmlessly until mpf-check is installed --
  the GUI tests for exactly that.
- All GUI libraries are dlopen'd (winit, glutin) and thus invisible to rpm's
  automatic dependency extraction; declared by soname by hand.
