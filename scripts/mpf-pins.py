#!/usr/bin/env python3
"""mpf-pins.py -- the six MPF zips we repackage, pinned by sha256 in all three recipes.

mpf repackages MPF's rolling release: six zips, MPF.{Check,CLI,Avalonia} for
linux-x64 and linux-arm64, behind one tag that every MPF commit moves. Two gaps
follow from how MPF publishes it (.github/workflows/build_and_test.yml, read
2026-11-17): "Update rolling tag" runs BEFORE "Upload to rolling", so for some
minutes the tag names the new commit while the release still holds the old zips,
or a mix; and every later rebuild (copr-reconcile, OBS's daily service run)
downloads what is there THEN, under the version written earlier.

So the zips are taken only from MPF's own run for exactly the commit the tag
names, and the recipes carry the sha256 of each one: both specs check it in
%prep, debian/rules before it unpacks anything. A zip that is not the one taken
fails the build instead of shipping under the wrong version.

  mpf-pins.py check
      offline: the Fedora spec, the openSUSE spec and debian/rules carry the
      same well-formed pins (lint.sh).
  mpf-pins.py current <net> <cfg>
      do the zips on the rolling release still match the pins?
      0 yes · 10 no, MPF uploaded others for the same commit · 1 cannot tell.
  mpf-pins.py take <sha> <net> <cfg> <dir>
      take the zips of MPF commit <sha>: only once MPF's "Build and Test" run
      for that commit has completed with success, and only if every zip was
      uploaded while that run ran. Downloads them into <dir>, checks each
      against the sha256 digest GitHub lists, measures which glibc the bundled
      libGrindCore needs against the wrappers' EL8 guard (grind_glibc in
      ubuntu/mpf/debian/mpf-wrapper.in), then writes the pins.
      0 written · 3 written, but the guard asks for more glibc than MPF now
      needs (a session lowers or removes it) · 75 not yet: MPF's run is still
      going, or the tag moved while this read the release · 1 refused, nothing
      written · 2 usage.

Debian carries one pin the specs do not. MPF.Check for linux-x64 is the .orig
tarball there, so dpkg-source has unpacked it before debian/rules runs and the
zip itself is not in the tree: debian/rules checks the MPF.Check binary from it
instead (MPF_SHA256_Check_x64_binary).
"""
import hashlib
import json
import os
import pathlib
import re
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEDORA = "fedora/mpf/mpf.spec"
OPENSUSE = "opensuse/mpf/mpf.spec"
RULES = "ubuntu/mpf/debian/rules"
TEMPLATE = "ubuntu/mpf/debian/mpf-wrapper.in"
REPO = "SabreTools/MPF"
WORKFLOW = "build_and_test.yml"
# GitHub cancels a job after six hours; a run "in progress" for longer is stuck.
STUCK_SECONDS = 6 * 3600
EL8_GLIBC = 28

# (tool in the asset name, key in the spec macros, the single-file bundle in the zip)
TOOLS = (("Check", "check", "MPF.Check"), ("CLI", "cli", "MPF.CLI"), ("Avalonia", "gui", "MPF"))
RIDS = ("x64", "arm64")
KEYS = [(t, r) for t, _, _ in TOOLS for r in RIDS]
SPEC_KEY = {t: k for t, k, _ in TOOLS}
BUNDLE = {t: b for t, _, b in TOOLS}
DEB_BINARY = ("Check", "x64")  # in Debian the .orig tarball: pinned by its binary

SPEC_RE = re.compile(r"^%global[ \t]+mpfsha_(check|cli|gui)_(x64|arm64)[ \t]+(\S*)[ \t]*$", re.M)
RULES_RE = re.compile(r"^MPF_SHA256_(Check|CLI|Avalonia)_(x64|arm64)(_binary)?[ \t]*:=[ \t]*(\S*)[ \t]*$", re.M)
HEX = re.compile(r"[0-9a-f]{64}")
WAIT, REFUSED, OBSOLETE, CHANGED = 75, 1, 3, 10


def asset(tool, rid, net, cfg):
    return f"MPF.{tool}_{net}_linux-{rid}_{cfg}.zip"


def error(msg):
    print(f"::error::{msg}")


# ------------------------------------------------------------------ recipes

def read_spec(text):
    pins, dup = {}, []
    by_key = {k: t for t, k, _ in TOOLS}
    for key, rid, value in SPEC_RE.findall(text):
        k = (by_key[key], rid)
        if k in pins:
            dup.append(k)
        pins[k] = value
    return pins, dup


