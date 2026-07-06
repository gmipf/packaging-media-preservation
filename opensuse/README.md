# openSUSE packaging lane (Open Build Service)

RPM packaging for the media-preservation tools, published on the
**[openSUSE Build Service](https://build.opensuse.org/)** (OBS). This is the
openSUSE counterpart to the Fedora/EPEL `fedora/` lane (COPR) and the Ubuntu
`ubuntu/` lane (Launchpad PPA).

> **Status: validated locally, not yet on OBS.** All five tools (`redumper`,
> `aaru5`, `aaru`, `mpf`, `discimagecreator`) have been built in a real
> **openSUSE Leap 16.0 chroot** (a podman container, `rpmbuild -ba`) — including
> the `discimagecreator` meson source build (the hermetic-build gate). The one
> mechanism that differs from the Fedora/Ubuntu lanes, the **permissions-framework
> capability handling**, is confirmed working: the `permissions.d` profile parses
> (`permctl`), the `%set_permissions`/`%verify_permissions` macros resolve, and
> `cap_sys_rawio=ep` actually lands on every target binary (`getcap`). See
> *Permissions framework & rpmlint* below for the one policy nuance this surfaced.
> What is **not** done yet is publishing on OBS: the account / home project still
> has to be created (see *Account setup*). Until then `redumper` is bumped by hand.

## How an OBS build works

Like COPR, OBS builds the RPMs itself on its own farm; unlike COPR the build
root is **hermetic - no network**. So every upstream asset has to be present as
a committed package source before the build starts. We use the same
repackaging model as the other lanes (ship the upstream prebuilt binary), with
the assets pulled in by a **source service** rather than fetched at build time.

1. A `_service` runs `download_files`, which reads the spec's `Source:` URLs and
   downloads each one by basename into the package.
2. We commit the spec, the `_service` and the downloaded assets together.
3. OBS builds the `.rpm` for each configured repository (Leap 16.0,
   Tumbleweed) and publishes them.

`download_files` reads the URLs straight from the spec, so a version bump only
touches the spec's `Version:` field - the `_service` never changes. Because
build.opensuse.org does not run `download_files` server-side (network policy),
the service is `mode="manual"`: run it locally and commit the result.

## Layout

```
opensuse/<tool>/
├── .upstream-tag       # last-seen upstream tag (watcher anchor, mirrors fedora/ & ubuntu/)
├── _service            # download_files (manual) - fetches the Source: URLs
├── <tool>.spec         # openSUSE spec (Fedora spec + distro-native adaptations)
├── <tool>.1            # handwritten manpage, @TAG@/@DATE@ stamped in %build
├── <tool>-rpmlintrc    # self-authorizes the permissions.d cap profile (see below)
└── <asset files>       # committed after `osc service manualrun` (release zip, LICENSE, README)
```

The `<tool>-rpmlintrc` is not a `Source:` and is not installed — OBS copies the
whole package directory into the build root's `SOURCES/`, and rpmlint
auto-loads any `*-rpmlintrc` it finds there.

The spec is deliberately close to `fedora/<tool>/<tool>.spec`. The one
structural difference is file capabilities: openSUSE grants them through the
**permissions framework**, because the post-build permissions check rejects a
bare `%caps` entry. So instead of `%caps(cap_sys_rawio=ep)` in `%files`, the
spec ships a `/usr/share/permissions/permissions.d/<tool>` profile and
applies/verifies it with `%set_permissions` / `%verify_permissions`. See the
next section for the details this was validated against.

## Permissions framework & rpmlint

The capability handling was validated in a Leap 16.0 chroot for all five tools
(container recipe kept outside the repo). Confirmed:

- The `%set_permissions` / `%verify_permissions` macros resolve. On Leap 16.0
  they expand to **`permctl`** (the `chkstat` binary was renamed; `chkstat`
  remains as a compat alias). `permctl` reads the shipped
  `permissions.d/<tool>` profile and the `+capabilities cap_sys_rawio=ep`
  continuation line parses cleanly.
- `cap_sys_rawio=ep` actually lands on every target binary after `%post`
  (verified with `getcap`) — redumper, aaru5, aaru, all three mpf binaries, and
  both DIC binaries.

One policy nuance surfaced: openSUSE's rpmlint flags any permissions.d profile
that isn't whitelisted in the central `permissions` package with
**`permissions-file-unauthorized` (Badness 10)**. This is the distro's security
review gate. It is a *BlockedFilter* in `opensuse.toml`, so it **cannot** be
silenced with `addFilter` (by design — that would defeat the review). Two facts
make it a non-issue here:

- On a personal OBS **home:** project the rpmlint result is informational; it
  does not block the build or publishing (same as the Fedora/COPR lane, which
  ships the identical capability via `%caps`).
- Each package ships a **`<tool>-rpmlintrc`** with
  `setBadness("permissions-file-unauthorized", 0)`, which demotes the finding to
  a zero-badness warning (verified: total rpmlint badness drops accordingly).
  `setBadness` is honoured where `addFilter` is blocked.

Submitting any of these to **openSUSE Factory** (not the plan — this is a
personal repo, the COPR/PPA equivalent) would instead require the profile to be
reviewed and whitelisted in the central `permissions` package. A separate
cosmetic `permissions-missing-verifyscript` warning is a stale rpmlint check
(it greps the verifyscript for `/chkstat` only, not the new `permctl`); our
`%verifyscript` is correct and the warning carries zero badness.

## Account setup (one-time gate)

Nothing here can be built until there is an OBS account and a home project:

1. Create an account on <https://build.opensuse.org/> (openSUSE / SUSE login).
2. `osc` is already installed locally (1.27.1). Configure credentials on first
   use: `osc checkout home:<user>` will prompt and write `~/.config/osc/oscrc`.
   **That file holds the OBS password/token - never display or commit it.**
3. Create the home project `home:<user>` and a package `redumper`, with
   repositories for **openSUSE Leap 16.0** (repository name `16.0`) and
   **openSUSE Tumbleweed**, architecture `x86_64`.

## Publishing a package

From `opensuse/redumper/` after the package exists on OBS:

```sh
osc checkout home:<user> redumper        # or work in an osc-managed checkout
# copy redumper.spec, _service, redumper.1 into the checkout, then:
osc service manualrun                     # download the release zip, LICENSE, README
osc addremove                             # stage spec + _service + assets
osc commit -m "redumper b729"             # triggers the OBS build
```

### Local test build (the `mock` equivalent)

`osc build` runs the exact OBS build locally in a chroot - the openSUSE analogue
of `mock` for the Fedora lane. Run the service first so the assets are present:

```sh
osc service manualrun
osc build openSUSE_Tumbleweed x86_64 redumper.spec
osc build 16.0 x86_64 redumper.spec       # openSUSE Leap 16.0
```

Needs network (chroot bootstrap + asset download), so run it outside the command
sandbox.

## Versioning

Base version in the spec is the upstream number with `Release: 0`; OBS supplies
its own build/release counter on top. A real upstream bump edits `Version:`,
re-runs `osc service manualrun` (fetching the new assets) and commits.

openSUSE's native changelog convention is a separate `<tool>.changes` file
(managed with `osc vc`); the scaffold keeps a `%changelog` in the spec for now,
which OBS accepts. Switching to `.changes` is a later polish, not a blocker.

## Automation (planned)

The Fedora and Ubuntu lanes are driven by per-tool watchers
(`.github/workflows/watch-<tool>.yml`) that bump both lanes on a new upstream
revision. OBS can be wired the same way once the account exists - either a
watcher step that commits to OBS via `osc` with a stored token, or OBS's own
`_service` scheduled remotely. Not built yet; `redumper` is bumped by hand for
now.

## Packaged tools

| Tool             | Kind                              | `_service`      | Notes |
|------------------|-----------------------------------|-----------------|-------|
| redumper         | static binary                     | download_files  | no shlib deps; stamped manpage |
| aaru5            | NativeAOT binary + sidecar `.so`  | download_files  | auto ELF deps; static manpage; udev |
| aaru             | self-contained .NET (single-file) | download_files  | two tarballs; manpage from `--help`; udev; icons/MIME/desktop |
| mpf              | self-contained .NET × 3           | download_files  | `mpf` meta + `mpf-check`/`mpf-cli`/`mpf-gui`; caps per subpackage |
| discimagecreator | **source build** (meson)          | download_url ×4 | four archives; helper makefiles; two caps binaries; udev |

Every tool grants its `cap_sys_rawio` capability through the **permissions
framework** (see *Permissions framework & rpmlint*) instead of `%caps`. `aaru`,
`mpf` (all three subpackages) and `discimagecreator` map their .NET / Ninja
names to openSUSE under the `%if 0%{?suse_version}` branches already present in
the Fedora specs; those branches' BuildRequires were confirmed to resolve on
Leap 16.0 (`aaru`'s `libicu` / `krb5` / `libopenssl3` / `libz1` /
`libunwind.so.8`, `dic`'s `ninja` / `pkgconfig(libarchive|openssl|zlib)`) and
all five specs built with `rpmbuild -ba`.

`discimagecreator` is the only **source build** and the hermetic-build gate:
its `debian`-free meson compile plus three helper makefiles must complete with
no network in the OBS build root. Its four upstream archives use rpm's
`#/rename` Source convention, which `download_files` may not reproduce, so it
uses explicit `download_url` services with a matching `filename` per source
(the tag is hard-coded in `_service` and bumped per release alongside the spec).

The GUI weak `Recommends` (`aaru`, `mpf-gui`) still carry the Fedora library
names; they never enter the build root so they don't affect the build, but they
should be ported to openSUSE runtime names (`libX11-6`, `Mesa-libGL1`, ...) so a
GUI install actually pulls them. Tracked as a post-first-build polish.
