# packaging-media-preservation

Distribution packaging recipes (specs, debian rules, PKGBUILDs, …) for the
[`gmipf/media-preservation`](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
COPR repository.

**This repo does *not* contain upstream tool source code** — only the recipes
needed to build the tools into distro packages. Upstream source lives at the
respective project URLs (see below).

## Tools

| Tool | Update mode | Fedora | Debian | Arch | Alpine |
|---|---|---|---|---|---|
| [redumper](https://github.com/superg/redumper) | manual bump on new upstream tags (binary repackage) | ✅ | — | — | — |
| [MPF suite](https://github.com/SabreTools/MPF) | rolling, auto-tracked every 6 h (binary repackage); meta-package `mpf` pulls in `mpf-check` (validator), `mpf-cli` (headless orchestrator) and `mpf-gui` (Avalonia desktop UI) | ✅ | — | — | — |
| [DiscImageCreator suite](https://github.com/saramibreak/DiscImageCreator) | auto-tracked daily on quarterly upstream tags (binary repackage); bundles DIC + EccEdc + DVDAuth + unscrambler in one RPM | ✅ | — | — | — |
| [Aaru](https://github.com/aaru-dps/Aaru) | manual bump on new alphas; CLI + Avalonia GUI ship as one binary, launch the GUI via `aaru gui` (binary repackage) | ✅ | — | — | — |

For the currently shipping versions and full install instructions,
see the [COPR project page](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/).

## Layout

```
.
├── .packit.yaml                            # Packit-as-a-Service config (drives Fedora COPR builds)
├── .github/workflows/
│   ├── watch-mpf-rolling.yml               # 6h watcher for MPF's rolling tag
│   └── watch-dic-releases.yml              # daily watcher for DiscImageCreator's user-attachment releases
├── LICENSE                                 # MIT (recipes only; tools keep their own licenses)
├── README.md
└── fedora/
    ├── redumper/
    │   ├── redumper.spec                   # repackage of upstream prebuilt linux-x64 ZIP
    │   └── redumper.1                      # handwritten manpage
    ├── mpf/
    │   ├── mpf.spec                        # multi-subpackage: mpf + mpf-check + mpf-cli + mpf-gui
    │   ├── mpf-gui.desktop                 # menu entry for `mpf-gui`
    │   ├── mpf-check.1 / mpf-cli.1 / mpf-gui.1  # handwritten manpages
    │   ├── mpf-{32,64,128,256,512}.png     # hicolor icons (from upstream Icon.ico)
    │   └── .rolling-sha                    # last seen upstream rolling SHA (written by watcher)
    ├── discimagecreator/
    │   ├── discimagecreator.spec           # repackage of upstream linux_amd64 tarball (bundles 4 binaries)
    │   ├── discimagecreator.1              # handwritten manpage
    │   └── .upstream-tag                   # last seen upstream tag (written by watcher)
    └── aaru/
        ├── aaru.spec                       # repackage of upstream .NET self-contained binary
        ├── aaru.desktop                    # menu entry for `aaru gui`
        └── aaru.1                          # handwritten manpage
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

Fedora builds are driven by [Packit](https://packit.dev/). Every commit that
touches a tool's `fedora/<tool>/` path triggers Packit to fetch sources, build
the SRPM, and ship a build to COPR project `gmipf/media-preservation`. No
manual `copr-cli build` needed.

Two of the four packages have GitHub-hosted watchers:

- **mpf** rolls — upstream force-pushes its `rolling` tag on every
  release. `watch-mpf-rolling.yml` polls every six hours, rewrites the
  spec's `%global mpfver` + `%global mpfsnap` lines and stores the new
  upstream SHA when something has changed. All three subpackages
  (mpf-check, mpf-cli, mpf-gui) ship synchronously since they share one
  upstream `<VersionPrefix>`.
- **discimagecreator** bumps quarterly. sarami links the Linux tarball
  inline in the release-body markdown instead of attaching it as a
  proper release asset, so `watch-dic-releases.yml` polls
  `releases/latest` daily, parses the body markdown to extract the
  user-attachment URL, and rewrites both `%global dicver` and the
  Source0 URL on a tag bump.

`redumper` and `aaru` are manually bumped on new upstream tags. redumper
uses Packit's `pull_from_upstream` job to auto-handle release events.

See `.packit.yaml` for the per-tool trigger configuration.

## Install (Fedora 43+)

```sh
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper discimagecreator aaru mpf
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
