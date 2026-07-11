%global mpfver         3.8.3
%global mpfsnap        20260707133302.e1081655
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

Source3:        mpf-gui.desktop
Source4:        mpf-check.1
Source5:        mpf-cli.1
Source6:        mpf-gui.1

Source10:       mpf-32.png
Source11:       mpf-64.png
Source12:       mpf-128.png
Source13:       mpf-256.png
Source14:       mpf-512.png

ExclusiveArch:  x86_64
BuildRequires:  unzip
# openSUSE grants file capabilities through the permissions framework
# (chkstat), not a bare %%caps entry (see %%install / %%post per subpackage).
BuildRequires:  permissions
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
Requires:       jq

%description check
MPF.Check reads the log files next to a finished optical-media dump and
writes a !submissionInfo.txt alongside in the Redump submission format.
Supported dump sources include Redumper, Aaru, DiscImageCreator, Cleanrip
and UmdImageCreator.

Optional copy-protection scanning is available via --path/--scan; that
path uses vendor SCSI commands and requires CAP_SYS_RAWIO, which is set on
the shipped binary (via the openSUSE permissions framework) so no sudo is
needed.

Self-contained .NET 10 binary, repackaged unmodified from the upstream
rolling release.

# ------------------------------------------------------------------ cli

%package cli
Summary:        Headless dump orchestrator (drives redumper, aaru, discimagecreator)
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
Requires:       jq
Recommends:     redumper
Recommends:     aaru5
Recommends:     discimagecreator

%description cli
MPF.CLI orchestrates the disc-dumping workflow from a terminal: it drives
the selected backend (redumper, aaru or discimagecreator) through the
dump, post-processes the output and writes the submission info.

CAP_SYS_RAWIO is set on the shipped binary (via the openSUSE permissions
framework) for vendor-SCSI access.

The bundled Programs/Creator/ folder from the upstream ZIP is dropped at
package build time in favor of the system-installed dumpers; mpf-cli
resolves the backend binary via PATH.

Self-contained .NET 10 binary, repackaged from the upstream rolling
release.

# ------------------------------------------------------------------ gui

%package gui
Summary:        Avalonia desktop frontend for the MPF disc-dumping workflow
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
Requires:       jq
Requires:       hicolor-icon-theme
Requires:       desktop-file-utils
Recommends:     redumper
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

CAP_SYS_RAWIO is set on the shipped binary (via the openSUSE permissions
framework) for vendor-SCSI access.

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

unzip -q %{SOURCE0}

mkdir cli
pushd cli
unzip -q %{SOURCE1}
popd

mkdir gui
pushd gui
unzip -q %{SOURCE2}
popd

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
# dumper-path keys are always present and resolvable. We seed BARE tool
# names (aaru5, DiscImageCreator.out, redumper) rather than absolute
# paths: MPF (SabreTools/MPF#979) resolves a bare name through its
# runtime directory and $PATH, so the config stays valid no matter where
# the distro installs the dumpers and keeps working after the user
# deletes config.json.
#
# Behavior at every launch:
#   * config missing/empty  -> write a minimal 3-key bare-name seed
#   * config exists         -> reset each Aaru/DIC/Redumper key IFF its
#                              value no longer resolves (empty, a bare
#                              name not on $PATH, or a path that no longer
#                              exists); resolvable user values are kept
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
red_p=redumper
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

if [ ! -s "\$config" ]; then
    cat > "\$config" <<JSON
{
  "AaruPath": "\$aaru_p",
  "DiscImageCreatorPath": "\$dic_p",
  "RedumperPath": "\$red_p"
}
JSON
elif command -v jq >/dev/null 2>&1; then
    ca=\$(jq -r '.AaruPath // ""' "\$config" 2>/dev/null)
    cd_=\$(jq -r '.DiscImageCreatorPath // ""' "\$config" 2>/dev/null)
    cr=\$(jq -r '.RedumperPath // ""' "\$config" 2>/dev/null)
    fa=0; fd=0; fr=0
    resolves "\$ca"  || fa=1
    resolves "\$cd_" || fd=1
    resolves "\$cr"  || fr=1
    if [ \$((fa + fd + fr)) -gt 0 ]; then
        tmp=\$(mktemp -p "\$config_dir" .config.json.XXXXXX 2>/dev/null)
        if [ -n "\$tmp" ] && jq \\
            --arg ap "\$aaru_p" --arg dp "\$dic_p" --arg rp "\$red_p" \\
            --argjson fa "\$fa" --argjson fd "\$fd" --argjson fr "\$fr" '
            (if \$fa == 1 then .AaruPath = \$ap else . end)
            | (if \$fd == 1 then .DiscImageCreatorPath = \$dp else . end)
            | (if \$fr == 1 then .RedumperPath = \$rp else . end)
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
for sz in 32 64 128 256 512; do
  install -d %{buildroot}%{_datadir}/icons/hicolor/${sz}x${sz}/apps
