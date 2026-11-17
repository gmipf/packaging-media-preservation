#!/usr/bin/env python3
"""Decision tests for mpf-pins.py -- run in CI on every push (check-repo.yml).

The script's own functions, unmodified, on copies of the real recipes in a
scratch directory; GitHub is replaced by a fake that serves a release, MPF's
workflow runs and the downloads, and the libGrindCore measurement by a table.
Exit 1 if any case disagrees. MPFPINS=<path> runs the cases against another copy
of the script.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import os
import pathlib
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("mpfpins", os.environ.get("MPFPINS", HERE / "mpf-pins.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


SHA = "f" * 40
OTHER = "e" * 40
NET, CFG = "net11.0", "debug"
NOW = datetime(2026, 11, 17, 21, 0, tzinfo=timezone.utc)
FILES = (p.FEDORA, p.OPENSUSE, p.RULES, p.TEMPLATE)


def zip_with(member, payload):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, payload)
    return buf.getvalue()


# One "zip" per asset; the Check x64 one is a real zip, Debian's binary pin is read from it.
CONTENT = {k: b"zip:" + p.asset(*k, NET, CFG).encode() for k in p.KEYS}
CONTENT[p.DEB_BINARY] = zip_with("MPF.Check", b"the MPF.Check binary")
BINARY_SHA = hashlib.sha256(b"the MPF.Check binary").hexdigest()


def sha(b):
    return hashlib.sha256(b).hexdigest()


class FakeGitHub:
    def __init__(self):
        self.tag = SHA
        self.tag_after = None          # the tag as take() reads it last, after the release
        self.run_list = [{"id": 7, "head_branch": "master", "event": "push", "status": "completed",
                          "conclusion": "success", "created_at": "2026-11-17T20:00:00Z",
                          "run_started_at": "2026-11-17T20:00:00Z", "updated_at": "2026-11-17T20:13:00Z",
                          "html_url": "https://example.invalid/run/7"}]
        self.assets = [{"name": p.asset(*k, NET, CFG), "state": "uploaded", "updated_at": "2026-11-17T20:11:00Z",
                        "digest": "sha256:" + sha(CONTENT[k]), "browser_download_url": f"dl://{k[0]}/{k[1]}"}
                       for k in p.KEYS]
        self.served = {f"dl://{k[0]}/{k[1]}": CONTENT[k] for k in p.KEYS}
        self.downloads = 0

    def tag_sha(self):
        return self.tag_after or self.tag

    def release(self):
        return {"assets": copy.deepcopy(self.assets)}

    def runs(self, sha_):
        return copy.deepcopy(self.run_list) if sha_ == self.tag else []

    def download(self, url, dest):
        self.downloads += 1
        data = self.served[url]
        pathlib.Path(dest).write_bytes(data)
        return sha(data)


def scratch():
    d = pathlib.Path(tempfile.mkdtemp(prefix="mpf-pins-test-"))
    for rel in FILES:
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, d / rel)
    return d


def snapshot(root):
    return {rel: (root / rel).read_text() for rel in FILES}


def run_take(gh, needs=None, mutate=None):
    """take() on a scratch copy; returns (exit code, pins written?, check problems after)."""
    root = scratch()
    try:
        if mutate:
            mutate(root)
        before = snapshot(root)
        table = needs or {}
        need_of = lambda path, member: table.get(path.name, 34)  # noqa: E731
        with contextlib.redirect_stdout(io.StringIO()):
            rc = p.take(gh, root, SHA, NET, CFG, root / "zips", now=NOW, need_of=need_of)
        changed = snapshot(root) != before
        written = None
        if changed:
            pins = p.read_spec((root / p.FEDORA).read_text())[0]
            _, binary, _, _ = p.read_rules((root / p.RULES).read_text())
            written = pins == {k: sha(CONTENT[k]) for k in p.KEYS} and binary == BINARY_SHA
        return rc, changed, written, p.check(root)
    finally:
        shutil.rmtree(root)


def edit(rel, old, new):
    def f(root):
        t = (root / rel).read_text()
        assert old in t, f"fixture: {old!r} not in {rel}"
        (root / rel).write_text(t.replace(old, new, 1))
    return f


# --- check: the three recipes as committed, and broken copies ---------------------
check("check: recipes as committed", p.check(ROOT), [])
fed_pins = p.read_spec((ROOT / p.FEDORA).read_text())[0]
cli_arm = fed_pins[("CLI", "arm64")]


def problems_after(mutate):
    root = scratch()
    try:
        mutate(root)
        return len(p.check(root))
    finally:
        shutil.rmtree(root)


check("check: openSUSE pin differs -> 1", problems_after(edit(p.OPENSUSE, cli_arm, "0" * 64)), 1)
check("check: Debian pin differs -> 1", problems_after(edit(p.RULES, cli_arm, "0" * 64)), 1)
check("check: Fedora pin not hex -> differs in both others too",
      problems_after(edit(p.FEDORA, cli_arm, "x" * 64)) >= 1, True)
deb_binary = p.read_rules((ROOT / p.RULES).read_text())[1]
check("check: Debian binary pin not hex -> 1", problems_after(edit(p.RULES, deb_binary, "x" * 64)), 1)
check("check: Debian loses a line -> 1",
      problems_after(edit(p.RULES, "MPF_SHA256_CLI_arm64 ", "MPF_SHA256_CLI_armXX ")), 1)
check("check: Debian pins the Check x64 zip -> 1",
      problems_after(edit(p.RULES, "MPF_SHA256_Check_x64_binary", "MPF_SHA256_Check_x64")), 2)
check("check: spec macro set twice -> 1",
      problems_after(edit(p.FEDORA, "%global mpfsha_cli_x64 ", "%global mpfsha_cli_arm64 ")) >= 1, True)

# --- take: the gate on MPF's run ---------------------------------------------------
check("take: run done, zips uploaded during it -> pins written", run_take(FakeGitHub()), (0, True, True, []))

g = FakeGitHub()
g.run_list[0].update(status="in_progress", conclusion=None, run_started_at="2026-11-17T20:30:00Z")
check("take: run in progress -> wait, nothing written", run_take(g)[:2], (p.WAIT, False))

g = FakeGitHub()
g.run_list[0].update(status="in_progress", conclusion=None, run_started_at="2026-11-17T12:00:00Z")
check("take: run in progress for 9 h -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.run_list[0].update(conclusion="failure")
check("take: run failed -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.run_list = []
check("take: no run for the commit -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.run_list[0]["head_branch"] = "some-branch"
check("take: only a run on another branch -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
older = dict(g.run_list[0], id=6, created_at="2026-11-17T19:00:00Z", conclusion="failure")
g.run_list.insert(0, older)
check("take: failed older attempt, newer run succeeded -> written", run_take(g)[:2], (0, True))

# --- take: the zips must be that run's ---------------------------------------------
g = FakeGitHub()
g.assets[2]["updated_at"] = "2026-11-16T20:08:00Z"
check("take: one zip from before the run -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.assets[4]["updated_at"] = "2026-11-17T20:20:00Z"
check("take: one zip from after the run -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.assets[1]["state"] = "starter"
check("take: one zip not fully uploaded -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
del g.assets[5]
check("take: one zip missing -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.assets[0]["digest"] = None
check("take: no digest listed -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.served["dl://CLI/x64"] = b"something else"
check("take: download differs from the digest -> refused", run_take(g)[:2], (p.REFUSED, False))

g = FakeGitHub()
g.tag_after = OTHER
check("take: tag moved while reading -> wait", run_take(g)[:2], (p.WAIT, False))

g = FakeGitHub()
g.tag_after = OTHER
g.assets[4]["updated_at"] = "2026-11-17T20:20:00Z"
check("take: tag moved AND a newer zip -> wait, not refused", run_take(g)[:2], (p.WAIT, False))

# --- take: libGrindCore's glibc against the wrappers' guard --------------------------
arm_gui = p.asset("Avalonia", "arm64", NET, CFG)
check("take: one bundle needs 2.35 -> refused", run_take(FakeGitHub(), {arm_gui: 35})[:2], (p.REFUSED, False))
check("take: one bundle without libGrindCore -> refused",
      run_take(FakeGitHub(), {arm_gui: None})[:2], (p.REFUSED, False))
low = {p.asset(*k, NET, CFG): 31 for k in p.KEYS}
check("take: all need only 2.31 -> written, guard obsolete", run_take(FakeGitHub(), low)[:3], (p.OBSOLETE, True, True))
check("take: template without grind_glibc -> refused",
      run_take(FakeGitHub(), mutate=edit(p.TEMPLATE, "grind_glibc=34", "grind_glibc=x"))[:2], (p.REFUSED, False))
check("take: guard raised to 35 -> written, guard obsolete",
      run_take(FakeGitHub(), mutate=edit(p.TEMPLATE, "grind_glibc=34", "grind_glibc=35"))[:2], (p.OBSOLETE, True))


# --- current: do the zips on the release still match? --------------------------------
def run_current(gh):
    with contextlib.redirect_stdout(io.StringIO()):
        return p.current(gh, ROOT, NET, CFG)


g = FakeGitHub()
for a, k in zip(g.assets, p.KEYS, strict=True):
    a["digest"] = "sha256:" + fed_pins[k]
check("current: digests are the pins -> 0", run_current(g), 0)
g.assets[3]["digest"] = "sha256:" + "1" * 64
check("current: one zip re-uploaded -> changed", run_current(g), p.CHANGED)
g.assets[3]["digest"] = None
check("current: no digest -> cannot tell", run_current(g), p.REFUSED)

print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
