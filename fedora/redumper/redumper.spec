%global debug_package %{nil}
# ...and with debuginfo off, the /usr/lib/.build-id/ links rpm still makes on EL
# point at debuginfo that does not exist. Worse, they COLLIDE: `redumper` and
# `redumper<N>` ship the same upstream binary whenever the rolling build equals a
# pinned one, so both claim the same build-id path and stop being co-installable.
# Measured 2026-07-16 on EL10 with rolling == 732: `dnf install redumper mpf-cli`
# (mpf recommends redumper732) died on "/usr/lib/.build-id/db/ea49...ce
# kollidiert". EL ONLY -- Fedora's rpm drops the links together with
# debug_package, EL's does not, which is exactly why building and testing on
# Fedora never showed it. aaru/aaru5/mpf already set this; these did not.
%global _build_id_links none

Name:           redumper
Version:        742
Release:        1%{?dist}
Summary:        A low-level byte-perfect CD disc dumper

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper

# Repackage of the upstream prebuilt linux-x64 release ZIP. The binary
# inside is a single statically linked ELF (clang + libc++ + -static),
# built by upstream's own CI matching the same toolchain we previously
# used for our source build.
Source0:        %{url}/releases/download/b%{version}/redumper-b%{version}-linux-x64.zip

# arm64 counterpart of Source0. We bundle BOTH arch ZIPs into the one SRPM
# because packit builds a single SRPM that COPR/OBS then build across every
# arch chroot; an arch-conditional Source: would bake one arch's binary into
# the SRPM, so the aarch64 build would ship the x86 binary. We carry both and
# select in %%install via %%ifarch. Same %%{version} macro => the watcher bumps
# both URLs in lockstep on every upstream release.
Source4:        %{url}/releases/download/b%{version}/redumper-b%{version}-linux-arm64.zip

# LICENSE + README aren't shipped in the release zip; fetched separately
# from the same tag so %%license / %%doc work without a full source clone.
Source1:        https://raw.githubusercontent.com/superg/redumper/b%{version}/LICENSE
Source2:        https://raw.githubusercontent.com/superg/redumper/b%{version}/README.md

# Handwritten manpage (upstream provides none), installed VERBATIM. It carries a
# FIXED version marker naming the build its prose was written against (b724) --
# it is deliberately NOT stamped with %%{version}. Stamping the shipped release
# into a hand-written page is a forgery: the header would keep claiming currency
# release after release while the prose quietly aged, and the page even admitted
# as much two paragraphs further down. A fixed marker lets the reader see that
# their binary is newer than the text. (Generated pages are the opposite case --
# there content and version move together, so stamping is honest; that is why
# aaru's generated page stamps and this one does not.)
#
# We also deliberately do NOT use help2man: redumper's --help is a bare option
# dump, while this page carries curated Linux drive-access / device-node /
# examples guidance that help2man would strip out.
Source3:        redumper.1

ExclusiveArch:  x86_64 aarch64
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
%ifarch aarch64
unzip -q %{SOURCE4}
%else
unzip -q %{SOURCE0}
%endif

%build
# Self-contained statically linked binary; nothing to compile, and the manpage
# is installed verbatim (see Source3) rather than stamped.

%install
install -d %{buildroot}%{_bindir}
%ifarch aarch64
install -m 0755 redumper-b%{version}-linux-arm64/bin/redumper %{buildroot}%{_bindir}/redumper
%else
install -m 0755 redumper-b%{version}-linux-x64/bin/redumper %{buildroot}%{_bindir}/redumper
%endif

install -p -m 0644 %{SOURCE1} LICENSE
install -p -m 0644 %{SOURCE2} README.md

install -D -m 0644 %{SOURCE3} %{buildroot}%{_mandir}/man1/redumper.1

%files
%license LICENSE
%doc README.md
%caps(cap_sys_rawio=ep) %{_bindir}/redumper
%{_mandir}/man1/redumper.1*

%changelog
* Tue Aug 11 2026 gmipf <gmipf64@gmail.com> - 742-1
- Automated sync to upstream redumper release b742; Release reset to 1.

* Fri Aug 07 2026 gmipf <gmipf64@gmail.com> - 741-1
- Automated sync to upstream redumper release b741; Release reset to 1.

* Tue Aug 04 2026 gmipf <gmipf64@gmail.com> - 740-1
- Automated sync to upstream redumper release b740; Release reset to 1.

