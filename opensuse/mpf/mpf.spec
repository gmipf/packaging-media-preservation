%global mpfver         3.8.3
%global mpfsnap        20260717142924.2cb07a1a
%global rolltag        rolling

%global debug_package      %{nil}
%global __strip            /bin/true
%global __os_install_post  %{nil}
%global _build_id_links    none

Name:           mpf
Version:        %{mpfver}~%{mpfsnap}
Release:        0
Summary:        Media Preservation Frontend suite (mpf-check, mpf-cli, mpf-gui)

License:        MIT
URL:            https://github.com/SabreTools/MPF

# The three self-contained .NET release ZIPs. OBS build roots are hermetic
# (no network), so these are fetched by the _service (download_files) from
# the constant `rolling` tag and committed as package sources.
Source0:        %{url}/releases/download/%{rolltag}/MPF.Check_net10.0_linux-x64_release.zip
Source1:        %{url}/releases/download/%{rolltag}/MPF.CLI_net10.0_linux-x64_release.zip
Source2:        %{url}/releases/download/%{rolltag}/MPF.Avalonia_net10.0_linux-x64_release.zip

# arm64 counterparts of Source0-2. OBS builds ONE package source across every
# enabled arch, so an arch-conditional Source: would commit only one arch's
# binaries; carrying both trios keeps the aarch64 build honest. The matching trio
# is unzipped in %%prep via %%ifarch. Same %%{rolltag} as the x64 set, so the
# _service fetches and the rolling watcher bumps both together. On the Debian
# lane they travel as Debtransform-Files extras swapped by debian/rules.
Source15:       %{url}/releases/download/%{rolltag}/MPF.Check_net10.0_linux-arm64_release.zip
Source16:       %{url}/releases/download/%{rolltag}/MPF.CLI_net10.0_linux-arm64_release.zip
Source17:       %{url}/releases/download/%{rolltag}/MPF.Avalonia_net10.0_linux-arm64_release.zip

# The recipe files below carry a URL for the same reason the upstream sources do:
# download_files fetches whatever a Source: names, and that is what keeps them OUT
# of _service. _service lives in OBS and only an `osc commit` can change it, so
# every file listed there would make it a function of our file list. See
# opensuse/redumper-mpf/redumper-mpf.spec for the measurement behind this.
Source3:        https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-gui.desktop
Source4:        https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-check.1
Source5:        https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-cli.1
Source6:        https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-gui.1
# ONE icon master. The smaller hicolor sizes are rendered from it at build time
# (see %%install) instead of being committed here as pre-rendered copies: five
# files that have to be kept in lockstep are five chances to update four of them.
# Checked before dropping the others: mpf-32/64/128/256.png were plain downscales
# of this 512 (RMSE < 0.02 against a fresh Lanczos resample), not hand-tuned
# artwork -- so nothing is lost, and 16/22/24/48 are gained.
Source14:       https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-512.png

Source99:       https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main/opensuse/mpf/mpf-rpmlintrc

ExclusiveArch:  x86_64 aarch64
BuildRequires:  unzip
# Renders the hicolor icon sizes from Source14 (see %%install). On openSUSE the
# package is ImageMagick, same name as on Fedora/EL.
BuildRequires:  ImageMagick
# NOTE: deliberately NO permissions-framework profile here. MPF gets no
# cap_sys_rawio -- see the %%files section for why granting it breaks the GUI.
# hicolor-icon-theme owns /usr/share/icons/hicolor/**; it is a runtime Requires
# below, but it must ALSO be in the build root: openSUSE's 50-check-filelist
# post-build check fails the build on directories that no *installed* package
# owns, and it only sees BuildRequires. (Fedora does not run this check.)
BuildRequires:  hicolor-icon-theme
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
Recommends:     redumper-mpf
Recommends:     aaru5
Recommends:     discimagecreator
# Avalonia 11.x ships only the X11 backend; on Wayland sessions the GUI runs
# through Xwayland.
#
# Expressed as SONAMEs rather than package names. These are weak deps and never
# enter the build root, so a wrong name breaks nothing loudly — it just silently
# resolves to nothing, which is what the fedora spellings (libX11, mesa-libGL,
# ...) did here: they do not exist on openSUSE, so a GUI install pulled none of
# them. Sonames are distro-agnostic and survive renames. Verified against the
# Leap 16.0 and Tumbleweed repodata: each is a real 64-bit Provides, coming from
# libX11-6, libICE6, libSM6, libXext6, libXi6, libXrandr2, libXcursor1,
# libglvnd, libfontconfig1 and libfreetype6. Note libGL.so.1 is provided by
# libglvnd, NOT by Mesa-libGL1.
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
# CLI and GUI zips. The package relies on the system-installed
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
# deletes config.json.
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
# `magick` is ImageMagick 7's CLI; older ImageMagick 6 has only `convert`.
# Leap and Tumbleweed differ here, so pick whichever exists in the buildroot.
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

