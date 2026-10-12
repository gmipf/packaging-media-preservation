%global debug_package %{nil}
# Ship upstream's binary byte for byte: no strip, no debuginfo, and none of the
# /usr/lib/.build-id links EL's rpm still makes without debuginfo (dead weight
# pointing at nothing; see redumper.spec for the collision they caused there).
%global __strip /bin/true
%global _build_id_links none

# The dreamdump release MPF bundles. MPF starts dreamdump itself (since July
# 2026) and pins one release in publish-nix.sh; it has moved
# that pin the same day dreamdump released, every time so far (0.4.0, 0.5.0,
# 0.6.0). So there is ONE package, under the plain name, and its version follows
# MPF's pin: .github/workflows/watch-consumer-pins.yml bumps this macro hourly.
# Should the two ever drift apart for good, this name becomes the rolling one
# and a dreamdump-mpf pin appears -- versions only go up, so nobody strands.
%global ddver 0.6.0

Name:           dreamdump
Version:        %{ddver}
Release:        2%{?dist}
Summary:        Dump the high-density area of Sega Dreamcast GD-ROMs

License:        EPL-2.0
URL:            https://codeberg.org/MoriGM/dreamdump

# The source tarball comes FIRST: the Debian lane takes the first remote Source
# as its .orig tarball (scripts/obs/gen-deb.sh). It is not compiled -- dreamdump
# needs Go >= 1.26, which most of our targets lack -- but it is READ at %%build:
# for LICENSE/README/DRIVES.csv, for the manpage, and to check that the binaries
# below were built from exactly this commit (dreamdump-build.sh verify).
Source0:        %{url}/archive/%{ddver}.tar.gz#/dreamdump-%{ddver}.tar.gz
# Upstream's statically linked release binaries (CGO_ENABLED=0). Both arches are
# carried and the matching one picked per build arch: packit and OBS build ONE
# source package across every arch chroot, so an arch-conditional Source: would
# ship the x86 binary on aarch64. Same %%{ddver} => bumped in lockstep.
Source1:        %{url}/releases/download/%{ddver}/dreamdump-_linux_amd64
Source2:        %{url}/releases/download/%{ddver}/dreamdump-_linux_arm64
# Provenance + no-capability guard + manpage generator. One file, read by the
# openSUSE lane through its URL; the Debian lane carries a copy in debian/.
Source3:        dreamdump-build.sh

ExclusiveArch:  x86_64 aarch64

%description
dreamdump reads the high-density area of a Sega Dreamcast GD-ROM through raw
SCSI READ CD commands, checks each section by reading it repeatedly, and
writes the result as track files. MPF uses it as one of its dumping programs.

It needs a drive that can be made to read the high-density area; upstream's
record of tested drives is in the manual page and in DRIVES.csv. Other drives
are used with default settings and are untested.

No root, no group and no file capability is needed: every SCSI command
dreamdump sends (INQUIRY, SET CD SPEED, READ CD) is permitted to any user who
can open the drive, which systemd-logind grants to the user at the local seat.

This package follows the dreamdump release MPF bundles.

%prep
%setup -q -n dreamdump

%build
# Both binaries against the one source tarball: a re-uploaded asset of either
# arch fails every build, not just the build of its own arch.
sh %{SOURCE3} verify . %{SOURCE0} %{SOURCE1}
sh %{SOURCE3} verify . %{SOURCE0} %{SOURCE2}
sh %{SOURCE3} manpage . %{version} > dreamdump.1

%install
%ifarch aarch64
install -D -p -m 0755 %{SOURCE2} %{buildroot}%{_bindir}/dreamdump
%else
install -D -p -m 0755 %{SOURCE1} %{buildroot}%{_bindir}/dreamdump
%endif
install -D -p -m 0644 dreamdump.1 %{buildroot}%{_mandir}/man1/dreamdump.1

%check
# Run the binary just installed, on this builder's CPU: on aarch64 the only
# run of the arm64 binary before a user's (selftest in dreamdump-build.sh).
sh %{SOURCE3} selftest %{buildroot}%{_bindir}/dreamdump

%files
%license LICENSE
%doc README.md DRIVES.csv
%{_bindir}/dreamdump
%{_mandir}/man1/dreamdump.1*

%changelog
* Mon Oct 12 2026 gmipf <gmipf64@gmail.com> - 0.6.0-2
- %%check runs the packaged binary (dreamdump-build.sh selftest): on the
  aarch64 chroots the first execution of the arm64 binary before a user's.

* Mon Oct 12 2026 gmipf <gmipf64@gmail.com> - 0.6.0-1
- Initial package. Repackages upstream's static release binaries for x86_64
  and aarch64, at the dreamdump release MPF bundles (0.6.0).
- The build checks that both binaries carry the commit of the shipped source
  tarball (vcs.revision vs. the archive's pax header), and fails if the source
  sends a SCSI opcode outside INQUIRY / SET CD SPEED / READ CD: the package
  ships without cap_sys_rawio, measured as a plain user on 2026-10-12.
- dreamdump(1) is generated from the same source: commands and options from
  the code, the tested-drive table from DRIVES.csv. Upstream ships no manpage.
