# Does OBS keep a published binary when the package stops building?

> ⚠️ **Not a ledger proof and no ledger row.** The ledger tracks drive access —
> tool/lane/arch/property. This measures a property of the *build service*, so it
> is filed as a measurement report. Named `MEASURED`, not `.log`, because the
> filename is a claim too.

Measured 2026-07-22 in a throwaway project `home:gmipf:msrv-probe` (created,
measured, deleted; production untouched). Repository `16.0` →
`openSUSE:Leap:16.0/standard`, x86_64 scheduler, `BuildArch: noarch` packages.

## Why the question was load-bearing

Decision D2/(c) of 2026-07-19: when an upstream release raises the Rust floor
above a target we ship to, **that target is switched off for the new version and
the last package built for it stays in the repository and keeps being delivered.**

The COPR half of "switch off" is a git edit. The OBS half was believed to be
`build disable` in the package meta — which no OBS token can write, so it was a
declared human step and the watcher failed the run to demand it.

But `build disable` is only *necessary* if it is what preserves the old binary.
If a package that simply stops resolving keeps its published binary, then raising
the floor **in the recipe** switches the target off by itself, D2/(c) still holds,
and the human step is cosmetic. That is the whole question, and nothing in this
repository had ever measured it.

## Setup — two arms, one variable

Both packages: trivial noarch spec, `Version: 1`, built green and **published**
(verified in `/published/home:gmipf:msrv-probe/16.0/noarch` before any treatment).

    probe-unres-1-lp160.1.1.noarch.rpm
    probe-disable-1-lp160.1.1.noarch.rpm

Then both received the same new version. The only difference is *why* the new
build does not happen:

| | treatment | resulting build state |
|---|---|---|
| **A** | `Version: 2` + `BuildRequires: rust >= 99.0` | `unresolvable` |
| **B** | `Version: 3` committed while `<disable repository="16.0"/>` is in the package meta | `disabled` |

OBS reported for arm A, verbatim:

    <status package="probe-unres" code="unresolvable">
      <details>nothing provides rust &gt;= 99.0, (got version 1.96.0-160000.1.1)</details>

## Result — after both treatments, repository state `published`

    /published/home:gmipf:msrv-probe/16.0/noarch
      probe-disable-2-lp160.1.1.noarch.rpm      <- arm B: last build that succeeded
      probe-unres-1-lp160.1.1.noarch.rpm        <- arm A: last build that succeeded

**Both arms keep the last successfully built binary.** A package that becomes
`unresolvable` is not purged from the published repository; neither is one that
is `disabled`. The publisher ran in both states — the repository code is
`published`, not stale.

⭐ **So `build disable` is not what protects the artifact.** It suppresses an
`unresolvable` line in the build status. That is worth something — a permanently
red field trains people to ignore red — but it is a display concern, and a display
concern can be solved in git.

## What this changes

1. The Rust floor is now written into every recipe that declares it
   (`scripts/msrv-sync.sh`). Until 2026-07-22 nothing did: `msrv-disable.sh`
   edited `.packit.yaml` and the inventory and never touched a recipe.
   🔴 That gap is why "the resolver protects the artifact" was only half true.
   `BuildRequires: rust >= 1.92` means "1.92 and up may build" — if upstream needs
   1.94 and the literal stays at 1.92, every target still satisfies it, the build
   starts and dies in the middle of cargo. **The clean `unresolvable` state
   measured here only ever occurs if that number is raised.**
2. With the floor raised, a below-floor target switches itself off on every lane,
   with no package meta and no credential — and by the measurement above it keeps
   delivering its last package, which is exactly D2/(c).
3. `status.sh` reads `rust-targets.tsv` and calls a red on an `out` target
   EXPECTED, so the remaining permanent red does not erode the signal.

## Scope, stated honestly

- One OBS instance (`api.opensuse.org`), one repository type (rpm-md via
  Leap 16.0), one package format. The Debian/Ubuntu publisher is a different code
  path in OBS and was **not** measured.
- Measured for `unresolvable` and `disabled`. **Not** measured: `failed`,
  `broken`, `excluded`, an explicit `osc wipebinaries`, or removing the
  `<repository>` block entirely — that last one plausibly does remove binaries and
  is a different operation from switching a package off.
- Arm B was run twice. The first attempt set `build disable` *after* version 2 had
  already built and published, so it measured "disable preserves the last build"
  rather than "disable preserves an older build when a newer one cannot happen".
  The strict re-run (version 3, committed while disabled) is the one reported
  above. The loose first arm is kept in this note deliberately: it is the same
  class of error as measuring aaru5 without a terminal — an arm that answers a
  slightly different question than the one asked, and looks like an answer.

## Cleanup

`osc rdelete -r -f home:gmipf:msrv-probe` — verified gone.
