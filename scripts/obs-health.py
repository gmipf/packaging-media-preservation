#!/usr/bin/env python3
"""obs-health.py -- turn red when an OBS build fails or OBS falls behind main.

Usage:
  scripts/obs-health.py      report; exit 1 on any ERROR
                             (CI: .github/workflows/obs-health.yml, every 6 h;
                             scripts/status.sh prints the same report)

Why this exists
---------------
OBS builds every lane except Fedora: openSUSE, Debian and Ubuntu. Until
2026-10-13 a failed OBS build turned nothing red. obs-trigger.yml only ASKS OBS
to refresh and returns before anything is built, and the one place that read
the results, status.sh, runs when somebody runs it. COPR has copr-reconcile.yml
for this; this is the OBS half. It reads OBS anonymously (/public/...), so it
needs no credential.

It does not heal. The heal for a lost trigger exists already: obs-trigger.yml
refreshes every package once a day, and refreshing an unchanged package is a
no-op. This is the red for when that was not enough.

What it judges
--------------
1. Every target (repository/arch/package) in the project's build result:
     ok        succeeded, disabled, excluded, locked
     busy      building, scheduled, blocked, ... (BUSY below); part 2 catches a
               reference target that never finishes
     expected  redumper-gui failing where rust-targets.tsv lists the target as
               "out": below the Rust floor that failure IS the intended state,
               and it is read from the inventory, not waved through
     ERROR     anything else (failed, unresolvable, broken); a package with an
               opensuse/<pkg>/_service on main that OBS does not build, or the
               other way round; a TSV row naming a repository OBS does not have
2. Per package, the version OBS publishes for REF_REPO/x86_64 against the spec
   on origin/main (opensuse/<pkg>/<pkg>.spec; OBS's own Release is ignored):
     ok        the same version
     wait      behind, but only on versions main got less than GRACE ago
     ERROR     behind a version main already had GRACE ago; AHEAD of main;
               nothing published at all
   "Behind" is measured against main as it was GRACE ago, never against the age
   of the newest change: mpf bumps several times a day, so that age never
   reaches any grace, and a stuck OBS would wait forever.

Part 2 asks the published ARTIFACT, not the _service file: since every _service
became constant (URLs on main only) it cannot differ from git whatever the spec
says, and on 2026-07-24 OBS built an old mpf revision, green, for hours while a
check of the _service file said "in sync".

The reference is origin/main, never a working tree: OBS fetches the recipe from
main itself. A clone that is as old as a stale OBS agrees with it and reports
"ok" for exactly the lost trigger this is for (status.sh, 2026-07-25).

Not measured is not fine: an OBS that does not answer, an answer that is not the
document asked for, or a git that cannot fetch is an ERROR too.
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET

import rpm

PROJECT = "home:gmipf:media-preservation"
PUBLIC = os.environ.get("OBS_PUBLIC", "https://api.opensuse.org/public")
REF = os.environ.get("OBS_REF_GIT", "origin/main")
REF_REPO = os.environ.get("OBS_REF_REPO", "16.0")
# obs-trigger.yml refreshes every package daily at 05:23 UTC. A trigger lost
# right after one refresh is picked up by the next, a day later, plus the build:
# still behind after 26 h is not late any more, it is stuck.
GRACE = 26 * 3600
GOOD = {"succeeded", "disabled", "excluded", "locked"}
BUSY = {"building", "scheduled", "blocked", "dispatching", "signing", "finished",
        "unknown", "outdated", "unpublished"}
RUST_PKG = "redumper-gui"
# rust-targets.tsv spells one OBS repository differently. The aliases are checked
# against the repositories OBS reports, so a rotten one cannot quietly turn an
# expected failure into an unexpected one, or the other way round.
ALIAS = {"openSUSE_Leap_16.0": "16.0"}


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def obs(path, root_tag):
    """The parsed document at PUBLIC+path; raises unless it is a <root_tag>."""
    with urllib.request.urlopen(PUBLIC + path, timeout=60) as r:
        doc = ET.fromstring(r.read())
    if doc.tag != root_tag:
        raise ValueError(f"{path}: expected <{root_tag}>, got <{doc.tag}>")
    return doc


def inventory(path):
    """{OBS repository: 'ship' | 'out'} from rust-targets.tsv."""
    inv = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) >= 4 and f[0] == "obs":
                inv[ALIAS.get(f[1], f[1])] = f[3]
    if not inv:
        raise ValueError(f"{path} has no obs rows")
    return inv


def judge_targets(result, inv, packages):
    """-> (counts, errors, expected) for a <resultlist> document."""
    counts, errors, expected = {}, [], []
    repos, seen = set(), set()
    for r in result.findall("result"):
        repo, arch = r.get("repository"), r.get("arch")
        repos.add(repo)
        for s in r.findall("status"):
            pkg, code = s.get("package"), s.get("code")
            seen.add(pkg)
            counts[code] = counts.get(code, 0) + 1
            if code in GOOD or code in BUSY:
                continue
            where = f"{pkg} {repo}/{arch}: {code}"
            if pkg == RUST_PKG and inv.get(repo) == "out":
                expected.append(f"{where} (rust-targets.tsv: out, below the Rust floor)")
            else:
                errors.append(where)
    if not seen:
        errors.append("the build result lists no package at all")
    for pkg in sorted(set(packages) - seen):
        errors.append(f"{pkg} has opensuse/{pkg}/_service on {REF}, but OBS builds no {pkg}")
    for pkg in sorted(seen - set(packages)):
        errors.append(f"OBS builds {pkg}, which has no opensuse/{pkg}/_service on {REF}")
    for repo in sorted(set(inv) - repos):
        errors.append(f"rust-targets.tsv names {repo}, which OBS does not build: alias or inventory is stale")
    return counts, errors, expected


def published(binlist, pkg):
    """Version of <pkg>'s own RPM in a <binarylist>, or None. Subpackages
    (mpf-cli-..., redumper-mpf-... in redumper's list) do not count."""
    for b in binlist.findall("binary"):
        fn = b.get("filename", "")
        for suffix in (".x86_64.rpm", ".noarch.rpm"):
            if fn.startswith(pkg + "-") and fn.endswith(suffix):
                rest = fn[len(pkg) + 1:-len(suffix)]
                if rest[:1].isdigit() and "-" in rest:
                    return rest.rsplit("-", 1)[0]
    return None


def vcmp(a, b):
    return rpm.labelCompare(("0", a, "0"), ("0", b, "0"))


def judge_version(have, want, old):
    """-> (state, detail). have: published on OBS; want: main now; old: main
    GRACE ago, None if the package did not exist on main then."""
    h = GRACE // 3600
    if have is None:
        if old is None:
            return "wait", f"nothing published yet; the package is on main for less than {h} h"
        return "ERROR", f"nothing published for {REF_REPO}/x86_64, main has {want}"
    c = vcmp(have, want)
    if c == 0:
        return "ok", have
    if c > 0:
        return "ERROR", f"OBS publishes {have}, NEWER than main's {want}"
    if old is not None and vcmp(have, old) < 0:
        return "ERROR", (f"OBS publishes {have}, but main has had {old} for more than {h} h (now {want}); "
                         "the daily obs-trigger refresh did not bring it either")
    return "wait", f"OBS publishes {have}, main has {want} for less than {h} h"


def spec_version(commit, pkg, tmp):
    """Version of opensuse/<pkg>/<pkg>.spec at commit, None if it has no such spec."""
    blob = f"{commit}:opensuse/{pkg}/{pkg}.spec"
    if subprocess.run(["git", "cat-file", "-e", blob], capture_output=True).returncode != 0:
        return None
    local = os.path.join(tmp, f"{pkg}.spec")
    with open(local, "w") as f:
        f.write(git("show", blob) + "\n")
    out = subprocess.run(["rpmspec", "-q", "--srpm", "--qf", "%{version}\n", local],
                         check=True, capture_output=True, text=True).stdout.split("\n")[0]
    if not out:
        raise ValueError(f"rpmspec gave no version for {blob}")
    return out


def main():
    # The clone this script lives in, not the caller's CWD (status.sh is run from
    # anywhere).
    os.chdir(git("-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "--show-toplevel"))
    now = int(time.time())
    tally = {}

    def report(state, name, detail):
        tally[state] = tally.get(state, 0) + 1
        if state == "ERROR" and os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{name}: {detail}")
        print(f"{state:<9} {name:<17} {detail}")

    try:
        git("fetch", "-q", "origin")
        services = git("ls-tree", "-r", "--name-only", REF, "opensuse/").split("\n")
        packages = sorted(p.split("/")[1] for p in services if p.endswith("/_service"))
        if not packages:
            raise ValueError(f"no opensuse/*/_service on {REF}")
    except Exception as e:  # an unknown reference is no reference: stop here
        report("ERROR", "git", f"could not read {REF}: {type(e).__name__}: {e}")
        sys.exit(1)

    try:
        counts, errors, expected = judge_targets(obs(f"/build/{PROJECT}/_result", "resultlist"),
                                                 inventory("scripts/rust-targets.tsv"), packages)
        print(f"{'targets':<9} {'':<17} " + " · ".join(f"{v}x {k}" for k, v in sorted(counts.items())))
        for e in expected:
            report("expected", "targets", e)
        for e in errors:
            report("ERROR", "targets", e)
    except Exception as e:
        report("ERROR", "targets", f"could not measure: {type(e).__name__}: {e}")

    old_ref = git("rev-list", "-1", f"--before=@{now - GRACE}", REF) or None
    with tempfile.TemporaryDirectory() as tmp:
        for pkg in packages:
            try:
                want = spec_version(REF, pkg, tmp)
                if want is None:
                    raise ValueError(f"no opensuse/{pkg}/{pkg}.spec on {REF}")
                old = spec_version(old_ref, pkg, tmp) if old_ref else None
                have = published(obs(f"/build/{PROJECT}/{REF_REPO}/x86_64/{pkg}", "binarylist"), pkg)
                state, detail = judge_version(have, want, old)
            except Exception as e:
                state, detail = "ERROR", f"could not measure: {type(e).__name__}: {e}"
            report(state, pkg, detail)

    print("summary   " + " · ".join(f"{v}x {k}" for k, v in sorted(tally.items())))
    sys.exit(1 if tally.get("ERROR") else 0)


if __name__ == "__main__":
    main()
