# media-preservation-packaging

Distribution packaging recipes (specs, debian rules, PKGBUILDs, …) for the
[`gmipf/media-preservation`](https://copr.fedorainfracloud.org/coprs/gmipf/media-preservation/)
COPR repository.

**This repo does *not* contain upstream tool source code** — only the recipes
needed to build the tools into distro packages. Upstream source lives at the
respective project URLs (see below).

## Tools

| Tool | Upstream | Fedora | Debian | Arch | Alpine |
|---|---|---|---|---|---|
| [redumper](https://github.com/superg/redumper) | b724 | ✅ | — | — | — |
| [MPF](https://github.com/SabreTools/MPF) | — | planned | — | — | — |
| [DiscImageCreator](https://github.com/saramibreak/DiscImageCreator) | — | planned | — | — | — |

## Layout

```
.
├── .packit.yaml              # Packit-as-a-Service config (drives Fedora COPR builds)
├── LICENSE                   # MIT (recipes only; tools keep their own licenses)
├── README.md
└── fedora/
    └── <tool>/
        └── <tool>.spec       # RPM spec
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

Fedora builds are driven by [Packit](https://packit.dev/). When a new tag
appears in an upstream tool repo, Packit fetches the tarball, runs the spec,
and triggers a build in COPR project `gmipf/media-preservation`. No manual
`copr-cli build` needed.

See `.packit.yaml` for the trigger rules.

## Install (Fedora 43+)

```sh
sudo dnf copr enable gmipf/media-preservation
sudo dnf install redumper
```

For drive access setup (CAP_SYS_RAWIO is set on the binary, but you still
need read access to `/dev/sr*`) see the COPR project description.

## Status

Unsupported third-party recipes. Personal hobby project, not affiliated with
the Fedora Project, Redump, No-Intro, or any upstream tool author.
