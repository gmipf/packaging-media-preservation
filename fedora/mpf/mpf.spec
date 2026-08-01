%global mpfver         3.9.0
%global mpfsnap        20260801184626.7d262ae5
%global rolltag        rolling

%global debug_package      %{nil}
%global __strip            /bin/true
%global __os_install_post  %{nil}
%global _build_id_links    none

Name:           mpf
Version:        %{mpfver}~%{mpfsnap}
# watch-mpf-rolling.yml resets this to 1 on every new upstream rolling
# snapshot: a fresh %%{mpfsnap} is a new identity, so the packaging
# iteration counter starts over (RPM sorts on Version first, so -1 still
# supersedes the previous snapshot's -N). Bump manually only for
# spec-only changes that keep the same snapshot; per-change rationale
# lives in the changelog. (Stuck at 5 here from pre-fix manual bumps of
# the 71dafe3d snapshot — already shipped as -5, so left as-is to avoid
# a downgrade; the next snapshot resets it.)
Release:        1%{?dist}
Summary:        Media Preservation Frontend suite (mpf-check, mpf-cli, mpf-gui)

License:        MIT
URL:            https://github.com/SabreTools/MPF

Source0:        %{url}/releases/download/%{rolltag}/MPF.Check_net10.0_linux-x64_release.zip
Source1:        %{url}/releases/download/%{rolltag}/MPF.CLI_net10.0_linux-x64_release.zip
Source2:        %{url}/releases/download/%{rolltag}/MPF.Avalonia_net10.0_linux-x64_release.zip

# arm64 counterparts of Source0-2. All three arch pairs are bundled because
# packit builds ONE SRPM that COPR/OBS then build across every arch chroot -- an
# arch-conditional Source: would bake one arch's binaries into the SRPM and the
# aarch64 build would ship x86 binaries. The matching trio is unzipped in %%prep
# via %%ifarch. Same %%{rolltag} as the x64 set, so the rolling watcher picks up
# both in one go. On the Debian lane they travel as Debtransform-Files extras.
Source15:       %{url}/releases/download/%{rolltag}/MPF.Check_net10.0_linux-arm64_release.zip
Source16:       %{url}/releases/download/%{rolltag}/MPF.CLI_net10.0_linux-arm64_release.zip
Source17:       %{url}/releases/download/%{rolltag}/MPF.Avalonia_net10.0_linux-arm64_release.zip

Source3:        mpf-gui.desktop
Source4:        mpf-check.1
Source5:        mpf-cli.1
Source6:        mpf-gui.1

# ONE icon master. The smaller hicolor sizes are rendered from it at build time
# (see %%install) instead of being committed here as pre-rendered copies: five
# files that have to be kept in lockstep are five chances to update four of them.
# Checked before dropping the others: mpf-32/64/128/256.png were plain downscales
# of this 512 (RMSE < 0.02 against a fresh Lanczos resample), not hand-tuned
# artwork -- so nothing is lost, and 16/22/24/48 are gained.
Source14:       mpf-512.png

ExclusiveArch:  x86_64 aarch64
BuildRequires:  unzip
# Renders the hicolor icon sizes from Source14 (see %%install).
BuildRequires:  ImageMagick
AutoReqProv:    no

# Meta-package: pulls in all three subpackages.
Requires:       %{name}-check = %{version}-%{release}
Requires:       %{name}-cli   = %{version}-%{release}
Requires:       %{name}-gui   = %{version}-%{release}

%description
Media Preservation Frontend (MPF) is a suite of tools that drives the
optical-media dumping workflow used by the Redump preservation project.
Each tool wraps a specific role in the workflow:

  * mpf-check  log validator + submission-info writer
  * mpf-cli    headless dump orchestrator
  * mpf-gui    Avalonia desktop frontend

This meta-package installs all three. Install the individual subpackages
if you only need part of the suite.

# ---------------------------------------------------------------- check

%package check
Summary:        Validator that generates Redump !submissionInfo.txt from disc-dump logs
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
Requires:       jq

%description check
MPF.Check reads the log files next to a finished optical-media dump and
writes a !submissionInfo.txt alongside in the Redump submission format.
Supported dump sources include Redumper, Aaru, DiscImageCreator, Cleanrip
and UmdImageCreator.

Optional copy-protection scanning is available via --path/--scan; it
inspects the files on the mounted medium and needs no privileges beyond
read access to them.

Self-contained .NET 10 binary, repackaged unmodified from the upstream
rolling release.

# ------------------------------------------------------------------ cli

