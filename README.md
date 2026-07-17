# packaging-media-preservation

Distribution packaging recipes (RPM specs, Debian rules) for the
media-preservation tools, published to the
[`gmipf/media-preservation`](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
COPR repository (Fedora / EPEL) and the
[`home:gmipf:media-preservation`](https://build.opensuse.org/project/show/home:gmipf:media-preservation)
OBS project (openSUSE, Debian, Ubuntu).

**Every lane builds straight from upstream.** Neither depends on the other, and
neither re-hosts anyone's bytes: an RPM spec names its `Source0:`/`Source1:` URLs
and assembles the tree in `%prep`; the `.dsc` names the very same URLs
(`DEBTRANSFORM-TAR` + `DEBTRANSFORM-FILES`) and `debian/rules` does the same work.

**This repo does *not* contain upstream tool source code** — only the recipes
needed to build the tools into distro packages. Upstream source lives at the
respective project URLs (see below).

## Tools

| Tool | Update mode | [Fedora][copr] | [EPEL][copr] | [openSUSE][obs] | [Ubuntu][obs] | [Debian][obs] |
|---|---|---|---|---|---|---|
| [redumper](https://github.com/superg/redumper) | auto-tracked hourly on new `b<N>` tags (binary repackage) | ✅ | ✅ | ✅ | ✅ | ✅ |
| [MPF](https://github.com/SabreTools/MPF) | rolling, auto-tracked hourly (binary repackage); meta-package `mpf` pulls in `mpf-check` (validator), `mpf-cli` (headless orchestrator) and `mpf-gui` (Avalonia desktop UI) | ✅ | ✅ | ✅ | ✅ | ✅ |
| [DiscImageCreator](https://github.com/saramibreak/DiscImageCreator) | auto-tracked hourly on new master commits (built from source — upstream binary links against EOL OpenSSL 1.1); bundles DIC + EccEdc + DVDAuth + unscrambler in one package | ✅ | ✅ | ✅ | ✅ | ✅ |
| [Aaru](https://github.com/aaru-dps/Aaru) | auto-tracked hourly on new `v6.0.0-<alpha|beta|rc>.<N>` tags (binary repackage; beta since 2026-07-16); CLI + Avalonia GUI ship as one binary, launch the GUI via `aaru gui` | ✅ | ✅ | ✅ | ✅ | ✅ |
| [Aaru 5.4.x](https://github.com/aaru-dps/Aaru) (`aaru5`) | version-pinned, no auto-tracking (binary repackage); the stable 5.4 CLI that MPF drives, installs as `/usr/bin/aaru5` alongside the rolling `aaru` v6 | ✅ | ✅ | ✅ | ✅ | ✅ |
| [Redumper-GUI](https://github.com/Deterous/Redumper-GUI) | release tags, built from source (vendored crates) | ✅ | ✅ | ✅ | 26.04 only | 13 only |
| `redumper-mpf` / `redumper-rgui` | fixed-name pins with a moving version: the redumper build that MPF (`redumper-mpf`) and Redumper-GUI (`redumper-rgui`) bundle. `redumper-mpf` is **auto-tracked hourly** from MPF's `publish-nix.sh` and upgrades in place; `redumper-rgui` moves with the Redumper-GUI release. Install one only if you use that frontend — the rolling `redumper` is what you want otherwise. They coexist, each installing as `/usr/bin/<name>` | ✅ | ✅ | ✅ | ✅ | ✅ |

[copr]: https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/
[obs]: https://build.opensuse.org/project/show/home:gmipf:media-preservation

**Fedora** / **EPEL** link to the COPR project; **openSUSE**, **Ubuntu** and
**Debian** all link to the one OBS project (Leap 16.0, Tumbleweed,
Ubuntu 22.04/24.04/26.04, Debian 12+13 — x86_64). For the versions currently
shipping and full install instructions, see those pages.

Redumper-GUI needs rustc ≥ 1.92 (eframe/egui). Debian 13 clears the floor through
`trixie-backports` (rustc 1.94.1, which OBS builds against — the package's
`Build-Depends: rustc (>= 1.92)` pulls it), and Ubuntu 26.04 ships 1.93. Left out:
Ubuntu 22.04/24.04 (≤ 1.91) and Debian 12 (1.63, and its backports carry no rustc).

## Drive access

**Verified on every lane** (2026-07-14, real hardware passed through to a clean
VM per distribution: a Plextor PX-760A USB optical drive and a NEC USB floppy).
A plain desktop user in **no** drive group — not `cdrom`, not `floppy`, not
`disk`, not `plugdev` — dumped both, with `sudo` never invoked. Two independent
mechanisms carry that, and each is delivered differently per distribution:

| | what it grants | Fedora / EPEL | openSUSE | Ubuntu / Debian |
|---|---|---|---|---|
| `uaccess` ACL on the device node | opening and reading the drive | udev rule | udev rule | udev rule |
| `cap_sys_rawio` on the binary | vendor SCSI commands (Plextor `0xD8` …) | `%caps` in the spec | permissions framework (`permctl`) | `setcap` in the `postinst` |

The ACL is granted by systemd-logind to whoever holds the **active local seat** —
for optical drives (`/dev/sr*`) via systemd's own rule, and for USB or legacy
floppy drives via a udev rule these packages ship. It appears the moment the
package is installed; the drive does not need to be re-plugged.

The capability sits on the **dumping tools** — `redumper`, `redumper-rgui`,
`redumper-mpf`, `aaru`, `aaru5` and DiscImageCreator — and deliberately **not** on
any GUI (`mpf-gui`, `redumper-gui`) or on the MPF frontends, which orchestrate
those tools rather than talk to a drive. A process holding file capabilities is
non-dumpable, and the desktop portal service then refuses to authorise it: giving
a GUI `cap_sys_rawio` breaks every file dialog it opens.

Only headless / SSH / cron sessions, which have no seat, need more. For optical
drives, add yourself to the `cdrom` group. A headless floppy dump needs root: the
floppy node stays `root:disk`, and the `disk` group would expose every block
device on the system, so it is not a safe substitute.

### The proof ledger — and how to keep it honest

None of the above is a claim you have to take on trust, and none of it is allowed
to rot quietly. `scripts/proof-ledger.tsv` carries one line per (tool, lane,
mechanism), each with a fingerprint of exactly the recipe fragments that deliver
it — the udev rule, the `%post`/`postinst` body, the `%caps()` directive, the
openSUSE permissions profile. `scripts/proof-status.sh` recomputes that
fingerprint from the live tree and shouts when it moved: touch the scriptlet and
the proof is declared stale. It is keyed on the **mechanism**, never the version,
so a `redumper` b731→b732 bump does not cry wolf.

**Install the hook once per clone** — otherwise the ledger is a script somebody
has to remember to run, which is the failure mode it exists to remove:

```sh
git config core.hooksPath .githooks
```

It blocks a commit on drift, on a missing mechanism line (coverage), and on a
proof whose artifact is missing or does not show its own failure. It deliberately
does **not** block on the open backlog: you must be able to commit a new mechanism
together with the ledger line that admits it is unproven.

Three evidence states, and nothing else: `not-yet` (open), `log:<path>` (measured
red **and** green, artifact saved), and `blocked:<version>:<path>` — red proven,
green blocked by an upstream bug at exactly that version. A blockade passes
through without holding the gate shut, and fails loudly the moment the tool's
version moves, which is the point: marking such a line `proven` instead would sit
green forever and nobody would ever measure it again.

**The artifact is read, not just resolved.** A proof log must contain a RED half,
a GREEN half and a `VERDICT:` line; a blockade must contain a RED half and is not
asked for a GREEN. A run that could not have failed is not evidence — so the
ledger asks each artifact for its failure, rather than trusting that whoever wrote
it remembered to produce one.

Two things that look like permission errors and are not:

- **The desktop may have auto-mounted the medium** (GNOME does, KDE does not) —
  the dumper then cannot take its exclusive lock. Release it without root:
  `udisksctl unmount -b /dev/sr1` (or the floppy's node). Aaru reports this as
  `Could not open device, error EncodingUnknown`, which names everything except
  the cause.
- **Aaru asks a GDPR consent question on its very first run.** Until it is
  answered once, `aaru media dump` stops there. Run `aaru configure` in a
  terminal, then dump.

## Layout

```
.
├── .packit.yaml                            # Packit-as-a-Service config (drives Fedora COPR builds)
├── .github/workflows/
│   ├── watch-redumper-releases.yml         # hourly watcher for redumper's b<N> tags
│   ├── watch-mpf-rolling.yml               # hourly watcher for MPF's rolling tag
│   ├── watch-dic-releases.yml              # hourly watcher for DiscImageCreator master commits
│   └── watch-aaru-releases.yml             # hourly watcher for Aaru's v6.0.0 pre-release tags
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

The Debian-format recipes live in `ubuntu/` — see [`ubuntu/README.md`](ubuntu/README.md).
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

## Automation

Builds are driven by [Packit](https://packit.dev/). Every commit that
touches a tool's `fedora/<tool>/` path triggers Packit to fetch sources, build
the SRPM, and ship a build to COPR project `gmipf/media-preservation`. No
manual `copr-cli build` needed.

The same per-tool watchers drive the OBS lane: on an upstream bump they advance
`ubuntu/<tool>/debian/changelog` and regenerate `opensuse/<tool>/{<tool>.dsc,
debian.tar.gz,_service}` in the same commit, then ask OBS to re-run its source
services. Nothing is uploaded — OBS fetches the recipe and the upstream archives
itself.

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
keeps `%if 0%{?suse_version}` portability, which the openSUSE (OBS) lane builds on —
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
- **aaru** is on the v6.0.0 pre-release track — beta since 2026-07-16; upstream
  publishes a new alpha/beta/rc tag every two to six weeks.
  `watch-aaru-releases.yml` polls hourly, picks the highest tag across the track
  (alpha < beta < rc, the same order rpm and dpkg give the versions derived from
  it) and rewrites `%global aaruprerel` on a bump. Moving within the track needs
  no review: only the tag changes. The workflow loud-fails on stable v6.0.0 or a
  v7+ major, which reshape the packaging instead of advancing it — `Version`
  loses its `~pre-release` tilde and the release assets lose their `-<prerel>`
  infix, so `Source0`/`Source1` stop resolving.

See `.packit.yaml` for the per-tool trigger configuration.

## Install

### Fedora 43+ and RHEL / CentOS Stream / AlmaLinux / Rocky / Oracle 8–10

```sh
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper discimagecreator aaru aaru5 mpf redumper-gui
```

On enterprise Linux, enable EPEL first:

```sh
sudo dnf install epel-release
```

`aaru` and `mpf-gui` need `libunwind`, and enterprise Linux ships it in EPEL, not
in BaseOS/AppStream. Without EPEL those two are unresolvable and the `mpf`
meta-package fails with them (measured on AlmaLinux 9; the `epel-N` buildroot
carries EPEL, which is why the packages build regardless). The COPR `dnf` plugin
itself lives in `dnf-plugins-core` and is in the base repos. Fedora needs no
extra repository.

### openSUSE Leap 16.0 and Tumbleweed

Published on the [openSUSE Build Service](https://build.opensuse.org/project/show/home:gmipf:media-preservation)
(OBS) rather than COPR, whose openSUSE support is limited to an EOL Leap 15.6 and
a currently-broken Tumbleweed, with no Leap 16.0 chroot.

```sh
sudo zypper addrepo https://download.opensuse.org/repositories/home:gmipf:media-preservation/16.0/home:gmipf:media-preservation.repo
sudo zypper refresh
sudo zypper install redumper discimagecreator aaru aaru5 mpf redumper-gui
```

For Tumbleweed, swap `16.0` for `openSUSE_Tumbleweed` in the repo URL.

### Ubuntu 26.04 (resolute), 24.04 (noble) and 22.04 (jammy)

Same OBS project as openSUSE and Debian — swap the repository name for your
release (`xUbuntu_26.04`, `xUbuntu_24.04`, `xUbuntu_22.04`):

```sh
. /etc/os-release        # VERSION_ID is 26.04, 24.04 or 22.04
REPO="https://download.opensuse.org/repositories/home:/gmipf:/media-preservation/xUbuntu_${VERSION_ID}"

curl -fsSL "$REPO/Release.key" | sudo gpg --dearmor -o /usr/share/keyrings/media-preservation.gpg
echo "deb [signed-by=/usr/share/keyrings/media-preservation.gpg] $REPO/ /" \
  | sudo tee /etc/apt/sources.list.d/media-preservation.list

sudo apt update
sudo apt install redumper discimagecreator aaru aaru5 mpf
```

`redumper-gui` is available on 26.04 only: eframe/egui needs rustc ≥ 1.92, and
22.04/24.04 top out at 1.91.

### Debian 13 (trixie) and 12 (bookworm)

Built on the same OBS project as everything else. One `debian/` recipe serves
every Ubuntu and Debian release: an Ubuntu `.deb` does not fit Debian, because the
ICU runtime carries its soname in the package name (`libicu70` on jammy vs
`libicu72` on bookworm), so the dependency is resolved from the build root at
build time rather than from a table of series.

```sh
. /etc/os-release        # VERSION_ID is 13 on trixie, 12 on bookworm
REPO="https://download.opensuse.org/repositories/home:/gmipf:/media-preservation/Debian_${VERSION_ID}"

curl -fsSL "$REPO/Release.key" | sudo gpg --dearmor -o /usr/share/keyrings/media-preservation.gpg
echo "deb [signed-by=/usr/share/keyrings/media-preservation.gpg] $REPO/ /" \
  | sudo tee /etc/apt/sources.list.d/media-preservation.list

sudo apt update
sudo apt install redumper discimagecreator aaru aaru5 mpf
```

Redumper-GUI is available on Debian 13 (trixie) but not Debian 12 (bookworm): it
needs rustc ≥ 1.92, which trixie provides through `trixie-backports` (rustc 1.94.1,
what OBS builds against); bookworm's 1.63 has no backported rustc. On trixie, add it:
`sudo apt install redumper-gui`.

`mpf` is a meta-package; it pulls in `mpf-check` (log validator),
`mpf-cli` (headless dump orchestrator) and `mpf-gui` (Avalonia desktop
frontend). Install the individual subpackages if you only need part of
it (`sudo dnf install mpf-check`, etc.). Launch the GUI via
`mpf-gui` or the `MPF` desktop entry.

`aaru` ships both the CLI and its Avalonia GUI in one binary — launch
the GUI via `aaru gui` or via the `Aaru` desktop entry. `redumper` and
`discimagecreator` are CLI-only.

`cap_sys_rawio` is preset on the dumping tools (`redumper`, `redumper-rgui`,
`redumper-mpf`, `aaru`, `aaru5`, DiscImageCreator) so vendor SCSI passthrough
commands work without sudo — and deliberately **not** on the GUIs or the MPF
frontends, which drive those tools rather than a drive. Logged in at a local
desktop seat you also need **no group membership and no root** to read the drives
themselves. All of this is measured against real hardware on every distribution;
see [Drive access](#drive-access) above for what is proven, what a headless
session still needs, and the two non-errors (desktop auto-mount, Aaru's first-run
consent prompt) that look like permission failures.

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
any of the distributions it targets, with Redump or No-Intro, or with any
upstream tool author.
