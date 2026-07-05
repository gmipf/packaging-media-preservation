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

The tools are **repackages of upstream prebuilt binaries** (the same artifacts
the RPM specs repackage), so the `.orig` tarball is assembled from the upstream
release ZIP/tarball rather than a source clone — `debian/rules` compiles
nothing, it only stamps the manpage. `discimagecreator` will be the exception
(source build) when it is added.

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

## Signed upload to Launchpad (needs account + GPG)

Not automated yet. Once the Launchpad account exists and a signing key is
registered there:

```sh
# in the mp-deb-builder container, on the assembled source tree:
debuild -S -sa -k<KEYID>      # signed *source* package
dput ppa:gmipf/media-preservation ../<tool>_<ver>_source.changes
```

A GitHub-Actions watcher (mirroring the `fedora/` watchers) will later rebuild
the `.orig` + bump the changelog on new upstream releases and push the signed
source upload, using a dedicated signing subkey stored as an Actions secret.