%package cli
Summary:        Headless dump orchestrator (drives redumper, aaru, discimagecreator)
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
Requires:       jq
# The three backends, and why two of them are PINNED and one is not:
#
#   redumper-mpf  PINNED to the build MPF's publish-nix.sh bundles. NOT the rolling
#                `redumper` -- not even on a day when the rolling package carries
#                the very same build (it does right now: both are b732). The
#                rolling package MOVES. The day b733 lands, an MPF pointed at it
#                would silently dump with a build MPF was never tested against, and
#                MPF has no version check of any kind to notice -- it just reads
#                whatever version it finds out of the log and writes it into the
#                submission. Today's equality is an accident of timing.
#                ⇒ When MPF bundles a new build, GENERATE redumper<N> and repoint
#                  here. Never collapse this back to the rolling package.
#   aaru5        PINNED. MPF supports only the latest STABLE Aaru; the rolling
#                `aaru` is a 6.0 alpha with a different command line and does not
#                run in MPF at all.
#   dic          NOT pinned, deliberately. DiscImageCreator's command-line surface
#                is effectively frozen -- what still lands upstream is bugfixes and
#                new disc types, not features that could break a frontend. A pin
#                would guard against a risk that does not exist.
#
# scripts/status.sh compares MPF's bundled builds against these and goes red on
# drift. The wrapper below seeds the same names into MPF's config.
Recommends:     redumper-mpf
Recommends:     aaru5
Recommends:     discimagecreator

%description cli
MPF.CLI orchestrates the disc-dumping workflow from a terminal: it drives
the selected backend (redumper, aaru or discimagecreator) through the
dump, post-processes the output and writes the submission info.

MPF itself needs no elevated privileges: it never talks to the drive
directly. The raw SCSI access belongs to the backend dumper, which
carries the cap_sys_rawio capability on its own binary and receives it
regardless of who starts it.

The bundled Programs/Creator/ folder from the upstream ZIP is dropped at
package build time in favor of the system-installed dumpers; mpf-cli
resolves the backend binary via PATH.

Self-contained .NET 10 binary, repackaged from the upstream rolling
release.

# ------------------------------------------------------------------ gui

%package gui
Summary:        Avalonia desktop frontend for the MPF disc-dumping workflow
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
Requires:       jq
Requires:       hicolor-icon-theme
Requires:       desktop-file-utils
# Same three backends as mpf-cli, same reasons -- see the block above it. In
# short: redumper-mpf and aaru5 are PINNED to the builds MPF bundles and must not
# be collapsed into the rolling packages; dic is deliberately not pinned.
Recommends:     redumper-mpf
Recommends:     aaru5
Recommends:     discimagecreator
# Avalonia 11.x ships only the X11 backend; on Wayland sessions the GUI
# runs through Xwayland. Recommends are library-level so the same set
# covers both X11 and XWayland-on-Wayland setups.
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

%description gui
MPF.Avalonia is the desktop GUI of the MPF suite. It drives the disc-
dumping workflow with a graphical interface built on Avalonia (.NET
cross-platform UI toolkit).

The GUI runs unprivileged: it never talks to the drive directly, and the
backend dumper it spawns carries the cap_sys_rawio capability on its own
binary. Granting the capability to the GUI itself would break every file
dialog, because a process with file capabilities is non-dumpable and
xdg-desktop-portal then cannot identify it.

The bundled Programs/Creator/ folder from the upstream ZIP is dropped at
package build time in favor of the system-installed dumpers, resolved
via PATH.

On Wayland sessions the GUI runs through Xwayland (Avalonia 11.x has no
native Wayland backend yet); on X11 sessions it runs natively.

Self-contained .NET 10 binary, repackaged from the upstream rolling
release.

# =====================================================================

%prep
%setup -q -c -T

# Unpack the arch-matching trio (see the Source15-17 block above).
%ifarch aarch64
unzip -q %{SOURCE15}

mkdir cli
pushd cli
unzip -q %{SOURCE16}
popd

mkdir gui
pushd gui
unzip -q %{SOURCE17}
popd
%else
unzip -q %{SOURCE0}

mkdir cli
pushd cli
unzip -q %{SOURCE1}
popd

mkdir gui
pushd gui
unzip -q %{SOURCE2}
popd
%endif

# Drop the bundled Programs/Creator/ folder (~1.5 MB code + data) from
# CLI and GUI zips. The Fedora package relies on the system-installed
# redumper / aaru / discimagecreator, resolved via PATH instead.
rm -rf cli/Programs gui/Programs

%build
# Self-contained binaries; nothing to compile.

%install
# --- check: real binary + wrapper ---
install -d %{buildroot}%{_libdir}/mpf-check
install -m 0755 MPF.Check %{buildroot}%{_libdir}/mpf-check/MPF.Check

# --- cli: real binary + wrapper ---
install -d %{buildroot}%{_libdir}/mpf-cli
install -m 0755 cli/MPF.CLI %{buildroot}%{_libdir}/mpf-cli/MPF.CLI