def read_rules(text):
    zips, binary, dup, stray = {}, None, [], []
    for tool, rid, is_bin, value in RULES_RE.findall(text):
        k = (tool, rid)
        if is_bin:
            if k != DEB_BINARY:
                stray.append(f"MPF_SHA256_{tool}_{rid}_binary")
            elif binary is not None:
                dup.append(f"MPF_SHA256_{tool}_{rid}_binary")
            binary = value
        elif k == DEB_BINARY:
            stray.append(f"MPF_SHA256_{tool}_{rid} (its zip is the .orig tarball here; "
                         f"pin the binary as MPF_SHA256_{tool}_{rid}_binary)")
        else:
            if k in zips:
                dup.append(f"MPF_SHA256_{tool}_{rid}")
            zips[k] = value
    return zips, binary, dup, stray


def check(root):
    """Problems with the pins in the three recipes; empty = consistent."""
    probs = []
    specs = {}
    for rel in (FEDORA, OPENSUSE):
        pins, dup = read_spec((root / rel).read_text())
        specs[rel] = pins
        for t, r in dup:
            probs.append(f"{rel}: mpfsha_{SPEC_KEY[t]}_{r} is set twice")
        for t, r in KEYS:
            v = pins.get((t, r))
            if v is None:
                probs.append(f"{rel}: no %global mpfsha_{SPEC_KEY[t]}_{r}")
            elif not HEX.fullmatch(v):
                probs.append(f"{rel}: mpfsha_{SPEC_KEY[t]}_{r} is not a sha256 ({v!r})")
    fed = specs[FEDORA]
    for k in KEYS:
        if k in fed and k in specs[OPENSUSE] and fed[k] != specs[OPENSUSE][k]:
            probs.append(f"{OPENSUSE}: mpfsha_{SPEC_KEY[k[0]]}_{k[1]} differs from {FEDORA}")
    zips, binary, dup, stray = read_rules((root / RULES).read_text())
    probs += [f"{RULES}: {d} is set twice" for d in dup]
    probs += [f"{RULES}: unexpected {s}" for s in stray]
    for t, r in KEYS:
        if (t, r) == DEB_BINARY:
            continue
        v = zips.get((t, r))
        if v is None:
            probs.append(f"{RULES}: no MPF_SHA256_{t}_{r}")
        elif v != fed.get((t, r)):
            probs.append(f"{RULES}: MPF_SHA256_{t}_{r} differs from mpfsha_{SPEC_KEY[t]}_{r} in {FEDORA}")
    if binary is None:
        probs.append(f"{RULES}: no MPF_SHA256_{DEB_BINARY[0]}_{DEB_BINARY[1]}_binary")
    elif not HEX.fullmatch(binary):
        probs.append(f"{RULES}: MPF_SHA256_{DEB_BINARY[0]}_{DEB_BINARY[1]}_binary is not a sha256 ({binary!r})")
    return probs


def _set(text, pattern, value, where):
    new, n = re.subn(pattern, lambda m: m.group(1) + value + m.group(2), text, flags=re.M)
    if n != 1:
        raise SystemExit(f"{where}: expected one line matching {pattern!r}, found {n}")
    return new


def write(root, zips, binary):
    """Write the six zip pins into both specs and debian/rules, plus Debian's binary pin."""
    for rel in (FEDORA, OPENSUSE):
        p = root / rel
        text = p.read_text()
        for t, r in KEYS:
            text = _set(text, rf"^(%global[ \t]+mpfsha_{SPEC_KEY[t]}_{r}[ \t]+)\S*([ \t]*)$", zips[(t, r)], rel)
        p.write_text(text)
    p = root / RULES
    text = p.read_text()
    for t, r in KEYS:
        if (t, r) != DEB_BINARY:
            text = _set(text, rf"^(MPF_SHA256_{t}_{r}[ \t]*:=[ \t]*)\S*([ \t]*)$", zips[(t, r)], RULES)
    t, r = DEB_BINARY
    text = _set(text, rf"^(MPF_SHA256_{t}_{r}_binary[ \t]*:=[ \t]*)\S*([ \t]*)$", binary, RULES)
    p.write_text(text)
    probs = check(root)
    if probs or read_spec((root / FEDORA).read_text())[0] != zips:
        raise SystemExit("pins did not land:\n  " + "\n  ".join(probs or ["values differ after writing"]))


def guard_glibc(root):
    m = re.search(r"^grind_glibc=(\d+)$", (root / TEMPLATE).read_text(), re.M)
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------- binaries

def _readelf(flag, path):
    r = subprocess.run(["readelf", "-W", flag, str(path)], capture_output=True, text=True,
                       env={**os.environ, "LC_ALL": "C"}, check=False)
    return r.stdout


