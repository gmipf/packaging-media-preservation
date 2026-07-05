# packaging-media-preservation

Distribution packaging recipes (RPM specs, Debian rules) for the
media-preservation tools, published to the
[`gmipf/media-preservation`](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
COPR repository (Fedora / EPEL) and the
[`ppa:dreunion61/media-preservation`](https://launchpad.net/~dreunion61/+archive/ubuntu/media-preservation)
Launchpad PPA (Ubuntu).

**This repo does *not* contain upstream tool source code** — only the recipes
needed to build the tools into distro packages. Upstream source lives at the
respective project URLs (see below).

## Tools

| Tool | Update mode | [Fedora][copr] | [EPEL][copr] | [Ubuntu][ppa] | openSUSE |
|---|---|---|---|---|---|
| [redumper](https://github.com/superg/redumper) | auto-tracked hourly on new `b<N>` tags (binary repackage) | ✅ | ✅ | ✅ | — |
| [MPF suite](https://github.com/SabreTools/MPF) | rolling, auto-tracked hourly (binary repackage); meta-package `mpf` pulls in `mpf-check` (validator), `mpf-cli` (headless orchestrator) and `mpf-gui` (Avalonia desktop UI) | ✅ | ✅ | ✅ | — |
| [DiscImageCreator suite](https://github.com/saramibreak/DiscImageCreator) | auto-tracked hourly on new master commits (built from source — upstream binary links against EOL OpenSSL 1.1); bundles DIC + EccEdc + DVDAuth + unscrambler in one package | ✅ | ✅ | ✅ | — |
| [Aaru](https://github.com/aaru-dps/Aaru) | auto-tracked hourly on new `v6.0.0-alpha.<N>` tags (binary repackage); CLI + Avalonia GUI ship as one binary, launch the GUI via `aaru gui` | ✅ | ✅ | ✅ | — |

[copr]: https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/
[ppa]: https://launchpad.net/~dreunion61/+archive/ubuntu/media-preservation

The **Fedora** / **EPEL** column headers link to the COPR project and **Ubuntu**
to the Launchpad PPA; the openSUSE (OBS) lane is planned. For the currently
shipping versions and full install instructions, see those pages.

## Layout

```
.
├── .packit.yaml                            # Packit-as-a-Service config (drives Fedora COPR builds)
├── .github/workflows/
│   ├── watch-redumper-releases.yml         # hourly watcher for redumper's b<N> tags
│   ├── watch-mpf-rolling.yml               # hourly watcher for MPF's rolling tag
│   ├── watch-dic-releases.yml              # hourly watcher for DiscImageCreator master commits
│   └── watch-aaru-releases.yml             # hourly watcher for Aaru's v6.0.0-alpha.<N> tags
├── LICENSE                                 # MIT (recipes only; tools keep their own licenses)
├── README.md
└── fedora/
    ├── redumper/
    │   ├── redumper.spec                   # repackage of upstream prebuilt linux-x64 ZIP
    │   ├── redumper.1                      # handwritten manpage
    │   └── .upstream-tag                   # last seen upstream tag (written by watcher)
    ├── mpf/
    │   ├── mpf.spec                        # multi-subpackage: mpf + mpf-check + mpf-cli + mpf-gui
    │   ├── mpf-gui.desktop                 # menu entry for `mpf-gui`
    │   ├── mpf-check.1 / mpf-cli.1 / mpf-gui.1  # handwritten manpages
    │   ├── mpf-{32,64,128,256,512}.png     # hicolor icons (from upstream Icon.ico)
    │   └── .rolling-sha                    # last seen upstream rolling SHA (written by watcher)
    ├── discimagecreator/
    │   ├── discimagecreator.spec           # source-build of DIC + EccEdc + DVDAuth + unscrambler
    │   ├── discimagecreator.1              # handwritten manpage
    │   └── .upstream-tag                   # last seen upstream tag (written by watcher)
    └── aaru/
        ├── aaru.spec                       # repackage of upstream .NET self-contained binary
        ├── aaru.desktop                    # menu entry for `aaru gui`
        ├── aaru.1                          # handwritten manpage
        └── .upstream-tag                   # last seen upstream tag (written by watcher)
```

The Ubuntu lane (Launchpad PPA) is live — see [`ubuntu/README.md`](ubuntu/README.md):

```
ubuntu/<tool>/debian/         # debian/control, debian/rules, debian/changelog (Launchpad PPA)
```

An openSUSE (OBS) lane is planned and will reuse the specs' `%if 0%{?suse_version}`
branches. Each distro folder uses that distro's native tooling conventions —
no custom abstraction layer on top.

## Automation

Builds are driven by [Packit](https://packit.dev/). Every commit that
touches a tool's `fedora/<tool>/` path triggers Packit to fetch sources, build
the SRPM, and ship a build to COPR project `gmipf/media-preservation`. No
manual `copr-cli build` needed.

The same per-tool watchers also drive the Ubuntu PPA: on an upstream bump they
advance `ubuntu/<tool>/debian/changelog` in the same commit, then build and
`dput` the signed source package (noble + jammy) to the Launchpad PPA, which
compiles the `.deb`s on its own build farm. See
[`ubuntu/README.md`](ubuntu/README.md).

Each package is built for `fedora-all-x86_64` and `epel-all-x86_64` — x86_64
only, since every spec is `ExclusiveArch: x86_64` and the repackaged tools have
no non-x86_64 upstream binaries. `epel-all` auto-tracks every active EPEL major
(8/9/10 today, 11+ automatically), and the EPEL builds run on the CentOS
Stream N + EPEL buildroot, so one `.elN` package covers RHEL, CentOS Stream,
AlmaLinux, Rocky and Oracle Linux N.

openSUSE is **not** built on COPR: COPR only offers an EOL Leap 15.6 and a
currently-broken Tumbleweed and has no Leap 16.0 chroot, so openSUSE will be
published natively on the [openSUSE Build Service](https://build.opensuse.org/)
(OBS) instead. The specs keep their `%if 0%{?suse_version}` portability for that
future port.

`discimagecreator` (the only source build) carries small spec patches so it
compiles everywhere: for the EL8/EL9 EPEL builds it drops upstream meson's
`fs.copyfile` and renames a doc file with an `&` in its name for the older
toolchain (on EL8 it links the vendor-maintained system openssl 1.1.1k). It also
keeps `%if 0%{?suse_version}` portability for the planned openSUSE (OBS) port —
BuildRequiring Ninja under its openSUSE name (`ninja` vs `ninja-build`) and a
`<limits.h>` include for GCC 15 — and the self-contained .NET tools (`aaru`,
`mpf`) map their runtime dependency names under the same guard
(`krb5-libs`→`krb5`, `openssl-libs`→`libopenssl3`, `zlib`→`libz1`, `libunwind`
by soname; `libicu` and `jq` are portable as-is). These openSUSE branches are a
verified no-op on Fedora/EL.

All four packages have GitHub-hosted watchers that rewrite their spec on
upstream releases and let Packit handle the rebuild:

- **redumper** publishes new `b<N>` release tags frequently (multiple
  per day during active bursts; quieter weeks otherwise).
  `watch-redumper-releases.yml` polls hourly, picks the highest `b<N>`
  tag from the 20 most recent releases and rewrites the spec's
  `Version:` line. Older `build_<N>` tags from the pre-convention era
  are ignored by the filter.
- **mpf** rolls — upstream force-pushes its `rolling` tag on every
  release. `watch-mpf-rolling.yml` polls hourly, rewrites the
  spec's `%global mpfver` + `%global mpfsnap` lines and stores the new
  upstream SHA when something has changed. All three subpackages
  (mpf-check, mpf-cli, mpf-gui) ship synchronously since they share one
  upstream `<VersionPrefix>`.
- **discimagecreator** is packaged from a pinned master commit rather
  than the release tag: master carries the accumulated Linux fixes --
  notably the fd (floppy) SIGSEGV fix (#328) -- that the last release tag
  (20260101) lacks. `watch-dic-releases.yml` polls master HEAD hourly and,
  on a new commit, re-pins `%global diccommit` / `%global dicsnap` to that
  SHA. DIC has no semantic source version -- its AppVersion is a build-time
  timestamp and the release tags are bare `YYYYMMDD` date labels -- so the
  package version is simply the commit's UTC timestamp plus short SHA
  (`<YYYYMMDDHHMMSS>.<short-SHA>`): monotonic, pinned, no release-tag anchor.
  Built from source: the upstream Linux release binary links against
  EOL OpenSSL 1.1 (no longer in default Fedora / Ubuntu repos), so we
  recompile against OpenSSL 3 ourselves until upstream
  ([saramibreak/DiscImageCreator#321](https://github.com/saramibreak/DiscImageCreator/issues/321))
  migrates or static-links.
- **aaru** is on the v6.0.0 alpha track; upstream publishes a new
  `v6.0.0-alpha.<N>` tag every two to six weeks. `watch-aaru-releases.yml`
  polls hourly, picks the highest numeric `alpha.<N>[.<M>]` tag and
  rewrites `%global aaruprerel` on a bump. The workflow loud-fails if
  upstream transitions to stable v6.0.0, a beta/rc, or a v7+ major —
  the spec's tilde-versioning would need manual revision.

See `.packit.yaml` for the per-tool trigger configuration.

## Install

### Fedora 43+ and RHEL / CentOS Stream / AlmaLinux / Rocky / Oracle 8–10

```sh
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper discimagecreator aaru mpf
```

On enterprise-Linux clones the COPR `dnf` plugin lives in `dnf-plugins-core`
(shipped in the base repos), and these packages' runtime dependencies are all
in the base/AppStream repos — so EPEL does **not** need to be enabled to
install them.

### Ubuntu 24.04 (noble) and 22.04 (jammy)

```sh
sudo add-apt-repository ppa:dreunion61/media-preservation
sudo apt update
sudo apt install redumper discimagecreator aaru mpf
```

See [`ubuntu/README.md`](ubuntu/README.md) for how the PPA source packages are
built and signed.

### openSUSE (planned, not yet available)

openSUSE is not built on COPR: its openSUSE support is limited to an EOL Leap
15.6 and a currently-broken Tumbleweed, with no Leap 16.0 chroot, so openSUSE
will be published natively on the
[openSUSE Build Service](https://build.opensuse.org/) (OBS) instead — planned,
not yet available.

`mpf` is a meta-package; it pulls in `mpf-check` (log validator),
`mpf-cli` (headless dump orchestrator) and `mpf-gui` (Avalonia desktop
frontend). Install the individual subpackages if you only need part of
the suite (`sudo dnf install mpf-check`, etc.). Launch the GUI via
`mpf-gui` or the `MPF` desktop entry.

`aaru` ships both the CLI and its Avalonia GUI in one binary — launch
the GUI via `aaru gui` or via the `Aaru` desktop entry. `redumper` and
`discimagecreator` are CLI-only.

`cap_sys_rawio` is preset on the dumper binaries (redumper, discimagecreator,
aaru, mpf-check, mpf-cli, mpf-gui) so vendor SCSI passthrough commands work
without sudo. Drive-node access (`/dev/sr*`) is granted automatically via
`uaccess` when logged in at a local desktop seat; for headless / SSH use add
yourself to the `cdrom` group. See the
[COPR project page](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
for details.

## Versioning convention

All RPMs in this repo follow one convention:

- **Stable upstream tags**: bare Version + simple Release-N
  (e.g. `<name>-<upstream-tag>-N`)
- **Pre-releases / rolling snapshots**: `<base>~<extra>` Version + bare-N Release
  (e.g. `<name>-<upstream-base>~<pre-release-or-snapshot>-N`)
- **Iteration counter** (`-1`, `-2`, …) is always the last NEVRA segment
- **Epoch** stays at 0 (implicit) across the board — no `1:` prefix on any package

The tilde sorts before any other character in RPM version comparison, so
pre-releases automatically rank below stable bumps without needing any
clever `0.<N>.alpha.<M>` Release tricks.

## Status

Unsupported third-party recipes. Personal hobby project, not affiliated with
the Fedora Project, Redump, No-Intro, or any upstream tool author.
