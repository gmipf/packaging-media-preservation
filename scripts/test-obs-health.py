#!/usr/bin/env python3
"""Decision tests for obs-health.py -- run before every check in CI.

The judging functions are the code under test, unmodified; OBS is replaced by
XML fixtures (and once by a file:// "server"), git by fixed versions. Exit 1 if
any case disagrees.

Each group was seen to fail against a deliberately broken copy of the script
(2026-10-13, OBSH=<copy>): comparing with the newest version on main instead of
the one GRACE ago, dropping the Rust-floor expectation, and accepting any
filename that starts with the package name.
"""
import importlib.util
import os
import pathlib
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("obsh", os.environ.get("OBSH", HERE / "obs-health.py"))
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


# --- versions -----------------------------------------------------------------
V = [
    ("OBS has main's version", ("1.2", "1.2", "1.2"), "ok"),
    ("OBS ahead of main", ("1.3", "1.2", "1.2"), "ERROR"),
    ("nothing published, package new on main", (None, "1.2", None), "wait"),
    ("nothing published, package older than GRACE", (None, "1.2", "1.2"), "ERROR"),
    ("behind on a bump younger than GRACE", ("1.1", "1.2", "1.1"), "wait"),
    ("behind, package itself younger than GRACE", ("1.1", "1.2", None), "wait"),
    ("behind on a version main had GRACE ago (bumps keep coming)", ("1.0", "1.2", "1.1"), "ERROR"),
    ("behind, main unchanged for longer than GRACE", ("1.1", "1.2", "1.2"), "ERROR"),
    ("rolling snapshot behind its release (~ sorts first)", ("3.11.0~2026.a", "3.11.0", "3.11.0"), "ERROR"),
    ("release ahead of main's pre-release (~)", ("6.0.0", "6.0.0~beta.2", "6.0.0~beta.2"), "ERROR"),
    ("newer snapshot on main within GRACE", ("3.11.0~20261012.a", "3.11.0~20261013.b", "3.11.0~20261012.a"),
     "wait"),
]
for label, (have, want, old), expect in V:
    check(f"version: {label}", h.judge_version(have, want, old)[0], expect)


# --- targets ------------------------------------------------------------------
INV = {"16.0": "ship", "Debian_13": "ship", "Debian_12": "out"}
PKGS = ["mpf", "redumper-gui"]


def result(*rows):
    """rows: (repo, arch, pkg, code)"""
    root = ET.Element("resultlist")
    by = {}
    for repo, arch, pkg, code in rows:
        if (repo, arch) not in by:
            by[(repo, arch)] = ET.SubElement(root, "result", repository=repo, arch=arch)
        ET.SubElement(by[(repo, arch)], "status", package=pkg, code=code)
    return root


def base(override=None):
    rows = {(r, a, p): "succeeded" for r in INV for a in ("x86_64", "aarch64") for p in PKGS}
    rows.update(override or {})
    return result(*[(r, a, p, c) for (r, a, p), c in rows.items()])


def errors(doc, inv=INV, pkgs=PKGS):
    counts, err, exp = h.judge_targets(doc, inv, pkgs)
    return len(err), len(exp)


T = [
    ("all succeeded", base(), (0, 0)),
    ("disabled and building are not errors",
     base({("Debian_12", "x86_64", "redumper-gui"): "disabled", ("16.0", "x86_64", "mpf"): "building"}), (0, 0)),
    ("failed build", base({("Debian_13", "aarch64", "mpf"): "failed"}), (1, 0)),
    ("broken (_service could not run)", base({("16.0", "x86_64", "mpf"): "broken"}), (1, 0)),
    ("redumper-gui unresolvable below the Rust floor",
     base({("Debian_12", "x86_64", "redumper-gui"): "unresolvable"}), (0, 1)),
    ("redumper-gui unresolvable on a shipped target",
     base({("Debian_13", "x86_64", "redumper-gui"): "unresolvable"}), (1, 0)),
    ("another package unresolvable below the Rust floor",
     base({("Debian_12", "x86_64", "mpf"): "unresolvable"}), (1, 0)),
]
for label, doc, expect in T:
    check(f"targets: {label}", errors(doc), expect)
check("targets: a package on main that OBS does not build", errors(base(), pkgs=PKGS + ["dreamdump"]), (1, 0))
check("targets: OBS builds a package main does not have", errors(base(), pkgs=["mpf"]), (1, 0))
check("targets: TSV names a repository OBS does not build",
      errors(base(), inv={**INV, "xUbuntu_99.04": "ship"}), (1, 0))
check("targets: empty result (no package, 2 missing, 3 unknown TSV rows)", errors(result()), (6, 0))


# --- published version ----------------------------------------------------------
def binlist(*names):
    root = ET.Element("binarylist")
    for n in names:
        ET.SubElement(root, "binary", filename=n)
    return root


P = [
    ("own RPM among subpackages and the SRPM",
     binlist("_buildenv", "mpf-3.1~2.a-lp160.9.1.src.rpm", "mpf-cli-3.1~2.a-lp160.9.1.x86_64.rpm",
             "mpf-3.1~2.a-lp160.9.1.x86_64.rpm"), "mpf", "3.1~2.a"),
    ("a sibling package whose name extends ours", binlist("redumper-mpf-761-lp160.3.1.x86_64.rpm"), "redumper", None),
    ("sibling listed first, own RPM after it",
     binlist("redumper-mpf-761-lp160.3.1.x86_64.rpm", "redumper-760-lp160.2.1.x86_64.rpm"), "redumper", "760"),
    ("noarch", binlist("foo-1.0-1.1.noarch.rpm"), "foo", "1.0"),
    ("empty list", binlist(), "mpf", None),
]
for label, doc, pkg, expect in P:
    check(f"published: {label}", h.published(doc, pkg), expect)


# --- an answer must be the document asked for -------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    pathlib.Path(tmp, "html").write_text("<html><body>maintenance</body></html>\n")
    pathlib.Path(tmp, "cut").write_text('<resultlist state="x">\n  <result repository="16.0"')
    pathlib.Path(tmp, "good").write_text('<resultlist state="x"/>\n')
    saved, h.PUBLIC = h.PUBLIC, "file://" + tmp
    try:
        for name, expect in (("html", "ValueError"), ("cut", "ParseError"), ("missing", "URLError"),
                             ("good", "resultlist")):
            try:
                got = h.obs("/" + name, "resultlist").tag
            except Exception as e:  # the type IS the answer here
                got = type(e).__name__
            check(f"answer: {name}", got, expect)
    finally:
        h.PUBLIC = saved

print(f"{'FAILED' if failures else 'passed'}: {failures} of the cases above disagree")
sys.exit(1 if failures else 0)