# --- gui: upstream zip names the binary "MPF"; we install it as
#         MPF.Avalonia to make the role obvious on disk.
install -d %{buildroot}%{_libdir}/mpf-gui
install -m 0755 gui/MPF %{buildroot}%{_libdir}/mpf-gui/MPF.Avalonia

# --- /usr/bin/ wrappers ---
# The wrappers seed AND heal ~/.config/mpf/config.json so the three
# dumper-path keys and the output path are always present and usable. We
# seed BARE tool names (aaru5, DiscImageCreator.out, redumper) rather than
# absolute paths: MPF (SabreTools/MPF#979) resolves a bare name through its
# runtime directory and $PATH, so the config stays valid no matter where
# the distro installs the dumpers and keeps working after the user
# deletes config.json. Upstream MPF otherwise defaults to relative bundle
# paths ("Programs/Creator/DiscImageCreator.out") that don't exist in a
# /usr-tree install.
#
# The same mismatch applies to DefaultOutputPath, whose upstream default is
# the RELATIVE "ISO". For the portable Windows bundle that means "an ISO
# folder next to the executable"; in a /usr-tree install there is no such
# place, and a relative path resolves against the process's working
# directory instead -- so dumps land wherever the app happened to be
# started from, and the Browse dialog opens there. We point it at an
# absolute directory in the user's home; MPF creates it on first dump.
#
# Behavior at every launch:
#   * config missing/empty  -> write a minimal 4-key seed
#   * config exists         -> reset each Aaru/DIC/Redumper key IFF its
#                              value no longer resolves (empty, a bare
#                              name not on $PATH, or a path that no longer
#                              exists), and reset DefaultOutputPath IFF it
#                              is empty or relative; an absolute path the
#                              user chose is kept
# Atomicity: heal writes to a sibling tmp file via mktemp + mv so a
# crashed jq never leaves a half-written config behind.
install -d %{buildroot}%{_bindir}

