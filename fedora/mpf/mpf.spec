%global mpfver         3.8.2
%global mpfsnap        20260702131742.1b3bfc0f
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
Release:        3%{?dist}
Summary:        Media Preservation Frontend suite (mpf-check, mpf-cli, mpf-gui)

License:        MIT
URL:            https://github.com/SabreTools/MPF

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
Requires:       krb5-libs
Requires:       libunwind
Requires:       openssl-libs
Requires:       zlib
Requires:       jq

%description check
MPF.Check reads the log files next to a finished optical-media dump and
writes a !submissionInfo.txt alongside in the Redump submission format.
Supported dump sources include Redumper, Aaru, DiscImageCreator, Cleanrip
and UmdImageCreator.

Optional copy-protection scanning is available via --path/--scan; that
path uses vendor SCSI commands and requires CAP_SYS_RAWIO, which is
preset on the shipped binary so no sudo is needed.

Self-contained .NET 10 binary, repackaged unmodified from the upstream
rolling release.

# ------------------------------------------------------------------ cli

%package cli
Summary:        Headless dump orchestrator (drives redumper, aaru, discimagecreator)
Requires:       libicu
Requires:       krb5-libs
Requires:       libunwind
Requires:       openssl-libs
Requires:       zlib
Requires:       jq
Recommends:     redumper
Recommends:     aaru5
Recommends:     discimagecreator

%description cli
MPF.CLI orchestrates the disc-dumping workflow from a terminal: it drives
the selected backend (redumper, aaru or discimagecreator) through the
dump, post-processes the output and writes the submission info.

CAP_SYS_RAWIO is preset on the shipped binary for vendor-SCSI access.

The bundled Programs/Creator/ folder from the upstream ZIP is dropped at
package build time in favor of the system-installed dumpers; mpf-cli
resolves the backend binary via PATH.

Self-contained .NET 10 binary, repackaged from the upstream rolling
release.

# ------------------------------------------------------------------ gui

%package gui
Summary:        Avalonia desktop frontend for the MPF disc-dumping workflow
Requires:       libicu
Requires:       krb5-libs
Requires:       libunwind
Requires:       openssl-libs
Requires:       zlib
Requires:       jq
Requires:       hicolor-icon-theme
Requires:       desktop-file-utils
Recommends:     redumper
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

CAP_SYS_RAWIO is preset on the shipped binary for vendor-SCSI access.

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
# dumper-path keys are always present and resolvable. We seed BARE tool
# names (aaru5, DiscImageCreator.out, redumper) rather than absolute
# paths: MPF (SabreTools/MPF#979) resolves a bare name through its
# runtime directory and $PATH, so the config stays valid no matter where
# the distro installs the dumpers and keeps working after the user
# deletes config.json. Upstream MPF otherwise defaults to relative bundle
# paths ("Programs/Creator/DiscImageCreator.out") that don't exist in a
# /usr-tree install.
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

# =====================================================================

%files
# meta-package: no files, only Requires above

%files check
%{_bindir}/mpf-check
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{_libdir}/mpf-check/MPF.Check
%dir %{_libdir}/mpf-check
%{_mandir}/man1/mpf-check.1*

%files cli
%{_bindir}/mpf-cli
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{_libdir}/mpf-cli/MPF.CLI
%dir %{_libdir}/mpf-cli
%{_mandir}/man1/mpf-cli.1*

%files gui
%{_bindir}/mpf-gui
%caps(cap_sys_rawio=ep) %attr(0755,root,root) %{_libdir}/mpf-gui/MPF.Avalonia
%dir %{_libdir}/mpf-gui
%{_mandir}/man1/mpf-gui.1*
%{_datadir}/applications/mpf-gui.desktop
%{_datadir}/icons/hicolor/32x32/apps/mpf.png
%{_datadir}/icons/hicolor/64x64/apps/mpf.png
%{_datadir}/icons/hicolor/128x128/apps/mpf.png
%{_datadir}/icons/hicolor/256x256/apps/mpf.png
%{_datadir}/icons/hicolor/512x512/apps/mpf.png

%changelog
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