# DO NOT hand MPF a cap_sys_rawio profile (permissions.d + %%set_permissions).
# It is both unnecessary and harmful:
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
%files
# meta-package: no files, only Requires above

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
* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717142924.2cb07a1a-0
- Add aarch64 (arm64) support: bundle the upstream linux-arm64 ZIPs of all three
  tools (Check, CLI, Avalonia) alongside linux-x64 and unzip the arch-matching
  trio via %%ifarch; ExclusiveArch now x86_64 aarch64. Ships UNTESTED on arm64
  (no hardware drive-access proof); the repackage path is architecture-neutral.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717142924.2cb07a1a-0
- Automated rolling-snapshot sync to upstream MPF commit 2cb07a1a (published 20260717142924 UTC).

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260717140939.19d13893-0
- Automated rolling-snapshot sync to upstream MPF commit 19d13893 (published 20260717140939 UTC).

* Wed Jul 15 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260715133029.4c0f474a-0
- Automated rolling-snapshot sync to upstream MPF commit 4c0f474a (published 20260715133029 UTC).

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260714185251.c7a09574-0
- Automated rolling-snapshot sync to upstream MPF commit c7a09574 (published 20260714185251 UTC).

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260714014450.252b3617-0
- Automated rolling-snapshot sync to upstream MPF commit 252b3617 (published 20260714014450 UTC).

* Tue Jul 14 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713172204.8602d4dd-0
- Point MPF at the PINNED redumper732 instead of the rolling `redumper`, in both
  the metadata and the config the wrapper seeds. b732 is the build MPF's
  publish-nix.sh bundles. The pin exists even though the rolling package carries
  the same build today: it moves, MPF has no version check, and the day b733 lands
  an MPF pointed at the rolling package would silently dump with an untested build.

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713172204.8602d4dd-0
- Automated rolling-snapshot sync to upstream MPF commit 8602d4dd (published 20260713172204 UTC).

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713042509.813e8305-0
- Ship the launcher icon in all standard hicolor sizes. We had 32/64/128/256/512
  as five pre-rendered PNGs; the sizes a panel or dock actually asks for -- 16,
  22, 24, 48 -- were missing, so the desktop downscaled the 32 (or the 512) on
  the fly for every taskbar slot. Now ONE master (mpf-512.png) is kept and the
  rest is rendered at build time with a Lanczos filter. The dropped PNGs were
  plain downscales anyway (RMSE < 0.02 against a fresh resample -- measured
  before removing them), so no hand-tuned artwork was lost.
- _service no longer fetches the four removed PNGs: those URLs would 404 and
  fail the source service outright.
- %%install fails the build if any icon size is missing or empty. `magick` (IM7)
  and `convert` (IM6) are both handled -- openSUSE ships ImageMagick 7, which
  provides both names, but the spec is shared in spirit with the EL8 build where
  only `convert` exists.
- Automated rolling-snapshot sync to upstream MPF commit 813e8305 (published 20260713042509 UTC).

* Mon Jul 13 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260713002008.75a62a53-0
- Automated rolling-snapshot sync to upstream MPF commit 75a62a53 (published 20260713002008 UTC).

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260712230315.2f3b511f-0
- Automated rolling-snapshot sync to upstream MPF commit 2f3b511f (published 20260712230315 UTC).

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260707133302.e1081655-0
- Drop the cap_sys_rawio permissions-framework profiles from all three MPF
  binaries. They made every file dialog in the GUI abort the process: a
  binary with file capabilities runs non-dumpable, so /proc/<pid>/root
  becomes root-owned, xdg-desktop-portal cannot identify the caller and
  answers "Portal operation not allowed: Unable to open /proc/<pid>/root".
  The Tmds.DBus exception escapes an async void click handler and kills MPF
  with SIGABRT. The capability was never needed either -- MPF issues no raw
  SCSI, and redumper / aaru / discimagecreator carry cap_sys_rawio on their
  own binaries, which the kernel grants at exec no matter who starts them.
- Wrappers now also seed and heal DefaultOutputPath to an absolute path under
  the user's home ($HOME/ISO). Upstream defaults it to the relative "ISO",
  which in a /usr-tree install resolves against the working directory, so
  dumps landed wherever the app was started from.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 3.8.3~20260707133302.e1081655-0
- Initial openSUSE (OBS) packaging of the MPF suite (mpf-check, mpf-cli,
  mpf-gui), synced to the same rolling snapshot as the Fedora lane
  (upstream commit e1081655, published 20260707133302 UTC).

* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 3.8.2~20260703023433.eb239b60-0
- Initial openSUSE (OBS) packaging of the MPF suite (mpf meta + mpf-check,
  mpf-cli, mpf-gui) from the upstream rolling snapshot eb239b60.
- Repackage of the three self-contained .NET 10 release ZIPs (identical
  artifacts to the Fedora/COPR lane); fetched via the _service
  (download_files) from the constant `rolling` tag and committed, since
  OBS build roots have no network.
- .NET runtime Requires mapped to openSUSE names under %%if 0%%{?suse_version}
  (krb5, libopenssl3, libz1, libunwind.so.8; libicu + jq portable) on all
  three subpackages.
- cap_sys_rawio granted per subpackage through the openSUSE permissions
  framework (permissions.d profile + %%set_permissions / %%verify_permissions),
  the distro-native equivalent of the Fedora spec's %%caps entries.
