# packaging-media-preservation

Distribution packaging recipes (specs, debian rules, PKGBUILDs, …) for the
[`gmipf/media-preservation`](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
COPR repository.

**This repo does *not* contain upstream tool source code** — only the recipes
needed to build the tools into distro packages. Upstream source lives at the
respective project URLs (see below).

## Tools

| Tool | Update mode | Fedora | EPEL | openSUSE | Debian | Arch | Alpine |
|---|---|---|---|---|---|---|---|
| [redumper](https://github.com/superg/redumper) | auto-tracked hourly on new `b<N>` tags (binary repackage) | ✅ | ✅ | ✅ | — | — | — |
| [MPF suite](https://github.com/SabreTools/MPF) | rolling, auto-tracked hourly (binary repackage); meta-package `mpf` pulls in `mpf-check` (validator), `mpf-cli` (headless orchestrator) and `mpf-gui` (Avalonia desktop UI) | ✅ | ✅ | ✅ | — | — | — |
| [DiscImageCreator suite](https://github.com/saramibreak/DiscImageCreator) | auto-tracked hourly on new master commits (built from source — upstream binary links against EOL OpenSSL 1.1); bundles DIC + EccEdc + DVDAuth + unscrambler in one RPM | ✅ | ✅ | ✅ | — | — | — |
| [Aaru](https://github.com/aaru-dps/Aaru) | auto-tracked hourly on new `v6.0.0-alpha.<N>` tags (binary repackage); CLI + Avalonia GUI ship as one binary, launch the GUI via `aaru gui` | ✅ | ✅ | ✅ | — | — | — |

For the currently shipping versions and full install instructions,
see the [COPR project page](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/).

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

Future distro additions follow the same `<distro>/<tool>/` pattern:

```
debian/<tool>/debian/         # debian/control, debian/rules, debian/changelog
arch/<tool>/PKGBUILD          # AUR
alpine/<tool>/APKBUILD        # Alpine
```

One repo, all distros. Each distro folder uses that distro's native tooling
conventions — no custom abstraction layer on top.

## Automation

Builds are driven by [Packit](https://packit.dev/). Every commit that
touches a tool's `fedora/<tool>/` path triggers Packit to fetch sources, build
the SRPM, and ship a build to COPR project `gmipf/media-preservation`. No
manual `copr-cli build` needed.

Each package is built for `fedora-all-x86_64`, `epel-all-x86_64` and openSUSE
(`opensuse-leap-15.6-x86_64` + `opensuse-tumbleweed-x86_64`) — x86_64 only,
since every spec is `ExclusiveArch: x86_64` and the repackaged tools have no
non-x86_64 upstream binaries. `epel-all` auto-tracks every active EPEL major
(8/9/10 today, 11+ automatically), and the EPEL builds run on the CentOS
Stream N + EPEL buildroot, so one `.elN` package covers RHEL, CentOS Stream,
AlmaLinux, Rocky and Oracle Linux N. openSUSE is a separate RPM family with its
own macros and package names (and no `-all` alias in Packit), so its versions
are pinned explicitly.

`discimagecreator` (the only source build) carries small spec patches so it
compiles everywhere: dropping upstream meson's `fs.copyfile` and renaming a
doc file with an `&` in its name for EL8/EL9's older toolchain (on EL8 it links
the vendor-maintained system openssl 1.1.1k), plus BuildRequiring Ninja under
its openSUSE name (`ninja` vs `ninja-build`) and adding a `<limits.h>` include
for GCC 15 (Tumbleweed). The self-contained .NET tools (`aaru`, `mpf`) map
their runtime dependency names on openSUSE under a `%if 0%{?suse_version}`
guard (`krb5-libs`→`krb5`, `openssl-libs`→`libopenssl3`, `zlib`→`libz1`,
`libunwind` by soname); `libicu` and `jq` are portable as-is.

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
  EOL OpenSSL 1.1 (no longer in default Fedora/Ubuntu/Debian/Arch
  repos), so we recompile against OpenSSL 3 ourselves until upstream
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

### openSUSE Leap 15.6 / Tumbleweed

openSUSE has no `dnf copr` plugin; add the COPR repo with `zypper` instead
(swap `opensuse-tumbleweed` for `opensuse-leap-15.6` on Leap):

```sh
sudo zypper addrepo \
  https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/repo/opensuse-tumbleweed/gmipf-media-preservation-opensuse-tumbleweed.repo
sudo zypper --gpg-auto-import-keys refresh
sudo zypper install redumper discimagecreator aaru mpf
```

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