done
install -m 0644 %{SOURCE10} %{buildroot}%{_datadir}/icons/hicolor/32x32/apps/mpf.png
install -m 0644 %{SOURCE11} %{buildroot}%{_datadir}/icons/hicolor/64x64/apps/mpf.png
install -m 0644 %{SOURCE12} %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/mpf.png
install -m 0644 %{SOURCE13} %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/mpf.png
install -m 0644 %{SOURCE14} %{buildroot}%{_datadir}/icons/hicolor/512x512/apps/mpf.png

# --- manpages ---
install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE4} %{buildroot}%{_mandir}/man1/mpf-check.1
install -m 0644 %{SOURCE5} %{buildroot}%{_mandir}/man1/mpf-cli.1
install -m 0644 %{SOURCE6} %{buildroot}%{_mandir}/man1/mpf-gui.1

# --- permissions framework profiles (one per subpackage, cap_sys_rawio on
#     the real binary; the capability lives on the " +capabilities" line) ---
install -d %{buildroot}%{_datadir}/permissions/permissions.d
cat > %{buildroot}%{_datadir}/permissions/permissions.d/mpf-check <<EOF
# MPF.Check optional --scan copy-protection path uses vendor SCSI commands.
%{_libdir}/mpf-check/MPF.Check root:root 0755
 +capabilities cap_sys_rawio=ep
EOF
cat > %{buildroot}%{_datadir}/permissions/permissions.d/mpf-cli <<EOF
# MPF.CLI drives vendor SCSI passthrough during dumps.
%{_libdir}/mpf-cli/MPF.CLI root:root 0755
 +capabilities cap_sys_rawio=ep
EOF
cat > %{buildroot}%{_datadir}/permissions/permissions.d/mpf-gui <<EOF
# MPF.Avalonia drives vendor SCSI passthrough during dumps.
%{_libdir}/mpf-gui/MPF.Avalonia root:root 0755
 +capabilities cap_sys_rawio=ep
EOF

# =====================================================================

%post check
%set_permissions %{_libdir}/mpf-check/MPF.Check

%verifyscript check
%verify_permissions -e %{_libdir}/mpf-check/MPF.Check

%post cli
%set_permissions %{_libdir}/mpf-cli/MPF.CLI

%verifyscript cli
%verify_permissions -e %{_libdir}/mpf-cli/MPF.CLI

%post gui
%set_permissions %{_libdir}/mpf-gui/MPF.Avalonia

%verifyscript gui
%verify_permissions -e %{_libdir}/mpf-gui/MPF.Avalonia

# =====================================================================

%files
# meta-package: no files, only Requires above

%files check
%{_bindir}/mpf-check
%attr(0755,root,root) %{_libdir}/mpf-check/MPF.Check
%dir %{_libdir}/mpf-check
%{_mandir}/man1/mpf-check.1*
%{_datadir}/permissions/permissions.d/mpf-check

%files cli
%{_bindir}/mpf-cli
%attr(0755,root,root) %{_libdir}/mpf-cli/MPF.CLI
%dir %{_libdir}/mpf-cli
%{_mandir}/man1/mpf-cli.1*
%{_datadir}/permissions/permissions.d/mpf-cli

%files gui
%{_bindir}/mpf-gui
%attr(0755,root,root) %{_libdir}/mpf-gui/MPF.Avalonia
%dir %{_libdir}/mpf-gui
%{_mandir}/man1/mpf-gui.1*
%{_datadir}/applications/mpf-gui.desktop
%{_datadir}/icons/hicolor/32x32/apps/mpf.png
%{_datadir}/icons/hicolor/64x64/apps/mpf.png
%{_datadir}/icons/hicolor/128x128/apps/mpf.png
%{_datadir}/icons/hicolor/256x256/apps/mpf.png
%{_datadir}/icons/hicolor/512x512/apps/mpf.png
%{_datadir}/permissions/permissions.d/mpf-gui

%changelog
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