# All three wrappers share the same seed/heal preamble; only the exec
# target differs. We generate them in a small loop to keep the spec
# DRY — the heredoc body is reused verbatim.
for pair in \
    "mpf-check:/usr/lib64/mpf-check/MPF.Check" \
    "mpf-cli:/usr/lib64/mpf-cli/MPF.CLI" \
    "mpf-gui:/usr/lib64/mpf-gui/MPF.Avalonia" ; do
    name=${pair%%:*}
    target=${pair#*:}
    cat > %{buildroot}%{_bindir}/$name <<EOF
#!/bin/sh
config_dir="\${XDG_CONFIG_HOME:-\$HOME/.config}/mpf"
config="\$config_dir/config.json"
aaru_p=aaru5
dic_p=DiscImageCreator.out
red_p=redumper-mpf
# Without a HOME there is no sane home-relative output directory; leave the
# key alone rather than rewriting it to a root-owned "/ISO".
out_p=""
[ -n "\$HOME" ] && out_p="\$HOME/ISO"
mkdir -p "\$config_dir" 2>/dev/null

# Does a configured tool value resolve the way MPF (#979) resolves it? A
# value containing a separator must exist as a file; a bare name must be
# found on \$PATH (command -v mirrors MPF's runtime-dir + \$PATH lookup).
resolves() {
    case "\$1" in
        "")  return 1 ;;
        */*) [ -e "\$1" ] ;;
        *)   command -v "\$1" >/dev/null 2>&1 ;;
    esac
}

# The output path must be absolute: a relative one resolves against the
# working directory, which for a /usr-installed app is wherever it was
# started from. The directory need not exist -- MPF creates it.
is_abs() {
    case "\$1" in /*) return 0 ;; *) return 1 ;; esac
}

if [ ! -s "\$config" ]; then
    cat > "\$config" <<JSON
{
  "AaruPath": "\$aaru_p",
  "DiscImageCreatorPath": "\$dic_p",
  "RedumperPath": "\$red_p",
  "DefaultOutputPath": "\${out_p:-ISO}"
}
JSON
elif command -v jq >/dev/null 2>&1; then
    ca=\$(jq -r '.AaruPath // ""' "\$config" 2>/dev/null)
    cd_=\$(jq -r '.DiscImageCreatorPath // ""' "\$config" 2>/dev/null)
    cr=\$(jq -r '.RedumperPath // ""' "\$config" 2>/dev/null)
    co=\$(jq -r '.DefaultOutputPath // ""' "\$config" 2>/dev/null)
    fa=0; fd=0; fr=0; fo=0
    resolves "\$ca"  || fa=1
    resolves "\$cd_" || fd=1
    resolves "\$cr"  || fr=1
    [ -n "\$out_p" ] && { is_abs "\$co" || fo=1; }
    if [ \$((fa + fd + fr + fo)) -gt 0 ]; then
        tmp=\$(mktemp -p "\$config_dir" .config.json.XXXXXX 2>/dev/null)
        if [ -n "\$tmp" ] && jq \\
            --arg ap "\$aaru_p" --arg dp "\$dic_p" --arg rp "\$red_p" \\
            --arg op "\$out_p" \\
            --argjson fa "\$fa" --argjson fd "\$fd" --argjson fr "\$fr" \\
            --argjson fo "\$fo" '
            (if \$fa == 1 then .AaruPath = \$ap else . end)
            | (if \$fd == 1 then .DiscImageCreatorPath = \$dp else . end)
            | (if \$fr == 1 then .RedumperPath = \$rp else . end)
            | (if \$fo == 1 then .DefaultOutputPath = \$op else . end)
            ' "\$config" > "\$tmp" 2>/dev/null; then
            mv "\$tmp" "\$config"
        else
            [ -n "\$tmp" ] && rm -f "\$tmp"
        fi
    fi
fi

exec $target "\$@"
EOF
    chmod 0755 %{buildroot}%{_bindir}/$name
done

# --- desktop entry (gui only) ---
install -d %{buildroot}%{_datadir}/applications
install -m 0644 %{SOURCE3} %{buildroot}%{_datadir}/applications/mpf-gui.desktop

# --- hicolor icons (gui only) ---
# We used to ship 32/64/128/256/512 only. The sizes a panel or dock actually
# reaches for -- 16, 22, 24, 48 -- were missing, so the desktop had to downscale
# the 32 (or worse, the 512) on the fly for every taskbar slot. Render the full
# standard set once here, with a proper Lanczos filter.
#
# ImageMagick 7 renamed the CLI to `magick` and deprecated `convert`; EL8 still
# ships ImageMagick 6, which has only `convert`. Pick whichever exists in the
# buildroot instead of assuming a version.
if command -v magick >/dev/null 2>&1; then IM=magick; else IM=convert; fi
for sz in 16 22 24 32 48 64 128 256; do
  install -d %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps
  $IM %{SOURCE14} -filter Lanczos -resize ${sz}x${sz} \
      %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/mpf.png
done
# The 512 is the master itself -- installed as-is, never resampled.
install -d %{buildroot}%{_datadir}/icons/hicolor/512x512/apps
install -m 0644 %{SOURCE14} %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/mpf.png

# A hicolor directory that exists but holds no icon is worse than none: the
# launcher silently comes up blank. Fail the build instead.
for sz in 16 22 24 32 48 64 128 256 512; do
  test -s %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps/mpf.png \
      || { echo "icon ${sz}x${sz} missing or empty"; exit 1; }
done

# --- manpages ---
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE4} %{buildroot}%{_mandir}/man1/mpf-check.1
install -m 0644 %{SOURCE5} %{buildroot}%{_mandir}/man1/mpf-cli.1
install -m 0644 %{SOURCE6} %{buildroot}%{_mandir}/man1/mpf-gui.1

# =====================================================================

%files
# meta-package: no files, only Requires above

# DO NOT add %%caps(cap_sys_rawio=ep) to the MPF binaries. It is not merely
# unnecessary, it is actively harmful:
#
#   * Unnecessary: MPF never issues a raw SCSI command. Its whole device
#     interaction is enumerating drives and reading files off the mounted
#     medium (the copy-protection scanner takes a filesystem *path*). The raw
#     I/O happens in redumper / aaru / discimagecreator, and those carry the
#     capability on their own binaries -- the kernel grants file capabilities
#     from the executed file, so a capability-less MPF still spawns a fully
#     privileged dumper. Drive nodes are reachable via the uaccess ACL those
#     packages install.
#
#   * Harmful: executing a file with capabilities makes the process
#     non-dumpable (AT_SECURE), which flips /proc/<pid>/root to root:root.
#     xdg-desktop-portal reads exactly that path to identify the calling app;
#     it fails with "Portal operation not allowed: Unable to open
#     /proc/<pid>/root" and refuses the request. Every file dialog in the GUI
#     then throws a DBusException out of an async void click handler, which
#     terminates the process. Measured: same binary, capability set -> portal
#     denies; capability removed -> portal accepts.
%files check
%{_bindir}/mpf-check
%attr(0755,root,root) %{_libdir}/mpf-check/MPF.Check
%dir %{_libdir}/mpf-check
%{_mandir}/man1/mpf-check.1*

%files cli
%{_bindir}/mpf-cli
%attr(0755,root,root) %{_libdir}/mpf-cli/MPF.CLI
%dir %{_libdir}/mpf-cli
%{_mandir}/man1/mpf-cli.1*

%files gui
%{_bindir}/mpf-gui
%attr(0755,root,root) %{_libdir}/mpf-gui/MPF.Avalonia
%dir %{_libdir}/mpf-gui
%{_mandir}/man1/mpf-gui.1*
%{_datadir}/applications/mpf-gui.desktop
%{_datadir}/icons/hicolor/*/apps/mpf.png

%changelog
* Sat Aug 01 2026 gmipf <gmipf64@gmail.com> - 3.9.0~20260801184626.7d262ae5-1
- Automated rolling-snapshot sync to upstream MPF commit 7d262ae5
  (rolling tag, published 20260801184626 UTC); Release reset to 1.

* Sat Aug 01 2026 gmipf <gmipf64@gmail.com> - 3.9.0~20260801041056.036100d8-1
- Automated rolling-snapshot sync to upstream MPF commit 036100d8
  (rolling tag, published 20260801041056 UTC); Release reset to 1.

* Fri Jul 31 2026 gmipf <gmipf64@gmail.com> - 3.9.0~20260731160924.512561ed-1
- Automated rolling-snapshot sync to upstream MPF commit 512561ed
  (rolling tag, published 20260731160924 UTC); Release reset to 1.

* Fri Jul 31 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260731015546.6db6a2c0-1
- Automated rolling-snapshot sync to upstream MPF commit 6db6a2c0
  (rolling tag, published 20260731015546 UTC); Release reset to 1.

* Tue Jul 28 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260728164439.574ed2c6-1
- Automated rolling-snapshot sync to upstream MPF commit 574ed2c6
  (rolling tag, published 20260728164439 UTC); Release reset to 1.

* Tue Jul 28 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260728133430.9e7f7e9b-1
- Automated rolling-snapshot sync to upstream MPF commit 9e7f7e9b
  (rolling tag, published 20260728133430 UTC); Release reset to 1.

* Mon Jul 27 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260727154509.d922e1da-1
- Automated rolling-snapshot sync to upstream MPF commit d922e1da
  (rolling tag, published 20260727154509 UTC); Release reset to 1.

* Mon Jul 27 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260727005703.d996667a-1
- Automated rolling-snapshot sync to upstream MPF commit d996667a
  (rolling tag, published 20260727005703 UTC); Release reset to 1.

* Sun Jul 26 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260726165639.479e5772-1
- Automated rolling-snapshot sync to upstream MPF commit 479e5772
  (rolling tag, published 20260726165639 UTC); Release reset to 1.

* Sun Jul 26 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260726162059.26438d8e-1
- Automated rolling-snapshot sync to upstream MPF commit 26438d8e
  (rolling tag, published 20260726162059 UTC); Release reset to 1.

* Sun Jul 26 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260726154500.045878b0-1
- Automated rolling-snapshot sync to upstream MPF commit 045878b0
  (rolling tag, published 20260726154500 UTC); Release reset to 1.

* Sun Jul 26 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260726043053.1e96147e-1
- Automated rolling-snapshot sync to upstream MPF commit 1e96147e
  (rolling tag, published 20260726043053 UTC); Release reset to 1.

* Sat Jul 25 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260725210714.7c0a426a-1
- Automated rolling-snapshot sync to upstream MPF commit 7c0a426a
  (rolling tag, published 20260725210714 UTC); Release reset to 1.

* Sat Jul 25 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260725174402.b057aa37-1
- Automated rolling-snapshot sync to upstream MPF commit b057aa37
  (rolling tag, published 20260725174402 UTC); Release reset to 1.

* Sat Jul 25 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260725135718.0435c89b-1
- Automated rolling-snapshot sync to upstream MPF commit 0435c89b
  (rolling tag, published 20260725135718 UTC); Release reset to 1.

* Sat Jul 25 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260725000844.f671c661-1
- Automated rolling-snapshot sync to upstream MPF commit f671c661
  (rolling tag, published 20260725000844 UTC); Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260724234123.5c736f88-1
- Automated rolling-snapshot sync to upstream MPF commit 5c736f88
  (rolling tag, published 20260724234123 UTC); Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260724222934.2cc88b1c-1
- Automated rolling-snapshot sync to upstream MPF commit 2cc88b1c
  (rolling tag, published 20260724222934 UTC); Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260724150633.a9425fab-1
- Automated rolling-snapshot sync to upstream MPF commit a9425fab
  (rolling tag, published 20260724150633 UTC); Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260724132502.e01984f7-1
- Automated rolling-snapshot sync to upstream MPF commit e01984f7
  (rolling tag, published 20260724132502 UTC); Release reset to 1.

* Wed Jul 22 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260722174504.175c1089-1
- Automated rolling-snapshot sync to upstream MPF commit 175c1089
  (rolling tag, published 20260722174504 UTC); Release reset to 1.

* Tue Jul 21 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260721132649.7f6aa4a3-1
- Automated rolling-snapshot sync to upstream MPF commit 7f6aa4a3
  (rolling tag, published 20260721132649 UTC); Release reset to 1.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717142924.2cb07a1a-2
- Add aarch64 (arm64) support. Bundle the upstream linux-arm64 release ZIPs of
  all three tools (Check, CLI, Avalonia) alongside the linux-x64 set and unzip
  the arch-matching trio in %%prep via %%ifarch; ExclusiveArch is now x86_64
  aarch64. packit builds ONE SRPM that COPR/OBS build across every arch chroot,
  so an arch-conditional Source: would bake one arch's binaries into the SRPM;
  bundling both sets is the only correct way. Both sets come from the same
  %%{rolltag}, so the rolling watcher picks them up together. arm64 ships
  UNTESTED -- no hardware drive-access proof exists for it; the repackaging path
  is architecture-neutral but this is deliberately not claimed as proven.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717142924.2cb07a1a-1
- Automated rolling-snapshot sync to upstream MPF commit 2cb07a1a
  (rolling tag, published 20260717142924 UTC); Release reset to 1.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717140939.19d13893-1
- Automated rolling-snapshot sync to upstream MPF commit 19d13893
  (rolling tag, published 20260717140939 UTC); Release reset to 1.

* Wed Jul 15 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260715133029.4c0f474a-1
- Automated rolling-snapshot sync to upstream MPF commit 4c0f474a
  (rolling tag, published 20260715133029 UTC); Release reset to 1.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260714185251.c7a09574-1
- Automated rolling-snapshot sync to upstream MPF commit c7a09574
  (rolling tag, published 20260714185251 UTC); Release reset to 1.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260714014450.252b3617-1
- Automated rolling-snapshot sync to upstream MPF commit 252b3617
  (rolling tag, published 20260714014450 UTC); Release reset to 1.

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713172204.8602d4dd-2
- Point MPF at the PINNED redumper732 instead of the rolling `redumper`, in both
  the metadata (Recommends) and the config the wrapper seeds. b732 is the build
  MPF's publish-nix.sh bundles, so an MPF dump now runs the dumper build its
  upstream actually tested with.
- The pin exists even though the rolling package carries the very same build
  today. That equality is an accident of timing, not something to lean on: the
  rolling package moves, and the day redumper b733 lands, an MPF pointed at it
  would silently dump with a build it was never tested against -- MPF has no
  version check of any kind and would never say so. When MPF bundles a new build,
  a new redumper<N> is generated and MPF is repointed; scripts/status.sh goes red
  until that is done.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713172204.8602d4dd-1
- Automated rolling-snapshot sync to upstream MPF commit 8602d4dd
  (rolling tag, published 20260713172204 UTC); Release reset to 1.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713042509.813e8305-2
- Ship the launcher icon in all standard hicolor sizes. We had 32/64/128/256/512
  as five pre-rendered PNGs; the sizes a panel or dock actually asks for -- 16,
  22, 24, 48 -- were missing, so the desktop downscaled the 32 (or the 512) on
  the fly for every taskbar slot.
- Now ONE master (mpf-512.png) is kept in the repo and the rest is rendered at
  build time with a Lanczos filter. Five files that must stay in lockstep are
  five chances to update four of them. The dropped PNGs were plain downscales
  anyway -- measured (RMSE < 0.02 against a fresh resample) before removing them,
  so no hand-tuned artwork was lost.
- ImageMagick 7 renamed the CLI to `magick` and deprecated `convert`; EL8 still
  carries ImageMagick 6 with only `convert`. The spec picks whichever exists in
  the buildroot rather than assuming; both paths were mock-built (fedora-43 and
  epel-8) before this landed.
- %%install now fails the build if any icon size is missing or empty: a launcher
  that silently comes up blank is not something to find out after shipping.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713042509.813e8305-1
- Automated rolling-snapshot sync to upstream MPF commit 813e8305
  (rolling tag, published 20260713042509 UTC); Release reset to 1.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713002008.75a62a53-1
- Automated rolling-snapshot sync to upstream MPF commit 75a62a53
  (rolling tag, published 20260713002008 UTC); Release reset to 1.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260712230315.2f3b511f-1
- Automated rolling-snapshot sync to upstream MPF commit 2f3b511f
  (rolling tag, published 20260712230315 UTC); Release reset to 1.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260707133302.e1081655-2
- Drop cap_sys_rawio from all three MPF binaries. It made every file dialog
  in the GUI abort the process: a binary with file capabilities runs
  non-dumpable, so /proc/<pid>/root becomes root-owned, xdg-desktop-portal
  cannot identify the caller and answers "Portal operation not allowed:
  Unable to open /proc/<pid>/root". The Tmds.DBus exception escapes an
  async void click handler and kills MPF with SIGABRT. Measured on the same
  binary: capability set -> portal denies, capability removed -> portal
  accepts. The capability was never needed either -- MPF issues no raw SCSI
  (its protection scanner takes a filesystem path), and redumper / aaru /
  discimagecreator carry cap_sys_rawio on their own binaries, which the
  kernel grants at exec no matter who starts them. The package descriptions
  and manpages claimed otherwise; corrected.
- Wrappers now also seed and heal DefaultOutputPath. Upstream defaults it to
  the relative "ISO", which suits the portable Windows bundle but in a
  /usr-tree install resolves against the working directory, so dumps landed
  wherever the app was started from. It is now an absolute path under the
  user's home ($HOME/ISO); an absolute path the user picked is left alone.

* Tue Jul 07 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260707133302.e1081655-1
- Automated rolling-snapshot sync to upstream MPF commit e1081655
  (rolling tag, published 20260707133302 UTC); Release reset to 1.

* Mon Jul 06 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260706160143.afd616d9-1
- Automated rolling-snapshot sync to upstream MPF commit afd616d9
  (rolling tag, published 20260706160143 UTC); Release reset to 1.

* Mon Jul 06 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260706021400.78237d7d-1
- Automated rolling-snapshot sync to upstream MPF commit 78237d7d
  (rolling tag, published 20260706021400 UTC); Release reset to 1.

* Fri Jul 03 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260703023433.eb239b60-1
- Automated rolling-snapshot sync to upstream MPF commit eb239b60
  (rolling tag, published 20260703023433 UTC); Release reset to 1.
- Portability for openSUSE (Leap 15.6 + Tumbleweed) on check/cli/gui: the
  .NET runtime Requires are renamed under a %if 0%{?suse_version} guard
  (krb5-libs->krb5, openssl-libs->libopenssl3, zlib->libz1, libunwind by its
  stable soname since Leap ships `libunwind` and Tumbleweed `libunwind8`);
  `libicu` and `jq` stay portable. Fedora/EL names unchanged. All four
  subpackages install cleanly on both openSUSE chroots (verified via mock).

* Fri Jul 03 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260702213611.ce6113d1-1
- Automated rolling-snapshot sync to upstream MPF commit ce6113d1
  (rolling tag, published 20260702213611 UTC); Release reset to 1.

* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260702131742.1b3bfc0f-1
- Automated rolling-snapshot sync to upstream MPF commit 1b3bfc0f
  (rolling tag, published 20260702131742 UTC); Release reset to 1.

* Thu Jul 02 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260702015612.47505972-1
- Automated rolling-snapshot sync to upstream MPF commit 47505972
  (rolling tag, published 20260702015612 UTC); Release reset to 1.

* Wed Jul 01 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260701144922.9fd7e26a-1
- Automated rolling-snapshot sync to upstream MPF commit 9fd7e26a
  (rolling tag, published 20260701144922 UTC); Release reset to 1.

* Wed Jul 01 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260701130057.d43cf539-1
- Automated rolling-snapshot sync to upstream MPF commit d43cf539
  (rolling tag, published 20260701130057 UTC); Release reset to 1.

* Wed Jul 01 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260701023402.e97d8081-1
- Automated rolling-snapshot sync to upstream MPF commit e97d8081
  (rolling tag, published 20260701023402 UTC); Release reset to 1.

* Tue Jun 30 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260630140234.3bb146a3-1
- Automated rolling-snapshot sync to upstream MPF commit 3bb146a3
  (rolling tag, published 20260630140234 UTC); Release reset to 1.

* Mon Jun 29 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260629155431.37cfe19b-1
- Automated rolling-snapshot sync to upstream MPF commit 37cfe19b
  (rolling tag, published 20260629155431 UTC); Release reset to 1.

* Mon Jun 29 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260629131442.fb2a801c-1
- Automated rolling-snapshot sync to upstream MPF commit fb2a801c
  (rolling tag, published 20260629131442 UTC); Release reset to 1.

* Mon Jun 29 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260628223204.0746a794-1
- Automated rolling-snapshot sync to upstream MPF commit 0746a794
  (rolling tag, published 20260628223204 UTC); Release reset to 1.

* Sun Jun 28 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260628033545.8e5dc324-1
- Automated rolling-snapshot sync to upstream MPF commit 8e5dc324
  (rolling tag, published 20260628033545 UTC); Release reset to 1.

* Sat Jun 27 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260627014238.df6ae589-1
- Automated rolling-snapshot sync to upstream MPF commit df6ae589
  (rolling tag, published 20260627014238 UTC); Release reset to 1.

* Fri Jun 26 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260626192341.d906045f-1
- Automated rolling-snapshot sync to upstream MPF commit d906045f
  (rolling tag, published 20260626192341 UTC); Release reset to 1.

* Fri Jun 26 2026 gmipf <gmipf64@gmail.com> - 3.8.1~20260626125727.a0fbfb5c-1
- Automated rolling-snapshot sync to upstream MPF commit a0fbfb5c
  (rolling tag, published 20260626125727 UTC); Release reset to 1.

* Thu Jun 25 2026 gmipf <gmipf64@gmail.com> - 3.8.0~20260625023516.db43edbe-1
- Automated rolling-snapshot sync to upstream MPF commit db43edbe
  (rolling tag, published 20260625023516 UTC); Release reset to 1.

* Wed Jun 24 2026 gmipf <gmipf64@gmail.com> - 3.8.0~20260624155942.eee55902-1
- Automated rolling-snapshot sync to upstream MPF commit eee55902
  (rolling tag, published 20260624155942 UTC); Release reset to 1.

* Wed Jun 24 2026 gmipf <gmipf64@gmail.com> - 3.8.0~20260623212849.ad3bc776-1
- Automated rolling-snapshot sync to upstream MPF commit ad3bc776
  (rolling tag, published 20260623212849 UTC); Release reset to 1.

* Tue Jun 23 2026 gmipf <gmipf64@gmail.com> - 3.8.0~20260623174911.81c5eeb2-1
- Automated rolling-snapshot sync to upstream MPF commit 81c5eeb2
  (rolling tag, published 20260623174911 UTC); Release reset to 1.

* Tue Jun 23 2026 gmipf <gmipf64@gmail.com> - 3.8.0~20260623125342.1ab35222-1
- Automated rolling-snapshot sync to upstream MPF commit 1ab35222
  (rolling tag, published 20260623125342 UTC); Release reset to 1.

* Tue Jun 23 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260623024737.440a2717-1
- Automated rolling-snapshot sync to upstream MPF commit 440a2717
  (rolling tag, published 20260623024737 UTC); Release reset to 1.

* Mon Jun 22 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260622182104.2799fb22-1
- Automated rolling-snapshot sync to upstream MPF commit 2799fb22
  (rolling tag, published 20260622182104 UTC); Release reset to 1.

* Mon Jun 22 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260622125926.c02d31a0-1
- Automated rolling-snapshot sync to upstream MPF commit c02d31a0
  (rolling tag, published 20260622125926 UTC); Release reset to 1.

* Sun Jun 21 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260621125605.0a87e1f1-1
- Automated rolling-snapshot sync to upstream MPF commit 0a87e1f1
  (rolling tag, published 20260621125605 UTC); Release reset to 1.

* Sun Jun 21 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260621041529.f4d50a4f-1
- Automated rolling-snapshot sync to upstream MPF commit f4d50a4f
  (rolling tag, published 20260621041529 UTC); Release reset to 1.

* Sun Jun 21 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260621032843.deb17867-1
- Automated rolling-snapshot sync to upstream MPF commit deb17867
  (rolling tag, published 20260621032843 UTC); Release reset to 1.

* Tue Jun 16 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260612220844.b16abc89-5
- Wrappers now also heal an existing config.json: any Aaru/DIC/Redumper
  Path entry that is missing or points to a non-existent file is reset
  to the canonical /usr/bin location at each launch. Other config keys
  are left untouched. The previous Release-4 seed-only-on-empty path
  missed configs already populated by an earlier MPF.Avalonia run with
  upstream's relative "Programs/Creator/..." defaults baked in.
- Add Requires: jq on check/cli/gui for the heal logic (atomic mktemp +
  mv write, jq parse failure is a no-op so a corrupt config never
  blocks launch).

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260612220844.b16abc89-2
- Phase 5: refactor single-binary mpf-check.spec into a multi-subpackage
  mpf.spec that builds mpf-check, mpf-cli and mpf-gui from one SRPM. The
  main `mpf` package is a meta-package pulling in all three.
- Add mpf-gui.desktop and hicolor icons (32 / 64 / 128 / 256 / 512,
  extracted from upstream MPF.UI/Images/Icon.ico).
- Add handwritten manpages for mpf-check, mpf-cli and mpf-gui.
- Drop bundled Programs/Creator/ from cli/gui zips; the Fedora package
  uses the system-installed redumper / aaru / discimagecreator via PATH.
- Recommends X11/XWayland runtime libs on mpf-gui (Avalonia 11.x has no
  native Wayland backend yet).
- Release bumped to 2 because the previously published mpf-check
  3.7.1~20260612220844.b16abc89-1 occupied -1; this refactor reuses the
  same snapshot identity. Watcher resets to -1 on the next SHA change.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 3.7.1~20260612220844.b16abc89-1
- Migrate to tilde-style versioning (Version: 3.7.1~<UTC-TS>.<short-SHA>,
  Release: 1) to match the convention used on aaru: rolling snapshot
  identifier sits in Version after `~`, packaging iteration is the
  trailing -N of NEVRA.

* Sun Jun 14 2026 gmipf - 3.7.1-1
- Initial mpf-check standalone package, repackaging upstream rolling
  release.
