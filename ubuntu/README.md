# Debian-format packaging lane (Ubuntu + Debian, built on OBS)

`ubuntu/<tool>/debian/` holds **one** Debian-format recipe per tool, and it serves
**every** Ubuntu and Debian target: Ubuntu 22.04, 24.04 and 26.04, Debian 12 and
13. The directory name predates the Debian targets; the recipes were never
Ubuntu-specific.

They are built on the [OBS project](https://build.opensuse.org/project/show/home:gmipf:media-preservation),
alongside the openSUSE RPMs. There is no separate Debian recipe and no separate
Ubuntu one — a `.deb` built for jammy does not fit bookworm anyway, because the
ICU runtime carries its soname in the package name (`libicu70` vs `libicu72`), so
`debian/rules` resolves that dependency from the **build root** at build time
(`dpkg-query`) instead of from a table of series. Each target gets the one it has.

Every target is built for **amd64 and arm64** (`control` says
`Architecture: amd64 arm64`). The repackaged tools need both upstream arch
archives, and only one of them can be the `.orig`: the amd64 archive is the
`Debtransform-Tar`, and the arm64 one rides along as a `Debtransform-Files`
extra, which `debian/rules` unpacks over the tree on an arm64 build. That step
runs *after* `dpkg-source -b` has captured the tree, so the source package stays
arch-neutral and carries no quilt patch for it. `unzip`/`xz-utils` are in
`Build-Depends` for that reason. The two source-built tools just compile per arch.

> **arm64 is built and published, but not hardware-tested** — the drive-access
> measurements were made on x86_64. The `postinst` `setcap` and the udev rule are
> the same files on both arches, but nobody has dumped a disc from an ARM machine,
> so it is deliberately not claimed as verified.

## File capabilities come from the `postinst`

This lane has no `%caps` (Fedora) and no permissions framework (openSUSE): each
dumper package's `postinst` calls `setcap cap_sys_rawio+ep` on its binary, and
depends on `libcap2-bin` so that `setcap` is guaranteed to be there.

**Verified on real hardware** (2026-07-14, clean Ubuntu 26.04 and Debian 13 VMs
with a Plextor PX-760A and a NEC USB floppy passed through; the user was in no
drive group and `sudo` was never invoked): both media dumped, and the installed
`redumper-rgui` read the Plextor lead-in over the vendor `0xD8` command. A **copy**
of that same binary — `cp` drops file capabilities — died on the first negative
LBA with `error: SYSTEM (Operation not permitted)`. The capability is the only
difference between the two runs.

The capability lands on the **dumping tools** only (`redumper`, `redumper-rgui`,
`redumper-mpf`, `aaru`, `aaru5`, DiscImageCreator). The GUIs and the MPF frontends
deliberately get none — a process with file capabilities is non-dumpable, so the
desktop portal will not authorise it and its file dialogs stop working.

⚠️ Measure the result with **`/usr/sbin/getcap`, spelled out in full**: on Debian
and Ubuntu `getcap` lives in `/sbin` and is *not* in a normal user's `PATH`, so a
bare `getcap` silently reports nothing and a perfectly good `postinst` looks
broken. (`getfattr` and `xxd` are not installed at all there, so they are no
substitute either.)

## How a build runs

OBS pulls everything itself; nothing is uploaded.

1. `opensuse/<tool>/_service` tells OBS to fetch the spec, the `.dsc`,
   `debian.tar.gz` and `debian/changelog` from `main` of this repo, and then to
   download the **upstream** archives named in the spec's `Source:` URLs.
2. At build time OBS runs `debtransform`, which turns the `.dsc` plus those files
   into a real `3.0 (quilt)` source package.
3. `dpkg-buildpackage` builds it in the target's build root.

The `.dsc`, `debian.tar.gz` and the deb block of `_service` are **generated** —
`scripts/obs/gen-deb.sh` — from this recipe and from the spec. Never edit them by
hand; `scripts/status.sh` fails if they drift.

## Nothing is assembled and nothing is re-hosted

An RPM spec lists `Source0:`, `Source1:`, `Source2:` and `rpmbuild` assembles the
tree in `%prep`. A Debian source package has **one** orig tarball, and the build
root has no network — which looks like it forces someone to pre-assemble a merged
tarball and host it somewhere. It does not:

| | RPM spec | `.dsc` |
|---|---|---|
| main upstream archive | `Source0:` | `DEBTRANSFORM-TAR:` |
| the other upstream files | `Source1:`, `Source2:` … | `DEBTRANSFORM-FILES:` |
| assembling the tree | `%prep` | `debian/rules` |

So `debian/rules` unpacks aaru's source tarball, mpf's CLI and GUI zips and dic's
three sibling projects — in the build root, from files OBS downloaded straight
from upstream. The RPM and the `.deb` are built from the same upstream bytes,
fetched once.

Two things about `DEBTRANSFORM-FILES` are not obvious and each costs a red build:

* **It must be UPPERCASE in the `.dsc`.** `debtransform` reads its own headers
  case-insensitively, but obs-build greps for a literal `^DEBTRANSFORM-FILES:` to
  decide whether to pass `--include-binaries` to `dpkg-source`. Spelled in mixed
  case the transform still works — and then `dpkg-source` rejects the extra
  upstream archives as "unrepresentable changes".
* **`--include-binaries` covers binaries, not text.** redumper's `LICENSE` and
  `README.md` — which upstream publishes separately, they are not in the release
  zip — come out as "unexpected upstream changes", so `debian/source/options`
  keeps them out of the diff. They are build inputs, not modifications.

## Testing before you push

```sh
scripts/obs/test-deb.sh debian:13 mpf aaru
scripts/obs/test-deb.sh ubuntu:24.04 redumper
```

This replays exactly what OBS does — download the spec's `Source:` URLs, take the
generated files from git, run `debtransform`, then `dpkg-buildpackage` — in the
target's own container.

It deliberately builds **without** `-b`, because obs-build runs
`dpkg-buildpackage -us -uc`: that builds the source package too, and every mistake
listed above lives in `dpkg-source -b`. A gate milder than the build farm is not
a gate.

The container cannot tell you whether the packaged tool **runs**: a binary
carrying `cap_sys_rawio` cannot even be `exec`'d there, because `CAP_SYS_RAWIO` is
absent from the container's bounding set and the kernel refuses the `execve`
outright. That is a property of the container, not a bug in the package — see the
`drive-access-verification` skill, and use a `test-*` VM.

## Per-tool notes

| Tool | Upstream inputs | Targets |
|---|---|---|
| `redumper`, `redumper-rgui`, `redumper-mpf` | release zip + `LICENSE` + `README.md` | all |
| `aaru5` | one release tarball | all |
| `aaru` | binary tarball + source tarball (icons, `.desktop`, MIME xml) | all |
| `discimagecreator` | DIC + EccEdc + DVDAuth + unscrambler, built from source | all |
| `mpf` | three release zips (Check, CLI, Avalonia) | all |
| `redumper-gui` | vendored source tarball (crates travel with the source: no build root has network) | **Ubuntu 26.04 + Debian 13** |

`redumper-gui` needs rustc ≥ 1.92 (eframe/egui), and that floor is not written
here: it is derived from the `ship` rows of `scripts/rust-targets.tsv`, which is
also what `rust-vendor-tarball.sh` and `watch-redumper-gui.yml` read. One fact,
one place.

Two deb targets clear it. **Ubuntu 26.04** carries 1.93. **Debian 13** carries
1.94 — *from `trixie-backports`*, which is why it builds even though plain trixie
ships 1.85 and the OBS repository is a Download-on-Demand path onto backports.
Ubuntu 22.04/24.04 top out at 1.91 and Debian 12 has no rustc in backports at all;
those three are `build disable`d in the package meta and keep delivering the last
package they could build.

> ⚠️ Until 2026-07-20 this section said "Debian 13 ships 1.85 … only 26.04 clears
> the floor … build-enabled for exactly one repository". That was already known to
> be wrong: `scripts/rust-targets.tsv` records the re-measurement, and its header
> warns in as many words that "an earlier note claimed trixie-backports had no
> newer rustc — that was wrong, and it was wrong in a public upstream issue too."
> The correction was made in the data and never carried into this prose, so the
> superseded number outlived the note that superseded it. Verified against the
> build farm before rewriting: `osc results` reports Debian_13 **succeeded** on
> both x86_64 and aarch64.