* Fri Jul 31 2026 gmipf <gmipf64@gmail.com> - 739-1
- Automated sync to upstream redumper release b739; Release reset to 1.

* Thu Jul 30 2026 gmipf <gmipf64@gmail.com> - 737-1
- Automated sync to upstream redumper release b737; Release reset to 1.

* Mon Jul 27 2026 gmipf <gmipf64@gmail.com> - 736-1
- Automated sync to upstream redumper release b736; Release reset to 1.

* Fri Jul 24 2026 gmipf <gmipf64@gmail.com> - 735-1
- Automated sync to upstream redumper release b735; Release reset to 1.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 734-1
- Automated sync to upstream redumper release b734; Release reset to 1.

* Sat Jul 18 2026 gmipf <gmipf64@gmail.com> - 733-2
- Add aarch64 (arm64) support. Bundle the upstream linux-arm64 release ZIP
  alongside linux-x64 (both carry the same %%{version} macro, so watchers bump
  them in lockstep) and pick the matching binary per build arch via %%ifarch.
  ExclusiveArch is now x86_64 aarch64. Rationale: packit builds ONE SRPM that
  COPR/OBS build across every arch chroot, so an arch-conditional Source: would
  bake one arch's binary into the SRPM; bundling both and selecting at %%install
  is the only correct way. arm64 ships UNTESTED -- no hardware drive-access
  proof exists for it; the repackaging path is architecture-neutral but this is
  deliberately not claimed as proven.

* Fri Jul 17 2026 gmipf <gmipf64@gmail.com> - 733-1
- Automated sync to upstream redumper release b733; Release reset to 1.

* Thu Jul 16 2026 gmipf <gmipf64@gmail.com> - 732-2
- Set %%global _build_id_links none. With debug_package off these links point at
  debuginfo that does not exist -- and on EL they made this package collide with
  the redumper732 pin: both ship the same upstream binary, so both claimed
  /usr/lib/.build-id/db/ea49...ce and `dnf install redumper mpf-cli` (mpf
  recommends redumper732) failed the transaction test. Fedora's rpm drops the
  links together with debug_package, EL's does not -- which is why building and
  testing on Fedora never showed it. Measured on CentOS Stream 10, 2026-07-16.

* Sun Jul 12 2026 gmipf <gmipf64@gmail.com> - 732-1
- Automated sync to upstream redumper release b732; Release reset to 1.
- Stop stamping the shipped release into the handwritten redumper(1) manpage.
  The .TH header now carries a FIXED marker naming the build the prose was
  actually written against (b724); the page is installed verbatim.
- This reverts the mechanism added in 726-2, which was backwards. The prose is
  maintained by hand and does not move when the package does, so stamping
  %%{version} into the header made every build claim the page documented the
  binary it shipped with -- while the page's own NOTES section admitted, two
  paragraphs down, that it might be stale. A header that always names the
  current build cannot show staleness; a fixed marker can, and now does.
- The rule this settles: a HANDWRITTEN page gets a fixed marker (which version
  the text describes), a GENERATED page gets the shipped version stamped in
  (content and version move together there, so it is honest). aaru's page is
  generated at build time from --help and keeps stamping.

* Sat Jul 11 2026 gmipf <gmipf64@gmail.com> - 731-1
- Automated sync to upstream redumper release b731; Release reset to 1.

* Fri Jul 10 2026 gmipf <gmipf64@gmail.com> - 730-1
- Automated sync to upstream redumper release b730; Release reset to 1.

* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 729-1
- Automated sync to upstream redumper release b729; Release reset to 1.

* Sun Jul 05 2026 gmipf <gmipf64@gmail.com> - 727-1
- Automated sync to upstream redumper release b727; Release reset to 1.

* Wed Jun 24 2026 gmipf <gmipf64@gmail.com> - 726-2
- Stamp the upstream tag and build date into the handwritten redumper(1)
  manpage at build time (%%build sed on %%{version}), so its header always
  matches the shipped binary instead of carrying a hand-maintained tag that
  drifts. Deliberately not help2man: the curated Linux drive-access and
  examples content is richer than the binary's bare --help output.

* Sun Jun 21 2026 gmipf <gmipf64@gmail.com> - 726-1
- Automated sync to upstream redumper release b726; Release reset to 1.

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