def grind_need(zip_path, member):
    """Highest GLIBC_2.<n> the libGrindCore.so inside the bundle needs; None if there is none.

    The bundle is a .NET single-file host with its native libraries appended.
    Each embedded ELF is cut out by its own header (section headers end it) and
    asked for its SONAME; readelf reads x86-64 and aarch64 alike.
    """
    with zipfile.ZipFile(zip_path) as z:
        try:
            data = z.read(member)
        except KeyError:
            return None
    with tempfile.TemporaryDirectory() as td:
        elf = pathlib.Path(td) / "embedded.so"
        for m in re.finditer(rb"\x7fELF\x02\x01\x01", data):
            o = m.start()
            if o + 0x40 > len(data):
                continue
            (shoff,) = struct.unpack_from("<Q", data, o + 0x28)
            shentsize, shnum = struct.unpack_from("<HH", data, o + 0x3A)
            size = shoff + shentsize * shnum
            if size <= 0x40 or o + size > len(data):
                continue
            elf.write_bytes(data[o:o + size])
            if "Library soname: [libGrindCore.so]" not in _readelf("-d", elf):
                continue
            need = [int(n) for n in re.findall(r"\bGLIBC_2\.(\d+)", _readelf("-V", elf))]
            return max(need) if need else None
    return None


def member_sha(zip_path, member):
    with zipfile.ZipFile(zip_path) as z:
        return hashlib.sha256(z.read(member)).hexdigest()


# ------------------------------------------------------------------- GitHub

class GitHub:
    """The four reads `take` and `current` need; tests pass their own."""

    def _get(self, path):
        req = urllib.request.Request(f"https://api.github.com/{path}", headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "packaging-media-preservation-mpf-pins"})
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)

    def tag_sha(self):
        return self._get(f"repos/{REPO}/git/refs/tags/rolling")["object"]["sha"]

    def release(self):
        return self._get(f"repos/{REPO}/releases/tags/rolling")

    def runs(self, sha):
        return self._get(f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
                         f"?head_sha={sha}&event=push&per_page=50")["workflow_runs"]

    def download(self, url, dest):
        h = hashlib.sha256()
        req = urllib.request.Request(url, headers={"User-Agent": "packaging-media-preservation-mpf-pins"})
        with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                h.update(chunk)
                f.write(chunk)
        return h.hexdigest()


def _when(stamp):
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def _digest(a):
    d = (a or {}).get("digest") or ""
    return d[7:] if d.startswith("sha256:") and HEX.fullmatch(d[7:]) else None


# ---------------------------------------------------------------- commands

