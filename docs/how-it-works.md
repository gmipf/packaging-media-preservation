# How it works

Back to the [README](../README.md). Drive permissions have their own page:
[drive-access.md](drive-access.md).

## What each package tracks

- **redumper** repackages upstream's own builds and is auto-tracked hourly on new
  `b<N>` tags.
- **MPF** is repackaged and rolling, auto-tracked hourly. The meta-package `mpf`
  pulls in `mpf-check` (log validator), `mpf-cli` (headless dump orchestrator)
  and `mpf-gui` (Avalonia desktop frontend); install the subpackages singly if
  you only need part of it (`sudo dnf install mpf-check`, etc.). Launch the GUI
  via `mpf-gui` or the `MPF` desktop entry.
- **DiscImageCreator** is built from source (upstream's Linux binary links
  against EOL OpenSSL 1.1) at a pinned master commit, auto-tracked hourly. One
  package bundles DIC + EccEdc + DVDAuth + unscrambler; the three helpers are
  pinned to their master commits too and tracked by the same watcher.
- **Aaru** (`aaru`) is repackaged and auto-tracked hourly on new
  `v6.0.0-<alpha|beta|rc>.<N>` tags. CLI and Avalonia GUI ship as one binary;
  launch the GUI via `aaru gui` or the `Aaru` desktop entry.
- **Aaru 5.4.x** (`aaru5`) is the stable 5.4 CLI that MPF drives, repackaged; it
  installs as `/usr/bin/aaru5` alongside the rolling `aaru` v6. It is
  version-pinned: **watched hourly, bumped by hand on purpose** — the version MPF
  bundles is read without a major-version constraint, and the day it lists a 6.x
  the package named `aaru5` must not silently become Aaru 6 (that is a
  retirement, decided by hand), so the watcher fails loudly instead.
- **Redumper-GUI** is built from source (vendored crates) at release tags.
- **dreamdump** is repackaged and follows the release MPF bundles, auto-tracked
  hourly from MPF's `publish-nix.sh`. It dumps the high-density area of Sega
  Dreamcast GD-ROMs and is one of the four programs MPF starts itself.
- **`redumper-mpf` / `redumper-rgui`** are fixed-name pins with a moving version:
  the redumper build that MPF (`redumper-mpf`) and Redumper-GUI
  (`redumper-rgui`) bundle. `redumper-mpf` is auto-tracked hourly from MPF's
  `publish-nix.sh` and upgrades in place; `redumper-rgui` moves with the
  Redumper-GUI release. Install one only if you use that frontend — the rolling
  `redumper` is what you want otherwise. They coexist, each installing as
  `/usr/bin/<name>`.

`redumper`, `discimagecreator` and `dreamdump` are CLI-only.

## Automation

