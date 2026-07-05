# openSUSE packaging lane (Open Build Service)

RPM packaging for the media-preservation tools, published on the
**[openSUSE Build Service](https://build.opensuse.org/)** (OBS). This is the
openSUSE counterpart to the Fedora/EPEL `fedora/` lane (COPR) and the Ubuntu
`ubuntu/` lane (Launchpad PPA).

> **Status: scaffold.** `redumper` is staged here but has **not** been built on
> OBS yet - the OBS account / home project still has to be created (see
> *Account setup* below). Everything marked *verify on first `osc build`* is a
> best-effort port from the Fedora spec that a first real build must confirm.

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
├── .upstream-tag     # last-seen upstream tag (watcher anchor, mirrors fedora/ & ubuntu/)
├── _service          # download_files (manual) - fetches the Source: URLs
├── <tool>.spec       # openSUSE spec (Fedora spec + distro-native adaptations)
├── <tool>.1          # handwritten manpage, @TAG@/@DATE@ stamped in %build
└── <asset files>     # committed after `osc service manualrun` (release zip, LICENSE, README)
```

The spec is deliberately close to `fedora/<tool>/<tool>.spec`. The one
structural difference for `redumper` is file capabilities: openSUSE grants them
through the **permissions framework** (`chkstat`), because the post-build
permissions check rejects a bare `%caps` entry. So instead of
`%caps(cap_sys_rawio=ep)` in `%files`, the spec ships a
`/usr/share/permissions/permissions.d/redumper` profile and applies/verifies it
with `%set_permissions` / `%verify_permissions`. *(Verify on first `osc build`:
macro names, the permissions.d path for Leap 16.0/Tumbleweed, and the
`+capabilities` continuation-line format.)*

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

| Tool     | Kind          | Notes |
|----------|---------------|-------|
| redumper | static binary | no shlib deps; stamped manpage; cap via permissions framework |

`aaru5`, `aaru`, `mpf` and `discimagecreator` follow (the portability of their
specs to openSUSE was already proven under `mock` with Leap/Tumbleweed configs;
`discimagecreator` is the hermetic-build gate - it needs its source tarballs
committed via the `_service`, like `fedora/discimagecreator`).
