# Debian-format packaging lane (Debian + Ubuntu, built on OBS)

`ubuntu/<tool>/debian/` holds **one** Debian-format recipe per tool, and it serves
**every** Debian and Ubuntu target: Debian 12 and 13, Ubuntu 22.04, 24.04 and
26.04. The directory name predates the Debian targets; the recipes were never
Ubuntu-specific.

They are built on the [OBS project](https://build.opensuse.org/project/show/home:gmipf:media-preservation),
alongside the openSUSE RPMs. There is no separate Debian recipe and no separate
Ubuntu one — a `.deb` built for jammy does not fit bookworm anyway, because the
ICU runtime carries its soname in the package name (`libicu70` vs `libicu72`), so
`debian/rules` resolves that dependency from the **build root** at build time
(`dpkg-query`) instead of from a table of series. Each target gets the one it has.

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
| `redumper`, `redumper729`, `redumper732` | release zip + `LICENSE` + `README.md` | all |
| `aaru5` | one release tarball | all |
| `aaru` | binary tarball + source tarball (icons, `.desktop`, MIME xml) | all |
| `discimagecreator` | DIC + EccEdc + DVDAuth + unscrambler, built from source | all |
| `mpf` | three release zips (Check, CLI, Avalonia) | all |
| `redumper-gui` | vendored source tarball (crates travel with the source: no build root has network) | **Ubuntu 26.04 only** |

`redumper-gui` needs rustc ≥ 1.92 (eframe/egui). Debian 13 ships 1.85, Debian 12
ships 1.63, and Ubuntu 22.04/24.04 top out at 1.91. Only 26.04 clears the floor —
that is a floor, not an oversight, and it is why the tool is build-enabled for
exactly one repository in its OBS package meta.
