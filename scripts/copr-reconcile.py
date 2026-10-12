#!/usr/bin/env python3
"""copr-reconcile.py -- make COPR catch up with main when a trigger got lost.

Usage:
  scripts/copr-reconcile.py          report only (safe anywhere, needs network)
  scripts/copr-reconcile.py --heal   also re-push the trigger branch of every
                                     package whose current version COPR never got
                                     (CI: .github/workflows/copr-reconcile.yml)

Why this exists
---------------
A COPR build starts when a watcher (or scripts/build-tool.sh) pushes the
package's trigger branch build-<tool> right after bumping the spec on main.
That push is the one step nothing ever repeats. On 2026-10-12 GitHub answered
pushes with 500s; push-retry.sh now retries, but if all attempts fail the
version sits on main and every later watcher run finds main already bumped and
has nothing left to do. The build is lost, not late. OBS has had the same
safety net since that day (obs-trigger.yml runs daily); this is the COPR one.

What it compares
----------------
Per copr_build job in .packit.yaml: the spec NEVRA on origin/main (rpmspec, the
same evaluation Packit uses) against the builds COPR has for that package.

  ok        COPR's latest successful build carries main's NEVRA
  running   a build of the package is queued or running -- wait for it
  fresh     main moved less than GRACE ago -- the watcher's own push may still
            be on its way to Packit
  heal      COPR has NO build of main's NEVRA at all, in any state: the trigger
            branch is pushed again (main's tree + the branch's own README)
  ERROR     needs a look, and is never retried here:
            - a build of main's NEVRA failed or was cancelled (a failed build
              can still have published some chroots, so a rebuild of the same
              NEVRA could swap packages under dnf's feet -- the same reason
              build-tool.sh bumps the Release instead)
            - COPR's latest success is NEWER than main
            - our own earlier re-push of this exact tree produced no build
            - COPR or git did not answer (not measurable is not "fine")

It only ever pushes a version that COPR has never seen, so it cannot publish the
same NEVRA twice. Exit status: 1 if any package is ERROR (or a heal push failed).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import rpm
import yaml

OWNER, PROJECT = "gmipf", "media-preservation"
API = "https://copr.fedorainfracloud.org/api_3"
BUILD_URL = f"https://copr.fedorainfracloud.org/coprs/{OWNER}/{PROJECT}/build/"
REF = "origin/main"
# A watcher commits, pushes main, then pushes the trigger branch; Packit then
# needs a few minutes to submit. An hour keeps us clear of that window, which is
# what makes a duplicate submission of the same NEVRA impossible.
GRACE = 3600
IN_FLIGHT = {"importing", "pending", "starting", "running", "waiting"}
HEAL_SUBJECT = "reconcile:"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def copr(path):
    with urllib.request.urlopen(f"{API}/{path}", timeout=60) as r:
        return json.load(r)


def jobs(root):
    """(package, trigger branch, package dir, spec path) for every copr_build job."""
    with open(os.path.join(root, ".packit.yaml")) as f:
        cfg = yaml.safe_load(f)
    out = []
    for job in cfg.get("jobs") or []:
        if job.get("job") != "copr_build" or job.get("trigger") != "commit":
            continue
        pattern = job.get("branch", "")
        branch = pattern[1:-1] if pattern.startswith("^") and pattern.endswith("$") else ""
        if not branch.startswith("build-") or any(c in branch for c in "^$*+?()[]|\\"):
            sys.exit(f"copr_build job with an unexpected branch pattern: {pattern!r}")
        # One package per trigger branch -- that IS the routing. Fail loudly on more.
        (pkg,) = job["packages"]
        p = cfg["packages"][pkg]
        (pkgdir,) = p["paths"]
        pkgdir = pkgdir.rstrip("/")
        out.append((pkg, branch, pkgdir, f"{pkgdir}/{p['specfile_path']}"))
    if not out:
        sys.exit("no copr_build commit jobs in .packit.yaml")
    return out


def spec_nevra(spec_path, tmp):
    """(name, 'version-release') of the spec as committed on REF, dist stripped."""
    local = os.path.join(tmp, os.path.basename(spec_path))
    with open(local, "w") as f:
        f.write(git("show", f"{REF}:{spec_path}") + "\n")
    out = subprocess.run(["rpmspec", "-q", "--srpm", "--qf", "%{name}\n%{version}\n%{release}\n", local],
                         check=True, capture_output=True, text=True).stdout.split("\n")
    name, version, release = out[0], out[1], out[2]
    return name, f"{version}-{release.split('.')[0]}"


def vr_cmp(a, b):
    av, ar = a.rsplit("-", 1)
    bv, br = b.rsplit("-", 1)
    return rpm.labelCompare(("0", av, ar), ("0", bv, br))


def judge(pkg, branch, pkgdir, spec, tmp, now):
    """-> (state, detail, main's version-release). Never raises for an expected condition."""
    name, want = spec_nevra(spec, tmp)
    changed = int(git("log", "-1", "--format=%ct", REF, "--", pkgdir))

    latest = copr(f"package?ownername={OWNER}&projectname={PROJECT}&packagename={name}"
                  "&with_latest_succeeded_build=True")
    ok_build = (latest.get("builds") or {}).get("latest_succeeded") or {}
    have = (ok_build.get("source_package") or {}).get("version")
    builds = copr(f"build/list?ownername={OWNER}&projectname={PROJECT}&packagename={name}"
                  "&limit=50&order=id&order_type=DESC")["items"]

    if have == want:
        return "ok", f"copr {have} (#{ok_build['id']})", want
    if have and vr_cmp(have, want) > 0:
        return "ERROR", f"COPR's latest success {have} (#{ok_build['id']}) is NEWER than main's {want}", want

    running = [b for b in builds if b["state"] in IN_FLIGHT]
    if running:
        return "running", f"#{running[0]['id']} is {running[0]['state']} (copr has {have or 'nothing'})", want

    # Every build that is, or may be, an attempt at main's NEVRA. A build whose
    # SRPM never got made carries no version at all -- count it if it came after
    # the change on main.
    tried = [b for b in builds
             if (b.get("source_package") or {}).get("version") == want
             or (not (b.get("source_package") or {}).get("version") and b["submitted_on"] >= changed)]
    if tried:
        b = tried[0]
        return "ERROR", (f"COPR build #{b['id']} of {want} ended '{b['state']}' -- {BUILD_URL}{b['id']}/ "
                         "(not re-pushed: the same NEVRA must not be built twice)"), want

    if now - changed < GRACE:
        return "fresh", f"main changed {(now - changed) // 60} min ago, copr has {have or 'nothing'}", want

    # The trigger branch already carries this tree: someone pushed it (a watcher
    # late, a human, or we ourselves on an earlier run). Recently -> wait for
    # Packit, never push twice. Long ago, and it was OUR re-push -> pushing yet
    # again would just repeat that every run, green and useless.
    tip_time, tip_subject = git("log", "-1", "--format=%ct%n%s", f"origin/{branch}").split("\n", 1)
    tip_age = now - int(tip_time)
    if git("rev-parse", f"origin/{branch}:{pkgdir}") == git("rev-parse", f"{REF}:{pkgdir}"):
        if tip_age < GRACE:
            return "fresh", f"{branch} got this tree {tip_age // 60} min ago, waiting for Packit", want
        if tip_subject.startswith(HEAL_SUBJECT):
            return "ERROR", (f"{branch} was re-pushed for {want} at "
                             f"{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(int(tip_time)))} "
                             "and Packit never submitted a COPR build"), want
    return "heal", f"COPR never got {want} (has {have or 'nothing'}); main changed {(now - changed) // 3600} h ago", want


def heal(pkg, branch, want):
    """Recreate the trigger branch as main's tree + its own README, force-push it."""
    readme = git("show", f"origin/{branch}:README.md")
    start = git("rev-parse", "HEAD")
    git("checkout", "-q", "-B", "reconcile-tmp", REF)
    try:
        with open("README.md", "w") as f:
            f.write(readme + "\n")
        git("add", "README.md")
        git("-c", "user.name=copr-reconcile", "-c", "user.email=actions@github.com",
            "commit", "-q", "-m", f"{HEAL_SUBJECT} {pkg} {want} -- COPR never got this version")
        return subprocess.run(["bash", "scripts/push-retry.sh", "-f", "origin",
                               f"reconcile-tmp:{branch}"]).returncode == 0
    finally:
        git("checkout", "-q", start)
        git("branch", "-D", "reconcile-tmp")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--heal", action="store_true", help="re-push trigger branches that COPR never built")
    args = ap.parse_args()

    root = git("rev-parse", "--show-toplevel")
    os.chdir(root)
    # Tracked changes only: heal() checks out other trees, which untracked files
    # do not get in the way of (and CI leaves some, e.g. a __pycache__).
    if args.heal and git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("tracked files are modified -- --heal checks out other trees, refusing")
    git("fetch", "-q", "--prune", "origin")

    now = int(time.time())
    bad = 0
    with tempfile.TemporaryDirectory() as tmp:
        for pkg, branch, pkgdir, spec in jobs(root):
            try:
                state, detail, want = judge(pkg, branch, pkgdir, spec, tmp, now)
            except Exception as e:  # any failure to measure is a finding, not a pass
                state, detail = "ERROR", f"could not measure: {type(e).__name__}: {e}"
            if state == "heal":
                if not args.heal:
                    state = "would-heal"
                elif heal(pkg, branch, want):
                    state, detail = "healed", f"{detail} -> {branch} re-pushed"
                else:
                    state, detail = "ERROR", f"{detail} -> re-push of {branch} FAILED"
            if state == "ERROR":
                bad += 1
                if os.environ.get("GITHUB_ACTIONS"):
                    print(f"::error::{pkg}: {detail}")
            print(f"{state:<11} {pkg:<15} {detail}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