Builds are driven by [Packit](https://packit.dev/). A push to `main` builds
nothing: every package has its own trigger branch `build-<tool>`, and the
watcher that bumps a spec on `main` then pushes that branch, so Packit fetches
the sources, builds the SRPM and ships exactly that one package to COPR project
`gmipf/media-preservation`. A rebuild by hand goes through
`scripts/build-tool.sh <tool>`, which also makes sure the same version-release
is never published twice. No manual `copr-cli build` needed.

If a trigger gets lost on the way (a failed push, an outage on either side),
`copr-reconcile` notices: every six hours it compares each spec on `main` with
COPR and re-pushes the trigger of any version COPR never received. For OBS,
`obs-trigger` asks for every recipe to be re-read once a day, and
`obs-health` turns red when an OBS build fails or OBS still publishes a
version `main` moved past more than a day ago.

"Hourly" is the schedule, not a promise: GitHub starts scheduled workflows
late when it is busy, and here they have run about 6 hours apart, at most
11 (October 2026). A new upstream release usually arrives the same day.
`scripts/schedule-health.py`, which `scripts/status.sh` runs, names a workflow
whose schedule stopped firing altogether: red once its last scheduled run is
older than its planned interval plus a day.

The same per-tool watchers drive the OBS lane: on an upstream bump they advance
`ubuntu/<tool>/debian/changelog` and regenerate `opensuse/<tool>/{<tool>.dsc,
debian.tar.gz,_service}` in the same commit, then ask OBS to re-run its source
services. Nothing is uploaded — OBS fetches the recipe and the upstream archives
itself.

Each package is built for `fedora-all` and `epel-all` on **x86_64 and aarch64**.
Every spec is `ExclusiveArch: x86_64 aarch64`. The repackaged tools bundle *both*
upstream arch archives as separate `Source:` lines and pick the matching one in
`%prep` / `%install` via `%ifarch` — packit builds ONE SRPM that COPR then builds
on every arch chroot, so an arch-conditional `Source:` would bake a single arch's
binary into the SRPM and the aarch64 build would ship the x86 one. Both URLs share
the same version macro, so a watcher bump carries them in lockstep. The two
source-built tools (DiscImageCreator, Redumper-GUI) simply compile per arch.
`epel-all` auto-tracks every active EPEL major
(8/9/10 today, 11+ automatically), and the EPEL builds run on the CentOS
Stream N + EPEL buildroot, so one `.elN` package covers RHEL, CentOS Stream,
AlmaLinux, Rocky and Oracle Linux N.

openSUSE is built on the [openSUSE Build Service](https://build.opensuse.org/)
(OBS), not on COPR, from specs that keep the Fedora spec's
`%if 0%{?suse_version}` branches; the same OBS project builds Debian and Ubuntu.
(When this lane started in July 2026, COPR had no Leap 16.0 chroot.)

`discimagecreator`, built from source, carries small spec patches so it
compiles everywhere. For the older EL toolchains it drops upstream meson's
`fs.copyfile` (EPEL 9 ships meson 0.63) and renames a doc file with an `&` in
its name (rpm 4.16 does not quote it); both apply on every distribution and
leave the installed files alike (on EL8 it links the vendor-maintained system
openssl 1.1.1k). It also
keeps `%if 0%{?suse_version}` portability, which the openSUSE (OBS) lane builds on —
BuildRequiring Ninja under its openSUSE name (`ninja` vs `ninja-build`) — and
the self-contained .NET tools (`aaru`, `mpf`) map their runtime dependency names
under the same guard (`krb5-libs`→`krb5`, `openssl-libs`→`libopenssl3`,
`zlib`→`libz1`, `libunwind` by soname; `libicu` and `jq` are portable as-is).
These openSUSE branches are a verified no-op on Fedora/EL.

The four upstreams with a release scheme of their own each have a watcher that
rewrites the spec on a new release and lets Packit handle the rebuild:

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
  EccEdc, DVDAuth and unscrambler follow their own master commits the same
  way (since 2026-10-14; EccEdc's last release, 20240901, lacked two fixes
  master has). Their pins stand in both specs and `debian/rules`;
  `scripts/dic-helpers.sh` reads and writes all of them and `lint.sh` checks
  that they agree. A helper commit leaves the version alone and becomes a new
  build of it: Fedora `Release`, the Debian revision and the formula's
  `revision` count up.
  Built from source: the upstream Linux release binary links against
  EOL OpenSSL 1.1 (no longer in default Fedora / Ubuntu repos), so we
  recompile against OpenSSL 3 ourselves until upstream
  ([saramibreak/DiscImageCreator#321](https://github.com/saramibreak/DiscImageCreator/issues/321))
  migrates or static-links.
- **aaru** is on the v6.0.0 pre-release track; upstream publishes a new
  alpha, beta or rc tag every two to six weeks.
  `watch-aaru-releases.yml` polls hourly, picks the highest tag across the track
  (alpha < beta < rc, the same order rpm and dpkg give the versions derived from
  it) and rewrites `%global aaruprerel` on a bump. Moving within the track needs
  no review: only the tag changes. The workflow loud-fails on stable v6.0.0 or a
  v7+ major, which reshape the packaging instead of advancing it — `Version`
  loses its `~pre-release` tilde and the release assets lose their `-<prerel>`
  infix, so `Source0`/`Source1` stop resolving.

The pinned packages follow their consumers: `watch-consumer-pins.yml` tracks the
builds MPF bundles (`redumper-mpf`, `aaru5`, `dreamdump`), and
`watch-redumper-gui.yml` tracks Redumper-GUI releases together with its redumper
pin (`redumper-rgui`).

See `.packit.yaml` for the per-tool trigger configuration.

### macOS

The redumper and DiscImageCreator watchers rewrite the Homebrew formula in the
same commit as the other lanes (`scripts/brew-sync.py`, which takes every version
from the Fedora spec and downloads each new source for its checksum), then run
`homebrew.yml` on the result: install from source, `brew test` and `brew audit`
on macOS 26 (Apple Silicon) and macOS 15 (Intel). It also runs weekly, and
`scripts/lint.sh` fails whenever a formula names other sources than its spec.

### The texts

A recipe moves and the texts about it stay behind unless something asks. Two
checks do:

- **Every commit** that changes a recipe, `.packit.yaml` or a workflow also
  changes a text a reader sees (this page, the README, `CHANGELOG.md`, the lane
  READMEs, [`descriptions/`](descriptions/README.md)), or says why none needs it
  in a `Docs-unchanged:` trailer. `scripts/docs-gate.py` checks that in the
  `commit-msg` hook and again for every pushed commit in `check-repo.yml`, and
  names the texts that mention each package the commit touches.
- **The texts against the tree and the services** (`scripts/texts-check.py`):
  every package is named in each text of its lanes and every workflow in the
  table below (in `scripts/lint.sh`); the GitHub, COPR and OBS descriptions equal
  their copies in [`descriptions/`](descriptions/README.md), and every release
  and architecture COPR and OBS build for is named in `CHANGELOG.md` (on every
  push, and in `scripts/status.sh`).

## Build notes per lane

**Tumbleweed on ARM** comes from a second repository,
**`openSUSE_Tumbleweed_ARM`** — Factory's x86_64 and ARM ports are separate OBS
projects, and one repository cannot serve both.

**Redumper-GUI** needs rustc ≥ 1.92 (eframe/egui). Debian 13 clears the floor
through `trixie-backports` (rustc 1.94.1, which OBS builds against — the package's
`Build-Depends: rustc (>= 1.92)` pulls it), and Ubuntu 26.04 ships 1.93. Left out:
Ubuntu 22.04/24.04 (≤ 1.91) and Debian 12 (1.63, and its backports carry no
rustc).

**Enterprise Linux needs EPEL** at install time: `aaru` and `mpf-gui` need
`libunwind`, and enterprise Linux ships it in EPEL, not in BaseOS/AppStream.
Without EPEL those two are unresolvable and the `mpf` meta-package fails with
them (measured on AlmaLinux 9; the `epel-N` buildroot carries EPEL, which is why
the packages build regardless). The COPR `dnf` plugin itself lives in
`dnf-plugins-core` and is in the base repos. Fedora needs no extra repository.

**One `debian/` recipe serves every Ubuntu and Debian release.** An Ubuntu `.deb`
does not fit Debian, because the ICU runtime carries its soname in the package
name (`libicu70` on jammy vs `libicu72` on bookworm), so the dependency is
resolved from the build root at build time rather than from a table of series.

**macOS:** redumper is upstream's own macOS build, repackaged; DiscImageCreator is
built from source at the same commit as the Linux packages (upstream publishes no
macOS build, and the one MPF bundles is linked against MacPorts). On Intel Macs
Homebrew no longer builds bottles (Tier 3 since September 2026), so dependencies
compile from source. DiscImageCreator builds with its own makefile: besides
libarchive and openssl@3 (and what they depend on) it needs only pkgconf -- not
meson, whose Python pulls in openssl@4 (that build failed on an Intel Mac in
October 2026). Not available on macOS: Aaru (its device layer does not support
macOS), dreamdump (Linux and Windows only), and floppy dumping (no tool reaches a
floppy there). MPF may follow.

## Layout

```
.
├── .packit.yaml            # Packit config: one COPR build job per package (Fedora / EPEL)
├── .github/workflows/      # watchers, OBS and COPR safety nets, Homebrew CI, repo checks
├── .githooks/              # pre-commit: proof ledger + lint; commit-msg: the docs gate
├── Formula/                # Homebrew tap (redumper, discimagecreator)
├── fedora/<tool>/          # RPM spec + what it ships besides upstream's files
├── ubuntu/<tool>/debian/   # Debian-format recipe, for Debian AND Ubuntu
├── opensuse/<tool>/        # OBS lane: openSUSE spec + generated .dsc, debian.tar.gz, _service
├── scripts/                # build trigger, generators, linters, health checks and their tests
├── proofs/                 # drive-access measurements the proof ledger points to
├── docs/                   # this page, drive-access.md, descriptions/ (the GitHub, COPR and OBS texts)
├── CHANGELOG.md            # packages, distributions and architectures added or dropped, by date
└── LICENSE                 # MIT (recipes only; tools keep their own licenses)
```

`fedora/<tool>/` holds the spec and what it ships besides upstream's files:
handwritten or generated manpages, desktop entries and icons for the GUIs, udev
rules for floppy access, and the watcher's record of the last upstream release
it saw (`.upstream-tag`, `.rolling-sha`).

The workflows in `.github/workflows/`:

| workflow | what it does |
|---|---|
| `watch-redumper-releases.yml` | hourly watcher for redumper's `b<N>` tags |
| `watch-mpf-rolling.yml` | hourly watcher for MPF's rolling tag |
| `watch-dic-releases.yml` | hourly watcher for DiscImageCreator master commits and its three helpers |
| `watch-aaru-releases.yml` | hourly watcher for Aaru's v6.0.0 pre-release tags |
| `watch-redumper-gui.yml` | hourly watcher for Redumper-GUI releases and its redumper pin |
| `watch-consumer-pins.yml` | follows the builds MPF bundles (`redumper-mpf`, `aaru5`, `dreamdump`) |
| `watch-distro-lifecycle.yml` | reports distro releases that OBS does not build for yet |
| `obs-trigger.yml` | asks OBS to re-read the recipes (after every bump, and daily) |
| `copr-reconcile.yml` | re-pushes a COPR trigger that got lost (every six hours) |
| `obs-health.yml` | red when an OBS build fails or OBS falls behind `main` (every six hours) |
| `homebrew.yml` | builds and tests every formula on Apple Silicon and Intel |
| `check-repo.yml` | repository checks (lint, proof ledger, Rust floor, the docs gate, the live texts, ...) |

The Debian-format recipes live in `ubuntu/` — see [`ubuntu/README.md`](../ubuntu/README.md).
One recipe serves Debian AND Ubuntu; the directory name predates the Debian targets:

```
ubuntu/<tool>/debian/         # debian/control, debian/rules, debian/changelog
```

`opensuse/<tool>/` is the OBS lane, and it delivers openSUSE, Debian **and**
Ubuntu:

```
opensuse/<tool>/
├── <tool>.spec               # reuses the Fedora spec's %if 0%{?suse_version} branches
├── <tool>.dsc                # debtransform template   ┐
├── debian.tar.gz             # debian/ minus changelog ├─ generated: scripts/obs/gen-deb.sh
└── _service                  # tells OBS what to fetch ┘
```

The `.deb` side reuses `ubuntu/<tool>/debian/` unchanged — there is no second
recipe. OBS assembles the Debian source package at build time from the `.dsc`,
and fetches every input itself, so git stays the single source of truth for both
halves. The three generated files are checked against the recipe by
`scripts/status.sh`: drift between them does not fail a build, it corrupts one
silently.

**No `.orig` tarball is assembled anywhere, and nothing is re-hosted.** A Debian
source package takes one orig tarball and the build root has no network, which
looks like it forces someone to pre-assemble and host a merged archive. It does
not: `DEBTRANSFORM-TAR` names the first upstream archive and `DEBTRANSFORM-FILES`
the rest — the `.dsc`'s answer to an RPM spec's `Source1:`/`Source2:` — and
`debian/rules` unpacks them in the build root exactly as `%prep` does (aaru's
source tarball, mpf's CLI and GUI zips, dic's three sibling projects). OBS has
already downloaded those files for the RPM, so the `.rpm` and the `.deb` are built
from the same upstream bytes, fetched once.

`scripts/obs/test-deb.sh <image> <tool>` replays that chain locally before a push
— including `dpkg-buildpackage` **without** `-b`, which is what OBS runs. A gate
milder than the build farm is not a gate.

Each distro folder uses that distro's native tooling conventions — no custom
abstraction layer on top.

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
