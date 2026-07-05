# Ubuntu packaging lane (Launchpad PPA)

Debian-format packaging for the media-preservation tools, published as an
**Ubuntu PPA** on [Launchpad](https://launchpad.net/). This is the Ubuntu/Debian
counterpart to the Fedora/EPEL `fedora/` lane (COPR) and the planned openSUSE
lane (OBS).

## How a Launchpad PPA build works

Unlike COPR (where we upload an SRPM), Launchpad builds the binaries itself:

1. **Locally** we build a signed **source package** (`.dsc` + `.orig.tar.*` +
   `.debian.tar.*` + `_source.changes`) and `dput` it to the PPA.
2. **Launchpad's build farm** compiles the `.deb` for each enabled series
   (noble, jammy) and architecture, then publishes them.

So no local binary build is strictly required to publish — but we still run a
local test build first (see below) to catch failures without the slow upload
round-trip.

## Layout

```
ubuntu/<tool>/
├── .upstream-tag          # last-seen upstream tag (watcher anchor, mirrors fedora/)
└── debian/
    ├── changelog          # base version <upstream>-1, distribution UNRELEASED;
    │                      #   deb-build.sh rewrites the top line to
    │                      #   <upstream>-1~<series>1 / <series> per build
    ├── control            # debhelper-compat 13; Architecture: amd64
    ├── copyright          # DEP-5 (upstream GPL-3.0-only, debian/* MIT)
    ├── rules              # dh; no compile — stamps the manpage, skips strip/dwz
    ├── <tool>.1.in        # handwritten manpage template (@TAG@/@DATE@ stamped at build)
    ├── <tool>.install     # bin/<tool> -> /usr/bin
    ├── <tool>.manpages    # installs the stamped manpage
    ├── <tool>.docs        # README + LICENSE
    ├── <tool>.postinst    # setcap cap_sys_rawio+ep (parity with the RPM %caps)
    ├── clean              # generated manpage
    └── source/format      # 3.0 (quilt)
```

Most tools are **repackages of upstream prebuilt binaries** (the same artifacts
the RPM specs repackage), so the `.orig` tarball is assembled from the upstream
release ZIP/tarball rather than a source clone — `debian/rules` compiles
nothing, it only stamps the manpage. `discimagecreator` is the exception: a real
source build (meson + three helper makefiles), so its `debian/rules` does
compile and `dh_strip`/`dh_dwz` run normally (a `-dbgsym` is produced).

## Local test build (the `mock` equivalent)

```sh
scripts/deb-build.sh redumper          # noble (default)
scripts/deb-build.sh redumper jammy    # 22.04
```

This builds a clean `mp-deb-builder:<series>` Podman image (Ubuntu of that
series + debhelper/devscripts/lintian), fetches the upstream release assets,
assembles the source package, runs `dpkg-buildpackage` (source + binary,
unsigned) and `lintian`. Artifacts land in `.deb-out/<tool>-<series>/`
(gitignored). Needs network, so run it outside the command sandbox.

Expected lintian tags for these repackages (inherent to shipping an upstream
prebuilt binary, not defects — and Launchpad does not gate uploads on lintian):
`source-is-missing` (the ELF in the orig tarball), `statically-linked-binary`
and `unstripped-binary-or-object`. These would block acceptance into the Debian
archive proper, but a personal PPA takes them — exactly parallel to the RPM lane
repackaging prebuilt binaries.

## Versioning

Base version in the committed changelog is `<upstream>-1` (e.g. `726-1`). Per
series the build appends `~<series>1`, so `726-1~noble1` and `726-1~jammy1`.
The `~` sorts *before* the plain version, and `jammy` < `noble` alphabetically,
so the per-series uploads never collide and always order sensibly — the same
tilde discipline the RPM lane uses.

## Signed upload to Launchpad

```sh
scripts/deb-upload.sh redumper noble             # build, sign, dput
scripts/deb-upload.sh redumper jammy --dry-run   # build + sign only, verify
```

This runs the same assembly as the test build, then `dpkg-buildpackage -S -sa`
(signed **source** package) and `dput` to `ppa:dreunion61/media-preservation`.
The dedicated passphrase-less packaging key is exported from the host
`~/.gnupg` to a private 0600 temp file, bind-mounted read-only into the
builder container and shredded on exit — the key never lives in the image or
the repo. Needs network + `~/.gnupg`, so run it outside the command sandbox.
Launchpad then builds the `.deb` for each series on its own farm.

A GitHub-Actions watcher (mirroring the `fedora/` watchers) will later rebuild
the `.orig` + bump the changelog on new upstream releases and push the signed
source upload, using the signing key stored as an Actions secret.

## Packaged tools

| Tool             | Kind                              | Notes |
|------------------|-----------------------------------|-------|
| redumper         | static binary                     | no shlib deps; stamped manpage |
| aaru5            | NativeAOT binary + sidecar `.so`  | `${shlibs:Depends}` from the ELF; static manpage; udev |
| aaru             | self-contained .NET (single-file) | two tarballs merged; manpage generated from `--help`; udev; icons/MIME/desktop |
| mpf              | self-contained .NET × 3           | `mpf` meta + `mpf-check`/`mpf-cli`/`mpf-gui`; generated `/usr/bin` wrappers |
| discimagecreator | **source build** (meson)          | four archive tarballs merged; `${shlibs:Depends}` from the ELF; helper makefiles; static manpage; udev |

`discimagecreator` is the only source build: like `fedora/discimagecreator` it
compiles the main dumper via meson against the system libarchive/OpenSSL/zlib
(so it links OpenSSL 3, sidestepping the EOL `libcrypto.so.1.1` the upstream
prebuilt Linux binary needs) plus three helper tools via their own makefiles.
Its `debian/rules` ports the RPM's `%prep` source fix-ups (they run at
binary-build time, keeping the source package quilt-patch-free).

### Self-contained .NET runtime dependencies

The self-contained .NET tools (`aaru`, `mpf`) load their runtime libraries by
`dlopen` at run time, so `dh_shlibdeps` cannot see them — they are declared by
hand (parity with the RPM `Requires`). The ICU runtime package carries its
soname in its *name* (`libicu74` on noble, `libicu70` on jammy), so it is
resolved per-series at build via a `${dep:icu}` substvar in
`override_dh_gencontrol` (from what `libicu-dev` pulled in); the others
(`libkrb5-3`, `libssl3`, `zlib1g`, `libunwind8`) have stable names. The shared
builder image carries the matching `-dev` packages so the prebuilt binary can
run at build time (for `aaru`'s `--help` manpage generation).
