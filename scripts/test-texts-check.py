#!/usr/bin/env python3
"""Decision tests for texts-check.py -- run in CI on every push (check-repo.yml).

The functions under test are the script's own, unmodified, on the real texts
and the real tree of this repository, edited in memory; the live services are
replaced by their answers as of 2026-10-14, so these cases need no network.
Exit 1 if any case disagrees. TEXTSCHECK=<path> runs them against another copy.
"""
import importlib.util
import os
import pathlib
import sys

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("textscheck", os.environ.get("TEXTSCHECK", HERE / "texts-check.py"))
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
ROOT, DESCR = t.ROOT, t.DESCR

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


def has(findings, *words):
    return any(all(w in f for w in words) for f in findings)


REAL_READ, REAL_PACKAGES = t.read, t.packages


def with_text(rel, old, new):
    """read() with one text edited in memory."""
    body = REAL_READ(ROOT, rel)
    edited = body.replace(old, new)
    assert edited != body, f"test setup: {old!r} not found in {rel}"
    t.read = lambda root, r: edited if r == rel else REAL_READ(root, r)


def restore():
    t.read, t.packages = REAL_READ, REAL_PACKAGES


# --- the readers ---------------------------------------------------------------------
check("a name of its own", t.names("install redumper here", "redumper"), True)
check("not inside a longer package name", t.names("install redumper-mpf here", "redumper"), False)
check("not inside a word", t.names("home:gmipf:media", "mpf"), False)
check("any case", t.names("**DiscImageCreator**", "discimagecreator"), True)
check("units: bullets, headings and paragraphs",
      t.units("# Head\ntext one\ncontinued\n\n- a\n  b\n- c\n<!--\n- hidden 12\n-->\nlast\n"),
      ["# Head", "text one continued", "- a b", "- c", "last"])
check("a version needs its word in the same unit", t.mentions("- Fedora 43.\n- EPEL 44.\n", "Fedora", "44"), False)
check("... and is found there", t.mentions("- Fedora 43, 44 and rawhide.\n", "Fedora", "44"), True)
check("a version at a sentence end", t.mentions("EPEL 8, 9 and 10.", "EPEL", "10"), True)
check("a version is not a longer number", t.mentions("Debian 120", "Debian", "12"), False)
check("a version is not part of another", t.mentions("Ubuntu 24.04.1", "Ubuntu", "24.04"), False)
check("a slash list", t.mentions("Enterprise Linux 8/9/10 (enable EPEL there)", "EPEL", "9"), True)
check("line ends and trailing blanks are no drift", t.norm("a  \r\nb\n\n"), t.norm("a\nb"))

# --- the targets -------------------------------------------------------------------------
CHROOTS = sorted(f"{d}-{a}" for d in ("fedora-43", "fedora-44", "fedora-45", "fedora-rawhide", "epel-8", "epel-9",
                                      "epel-10", "rhel+epel-10") for a in ("x86_64", "aarch64"))
REPOS = {"16.0": ["x86_64", "aarch64"], "openSUSE_Tumbleweed": ["x86_64"], "openSUSE_Tumbleweed_ARM": ["aarch64"],
         "xUbuntu_22.04": ["x86_64", "aarch64"], "xUbuntu_24.04": ["x86_64", "aarch64"],
         "xUbuntu_26.04": ["x86_64", "aarch64"], "Debian_12": ["x86_64", "aarch64"], "Debian_13": ["x86_64", "aarch64"]}
rel, arches, unknown = t.targets(CHROOTS, REPOS)
check("13 releases today", len(rel), 13)
check("rawhide and rhel+epel are no release of their own", unknown, [])
check("both architectures", arches, {"x86_64", "aarch64"})
check("Tumbleweed and its ARM repository are one release", ("OBS", "openSUSE Tumbleweed", "") in rel, True)
check("an unknown chroot form", t.targets(["opensuse-leap-16.0-x86_64"], REPOS)[2],
      ["COPR chroot opensuse-leap-16.0-x86_64"])
check("an unknown repository", t.targets(CHROOTS, {"Arch": ["x86_64"]})[2], ["OBS repository Arch"])
check("an unknown architecture", t.targets(CHROOTS, {"Debian_13": ["riscv64"]})[2],
      ["OBS repository Debian_13: architecture riscv64"])


