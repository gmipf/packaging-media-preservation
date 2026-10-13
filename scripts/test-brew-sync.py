#!/usr/bin/env python3
"""Decision tests for brew-sync.py -- run in CI on every push (check-repo.yml).

The functions under test are the script's own, unmodified, on the real formulae
and specs of this repository, edited in memory; downloads are replaced by a fake
fetch. Exit 1 if any case disagrees. BREWSYNC=<path> runs the cases against
another copy of the script.
"""
import importlib.util
import os
import pathlib
import sys

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("brewsync", os.environ.get("BREWSYNC", HERE / "brew-sync.py"))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


def outcome(fn, *args, **kw):
    try:
        return fn(*args, **kw)
    except Exception as e:
        return type(e).__name__


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


R, D = b.FORMULAE["redumper"], b.FORMULAE["discimagecreator"]
r_rb, r_spec = read("Formula/redumper.rb"), read(R["spec"])
d_rb, d_spec = read("Formula/discimagecreator.rb"), read(D["spec"])
V = b.spec_fields(r_spec, R["fields"])["V"]
f = b.spec_fields(d_spec, D["fields"])
r_next = r_spec.replace(f"Version:        {V}\n", f"Version:        {int(V) + 1}\n")
d_next = (d_spec.replace(f["SNAP"], "20991231235959.deadbeef")
          .replace(f["COMMIT"], "deadbeef" + "0" * 32))
d_ecc = d_spec.replace(f"%global eccedcver    {f['ECC']}", "%global eccedcver    20991231")
assert r_next != r_spec and d_next != d_spec and d_ecc != d_spec, "fixtures did not apply"

# --- drift ----------------------------------------------------------------------
check("drift: redumper as committed", b.drift(R, r_rb, r_spec), [])
check("drift: discimagecreator as committed", b.drift(D, d_rb, d_spec), [])
check("drift: redumper spec one build ahead -> all three urls", len(b.drift(R, r_rb, r_next)), 3)
check("drift: DIC new master commit -> source url and version", len(b.drift(D, d_rb, d_next)), 2)
check("drift: DIC helper version moved -> only that url", len(b.drift(D, d_rb, d_ecc)), 1)

# --- refusing what it does not understand ----------------------------------------
stray = d_rb.replace('  def install',
                     '  resource "x" do\n    url "https://example.org/x.tar.gz"\n'
                     '    sha256 "' + "0" * 64 + '"\n  end\n\n  def install', 1)
nosha = r_rb.replace('    sha256 "', '    # sha256 "', 1)
withver = r_rb.replace('  license "GPL-3.0-only"', '  version "761"\n  license "GPL-3.0-only"')
assert stray != d_rb and nosha != r_rb and withver != r_rb, "fixtures did not apply"
check("parse refuses a url that belongs to no slot", outcome(b.drift, D, stray, d_spec), "ValueError")
check("parse refuses a url without a sha256", outcome(b.drift, R, nosha, r_spec), "ValueError")
check("parse refuses a version line where the url gives it", outcome(b.drift, R, withver, r_spec), "ValueError")
twice = r_spec + f"\nVersion:        {V}\n"
check("spec field present twice is an error", outcome(b.drift, R, r_rb, twice), "ValueError")

# --- rewrite ----------------------------------------------------------------------
calls = []


def fake(url):
    calls.append(url)
    return "ab" * 32


new = b.rewrite(R, r_rb, r_next, fetch=fake)
check("rewrite: redumper in step afterwards", b.drift(R, new, r_next), [])
check("rewrite: redumper downloads each changed url once", len(calls), 3)
check("rewrite: redumper keeps everything else", new.count("\n"), r_rb.count("\n"))
calls.clear()
new = b.rewrite(D, d_rb, d_ecc, fetch=fake)
check("rewrite: DIC helper bump downloads only that url", [u.split("/")[4] for u in calls], ["EccEdc"])
check("rewrite: DIC other checksums untouched", sum(1 for x in new.split("\n") if ("ab" * 32) in x), 1)
calls.clear()
check("rewrite: nothing to do downloads nothing", (b.rewrite(R, r_rb, r_spec, fetch=fake) == r_rb, calls),
      (True, []))
check("rewrite: a fetch that returns no sha256 is an error",
      outcome(b.rewrite, R, r_rb, r_next, fetch=lambda u: "<html>"), "ValueError")

print(f"\n{failures} of the cases above disagree" if failures else "\nall cases agree")
sys.exit(1 if failures else 0)