def take(gh, root, sha, net, cfg, outdir, now=None, need_of=grind_need):
    now = now or datetime.now(timezone.utc)
    short = sha[:8]
    runs = [r for r in gh.runs(sha) if r.get("head_branch") == "master" and r.get("event") == "push"]
    if not runs:
        error(f"MPF has no '{WORKFLOW}' push run on master for {short}, the commit its rolling tag "
              f"names: nothing proves that the zips there were built from it. Not taken.")
        return REFUSED
    run = max(runs, key=lambda r: (r["created_at"], r["id"]))
    url = run.get("html_url", "")
    started = run.get("run_started_at") or run["created_at"]
    if run["status"] != "completed":
        if (now - _when(started)).total_seconds() > STUCK_SECONDS:
            error(f"MPF's Build and Test run for {short} has been '{run['status']}' since {started} "
                  f"({url}): it never finished uploading. Not taken.")
            return REFUSED
        print(f"MPF's Build and Test run for {short} is still '{run['status']}' ({url}); its zips are "
              f"not all uploaded yet. A later run takes them.")
        return WAIT
    if run["conclusion"] != "success":
        error(f"MPF's Build and Test run for {short} ended '{run['conclusion']}' ({url}); the rolling "
              f"release may hold a partial upload. Not taken; mpf moves by itself once MPF publishes "
              f"a commit whose run succeeds.")
        return REFUSED
    ended = run["updated_at"]

    by_name = {a.get("name"): a for a in gh.release().get("assets", [])}
    probs, want = [], {}
    for t, r in KEYS:
        name = asset(t, r, net, cfg)
        a = by_name.get(name)
        if a is None:
            probs.append(f"{name}: not on the release")
            continue
        if a.get("state") != "uploaded":
            probs.append(f"{name}: state '{a.get('state')}'")
        up = a.get("updated_at") or ""
        if not up or not _when(started) <= _when(up) <= _when(ended):
            probs.append(f"{name}: uploaded {up or '(no time)'}, not during MPF's run for {short} "
                         f"({started} .. {ended})")
        digest = _digest(a)
        if digest is None:
            probs.append(f"{name}: GitHub lists no sha256 digest for it")
        want[(t, r)] = (name, a.get("browser_download_url"), digest)
    if not probs:
        outdir.mkdir(parents=True, exist_ok=True)
        for t, r in KEYS:
            name, link, digest = want[(t, r)]
            got = gh.download(link, outdir / name)
            if got != digest:
                probs.append(f"{name}: downloaded sha256 {got} is not the digest GitHub lists ({digest})")
    moved = gh.tag_sha()
    if moved != sha:
        print(f"MPF's rolling tag moved from {short} to {moved[:8]} while this read the release; "
              f"a later run takes the new commit.")
        return WAIT
    if probs:
        error(f"The zips on MPF's rolling release are not the ones its run for {short} built "
              f"({url}). Not taken:\n  " + "\n  ".join(probs))
        return REFUSED

    guard = guard_glibc(root)
    if guard is None:
        error(f"{TEMPLATE} has no grind_glibc= line: the EL8 guard cannot be checked. Not taken.")
        return REFUSED
    needs = {k: need_of(outdir / want[k][0], BUNDLE[k[0]]) for k in KEYS}
    blind = [want[k][0] for k, v in needs.items() if v is None]
    if blind:
        error(f"No libGrindCore.so with a GLIBC_2.x need found in {', '.join(blind)} (MPF {short}). "
              f"MPF compresses its logs with it, and the wrappers' guard (grind_glibc={guard} in "
              f"{TEMPLATE}) is measured against it: read what MPF uses now before taking this build. "
              f"Not taken.")
        return REFUSED
    top = max(needs.values())
    shown = ", ".join(f"{want[k][0]} 2.{v}" for k, v in needs.items())
    if top > guard:
        gap = f"2.{guard}" if top - 1 == guard else f"2.{guard} to 2.{top - 1}"
        error(f"libGrindCore in MPF {short} needs glibc 2.{top}, but the wrappers' guard assumes "
              f"2.{guard} (grind_glibc in {TEMPLATE}): on glibc {gap} MPF would "
              f"write empty log archives and extract them as 0-byte files, unguarded. Not taken. "
              f"Raise grind_glibc to {top}, run scripts/mpf-wrapper-sync.py write, and update the "
              f"texts that name 2.{guard} (docs/how-it-works.md, docs/descriptions/). Measured: {shown}.")
        return REFUSED

    write(root, {k: want[k][2] for k in KEYS},
          member_sha(outdir / want[DEB_BINARY][0], BUNDLE[DEB_BINARY[0]]))
    print(f"Pinned the six zips of MPF {short} (run {url}); libGrindCore needs glibc 2.{top}.")
    if top < guard:
        todo = (f"remove the MPF-GLIBC-GUARD blocks from {TEMPLATE}" if top <= EL8_GLIBC
                else f"lower grind_glibc in {TEMPLATE} to {top}")
        error(f"libGrindCore in MPF {short} needs only glibc 2.{top}, the wrappers' guard still asks "
              f"for 2.{guard}: it refuses log archives on systems where MPF can read them. MPF was "
              f"packaged anyway. A session should {todo}, run scripts/mpf-wrapper-sync.py write, and "
              f"update the texts that name 2.{guard}. Measured: {shown}.")
        return OBSOLETE
    return 0


def current(gh, root, net, cfg):
    probs = check(root)
    if probs:
        error("The mpf pins are inconsistent:\n  " + "\n  ".join(probs))
        return REFUSED
    pins = read_spec((root / FEDORA).read_text())[0]
    by_name = {a.get("name"): a for a in gh.release().get("assets", [])}
    differ = []
    for t, r in KEYS:
        name = asset(t, r, net, cfg)
        digest = _digest(by_name.get(name))
        if digest is None:
            error(f"{name}: GitHub lists no sha256 digest for it, so whether it is still the zip we "
                  f"pinned cannot be told.")
            return REFUSED
        if digest != pins[(t, r)]:
            differ.append(name)
    if differ:
        print(f"MPF uploaded other zips for the commit we ship: {', '.join(differ)}.")
        return CHANGED
    print("The six zips on MPF's rolling release are the ones pinned.")
    return 0


def main(argv):
    if argv[:1] == ["check"] and len(argv) == 1:
        probs = check(ROOT)
        for p in probs:
            print(p, file=sys.stderr)
        if not probs:
            print("mpf pins: both specs and debian/rules carry the same six")
        return 1 if probs else 0
    if argv[:1] == ["current"] and len(argv) == 3:
        return current(GitHub(), ROOT, argv[1], argv[2])
    if argv[:1] == ["take"] and len(argv) == 5 and re.fullmatch(r"[0-9a-f]{40}", argv[1]):
        return take(GitHub(), ROOT, argv[1], argv[2], argv[3], pathlib.Path(argv[4]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