# --- offline: the real tree --------------------------------------------------------------
f, _ = t.offline()
check("the real tree: every package, lane and workflow named", f, [])
with_text("docs/how-it-works.md", "dreamdump", "gdtool")      # every mention, not only the first
f, _ = t.offline()
restore()
check("dreamdump gone from how-it-works", f, ["docs/how-it-works.md: does not name `dreamdump` (fedora/ builds it)",
                                              "docs/how-it-works.md: does not name `dreamdump` (opensuse/ builds it)",
                                              "docs/how-it-works.md: does not name `dreamdump` (ubuntu/ builds it)"])
t.packages = lambda root=ROOT: {k: v | ({"newtool"} if k == "opensuse" else set())
                                for k, v in REAL_PACKAGES(root).items()}
f, _ = t.offline()
restore()
check("a new openSUSE package nobody describes", sorted(x.split(":")[0] for x in f),
      ["README.md", f"{DESCR}/obs-description.txt", "docs/how-it-works.md", "opensuse/README.md"])
with_text(f"{DESCR}/github-about.txt", "macOS", "Mac")
f, _ = t.offline()
restore()
check("a lane missing from the About text", f, [f"{DESCR}/github-about.txt: does not name macOS (macos/ builds for it)"])
with_text("README.md", "gmipf/media-preservation/discimagecreator", "discimagecreator")
f, _ = t.offline()
restore()
check("a formula missing from the brew line", f,
      ["README.md: no `brew install gmipf/media-preservation/discimagecreator` (Formula/discimagecreator.rb)"])
with_text("docs/how-it-works.md", "obs-health.yml", "obs-health")
f, _ = t.offline()
restore()
check("a workflow missing from how-it-works", f, ["docs/how-it-works.md: does not name obs-health.yml"])


def missing(root, rel):
    raise t.Unmeasured(f"{rel}: gone")


t.read = missing
check("offline: an unreadable text is exit 2", t.main(["offline"]), 2)
restore()

# --- live: the answers of 2026-10-14, with the git copies as the live texts ---------------------
GOT = {key: REAL_READ(ROOT, f"{DESCR}/{fname}") for fname, key in t.LIVE.items()}
GOT.update(copr_chroots=CHROOTS, obs_repos=REPOS)


def live_with(**changes):
    return t.live({**GOT, **changes})[0]


check("live: the git copies against themselves", live_with(), [])
f = live_with(copr_description=GOT["copr_description"].replace("Fedora 43+", "Fedora 44+"))
check("live: a description edited on COPR", has(f, f"{DESCR}/copr-description.md: the live text differs",
                                                "-Optical", "+Optical"), True)
f = live_with(github=GOT["github"] + "\n")
check("live: a trailing newline is no drift", f, [])
f = live_with(copr_chroots=CHROOTS + ["fedora-46-x86_64"])
check("live: a new Fedora only the CHANGELOG must name", f, ["CHANGELOG.md: does not name Fedora 46 (COPR builds it)"])
f = live_with(copr_chroots=CHROOTS + ["epel-11-x86_64"])
check("live: a new EPEL", sorted(x.split(":")[0] for x in f), ["CHANGELOG.md", f"{DESCR}/copr-description.md"])
f = live_with(obs_repos={**REPOS, "xUbuntu_26.10": ["x86_64"]})
check("live: a new Ubuntu", sorted(x.split(":")[0] for x in f),
      ["CHANGELOG.md", "README.md", f"{DESCR}/obs-description.txt"])
f = live_with(obs_repos={**REPOS, "Debian_13": ["x86_64", "riscv64"]})
check("live: an unknown architecture is a finding", has(f, "riscv64", "form not understood"), True)
f = live_with(copr_chroots=["fedora-44-ppc64le"])
check("live: an unknown chroot is a finding", has(f, "COPR chroot fedora-44-ppc64le", "form not understood"), True)
with_text("CHANGELOG.md", "aarch64", "arm")
f = live_with()
restore()
check("live: an architecture the CHANGELOG never names", f,
      ["CHANGELOG.md: does not name aarch64 (aarch64/x86_64 are built)"])

t.fetch = lambda: (_ for _ in ()).throw(t.Unmeasured("COPR: timed out"))
check("live: a service that does not answer is exit 2", t.main(["live"]), 2)
check("usage: an unknown mode is exit 2", t.main(["bogus"]), 2)

print(f"\n{'FAILED' if failures else 'all passed'}: {failures} case(s) disagree")
sys.exit(1 if failures else 0)
