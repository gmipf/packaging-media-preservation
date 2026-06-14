Name:           redumper
Version:        724
Release:        1%{?dist}
Summary:        A low-level byte-perfect CD disc dumper

# Release build strips debug symbols anyway; auto-generated debuginfo
# and debugsource subpackages would be empty / fail.
%global debug_package %{nil}

License:        GPL-3.0-only
URL:            https://github.com/superg/redumper
Source0:        %{url}/archive/refs/tags/b%{version}.tar.gz#/%{name}-b%{version}.tar.gz

BuildRequires:  cmake >= 3.28
BuildRequires:  ninja-build
BuildRequires:  clang >= 18
BuildRequires:  lld
BuildRequires:  libcxx-devel
BuildRequires:  libcxx-static
BuildRequires:  libcxxabi-static
BuildRequires:  llvm-libunwind-static
BuildRequires:  glibc-static

%description
redumper is a low-level byte-perfect disc dumper for CD, DVD, HD-DVD and
Blu-ray. It supports advanced Plextor features (negative lead-in, read
method D8) and Xbox/Xbox 360 (XGD) dumping via Kreon firmware drives.
Primarily used by the Redump and No-Intro preservation projects.

This RPM ships the binary with the cap_sys_rawio file capability so
vendor SCSI passthrough commands work without sudo.

%prep
%autosetup -n %{name}-b%{version}

# Drop the tests subdir — its CMakeLists pulls googletest via FetchContent,
# which needs network access (off by default in COPR for reproducibility).
# Tests aren't packaged anyway.
sed -i '/^enable_testing()/d; /^add_subdirectory("tests")/d' CMakeLists.txt

%build
# Match upstream binary release: clang + libc++ + -static (single
# self-contained binary like the GitHub release ZIPs). -lunwind is
# explicit because libc++abi's static unwinder dep isn't auto-pulled
# under -static.
cmake -B BUILD -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=%{_prefix} \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_CXX_FLAGS="-stdlib=libc++" \
    -DCMAKE_EXE_LINKER_FLAGS="-stdlib=libc++ -lunwind" \
    -DREDUMPER_VERSION_BUILD=%{version}
cmake --build BUILD --config Release

%install
DESTDIR=%{buildroot} cmake --install BUILD

%files
%license LICENSE
%doc README.md
%caps(cap_sys_rawio=ep) %{_bindir}/redumper

%changelog
* Sun Jun 14 2026 gmipf <gmipf64@gmail.com> - 724-1
- Initial COPR build of redumper b724 for Fedora
- Source build from upstream tag b724 (GPL-3.0-only)
- Build matches upstream binary release: clang + libc++ + -static
- Single self-contained binary, no runtime libc++ dependency
- No debug subpackages (Release build, no symbols)
- Includes cap_sys_rawio file capability for vendor SCSI passthrough
- No sudo required for Plextor read method D8 and other vendor commands
