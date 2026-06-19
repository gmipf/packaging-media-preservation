%global debug_package %{nil}

Name:           redumper
Version:        725
Release:        3%{?dist}
Summary:        A low-level byte-perfect CD disc dumper

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP. The binary
# inside is a single statically linked ELF (clang + libc++ + -static),
# built by upstream's own CI matching the same toolchain we previously
# used for our source build.
Source0:        %{url}/releases/download/b%{version}/redumper-b%{version}-linux-x64.zip

# LICENSE + README aren't shipped in the release zip; fetched separately
# from the same tag so %%license / %%doc work without a full source clone.
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{version}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{version}/README.md

# Handwritten manpage (upstream provides none); pinned to b%%{version},
# see NOTES section inside the page for the drift caveat.
Source3:        redumper.1

ExclusiveArch:  x86_64
BuildRequires:  unzip

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray. It supports advanced Plextor features (negative lead-in, read
method D8) and Xbox/Xbox 360 (XGD) dumping via Kreon firmware drives.
Primarily used by the Redump and No-Intro preservation projects.

This RPM ships the binary with the cap_sys_rawio file capability so
vendor SCSI passthrough commands work without sudo.

%prep
%setup -q -c -T
unzip -q %{SOURCE0}

%build
# Self-contained statically linked binary; nothing to compile.

%install
install -d %{buildroot}%{_bindir}
install -m 0755 redumper-b%{version}-linux-x64/bin/redumper %{buildroot}%{_bindir}/redumper

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

install -d %{buildroot}%{_mandir}/man1
install -m 0644 %{SOURCE3} %{buildroot}%{_mandir}/man1/redumper.1

%files
%license LICENSE
%doc README.md
%caps(cap_sys_rawio=ep) %{_bindir}/redumper
%{_mandir}/man1/redumper.1*

%changelog
* Tue Jun 16 2026 gmipf <gmipf64@gmail.com> - 724-3
- Switch from source build to repackage of upstream prebuilt linux-x64
  release ZIP. The upstream binary is statically linked with the same
  clang + libc++ toolchain we used; the resulting RPM contents are
  effectively bit-identical to what users get from the GitHub release.
- Drops BuildRequires on cmake / ninja / clang / lld / libcxx-* /
  llvm-libunwind-static / glibc-static — none of these are needed in
  the chroot anymore. Build time per chroot drops from minutes to
  seconds and the spec is no longer exposed to upstream toolchain
  drift (no more googletest %prep patch, no more C++20-module
  surprises on clang bumps).
- LICENSE and README are pulled from raw.githubusercontent at the
  tagged revision so %license / %doc still work without the source
  tarball.

* Mon Jun 15 2026 gmipf <gmipf64@gmail.com> - 724-2
- Add handwritten redumper(1) manpage (upstream provides none); pinned
  to b724 — flagged stale-friendly in NOTES section if upstream syntax
  drifts before this manpage is updated

* Sun Jun 14 2026 gmipf <gmipf64@gmail.com> - 724-1
- Initial COPR build of redumper b724 for Fedora
- Source build from upstream tag b724 (GPL-3.0-only)
- Build matches upstream binary release: clang + libc++ + -static
- Single self-contained binary, no runtime libc++ dependency
- No debug subpackages (Release build, no symbols)
- Includes cap_sys_rawio file capability for vendor SCSI passthrough
- No sudo required for Plextor read method D8 and other vendor commands
