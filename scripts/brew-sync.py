#!/usr/bin/env python3
"""brew-sync.py -- keep Formula/ in step with the Fedora specs.

Usage:
  scripts/brew-sync.py --check [<formula> ...]   offline: exit 1 if a formula
                                                  names other upstream sources
                                                  than its spec
  scripts/brew-sync.py --write <formula> ...     rewrite urls and version from
                                                  the spec, download every
                                                  changed source for its sha256

The spec is the one source of truth: the watchers bump it (and the openSUSE and
Debian recipes) on every upstream change. A formula is a second copy of the same
facts -- which upstream file, which version -- and a second copy that nothing
compares drifts silently: the Linux packages move on, the Mac users keep the old
build, and every check stays green. So the watchers call --write before they
commit, and check-repo.yml runs --check on every push.

Each formula has SLOTS: one url line each, recognised by its shape whatever the
version, and the first sha256 line after it and before the next url. Every slot must match exactly one
url line and every url line must belong to a slot, so a url this script does not
know about is an error, not a line it quietly leaves alone. --write downloads a
source only when its url changed; an unchanged url keeps its checksum.
"""
import hashlib
import os
import re
import subprocess
import sys
import urllib.request

GH = "https://github.com"
FORMULAE = {
    "redumper": {
        "spec": "fedora/redumper/redumper.spec",
        "fields": {"V": r"^Version:\s*(\d+)\s*$"},
        "version": None,  # the url gives it
        "slots": [
            (r"https://github\.com/superg/redumper/archive/refs/tags/b\d+\.tar\.gz",
             GH + "/superg/redumper/archive/refs/tags/b{V}.tar.gz"),
            (r"https://github\.com/superg/redumper/releases/download/b\d+/redumper-b\d+-macos-arm64\.zip",
             GH + "/superg/redumper/releases/download/b{V}/redumper-b{V}-macos-arm64.zip"),
            (r"https://github\.com/superg/redumper/releases/download/b\d+/redumper-b\d+-macos-x64\.zip",
             GH + "/superg/redumper/releases/download/b{V}/redumper-b{V}-macos-x64.zip"),
        ],
    },
    "discimagecreator": {
        "spec": "fedora/discimagecreator/discimagecreator.spec",
        "fields": {
            "SNAP": r"^%global\s+dicsnap\s+(\S+)\s*$",
            "COMMIT": r"^%global\s+diccommit\s+([0-9a-f]{40})\s*$",
            "ECC": r"^%global\s+eccedcver\s+(\S+)\s*$",
            "DVD": r"^%global\s+dvdauthver\s+(\S+)\s*$",
            "UNSC": r"^%global\s+unscramblver\s+(\S+)\s*$",
        },
        "version": "{SNAP}",
        "slots": [
            (r"https://github\.com/saramibreak/DiscImageCreator/archive/[0-9a-f]{40}\.tar\.gz",
             GH + "/saramibreak/DiscImageCreator/archive/{COMMIT}.tar.gz"),
            (r"https://github\.com/saramibreak/EccEdc/archive/refs/tags/[^\"/]+\.tar\.gz",
             GH + "/saramibreak/EccEdc/archive/refs/tags/{ECC}.tar.gz"),
            (r"https://github\.com/saramibreak/DVDAuth/archive/refs/tags/v[^\"/]+\.tar\.gz",
             GH + "/saramibreak/DVDAuth/archive/refs/tags/v{DVD}.tar.gz"),
            (r"https://github\.com/saramibreak/unscrambler/archive/refs/tags/[^\"/]+\.tar\.gz",
             GH + "/saramibreak/unscrambler/archive/refs/tags/{UNSC}.tar.gz"),
        ],
    },
}
URL_LINE = re.compile(r'^(\s*)url "([^"]+)"\s*$')
SHA_LINE = re.compile(r'^(\s*)sha256 "([0-9a-f]{64})"\s*$')
VERSION_LINE = re.compile(r'^(\s*)version "([^"]+)"\s*$')


def spec_fields(text, fields):
    """{name: value} from the spec text; every field exactly once."""
    out = {}
    for name, rx in fields.items():
        hits = re.findall(rx, text, re.M)
        if len(hits) != 1:
            raise ValueError(f"spec: {len(hits)} matches for {name} ({rx}), expected 1")
        out[name] = hits[0]
    return out


def expected(cfg, spec_text):
    """-> (urls in slot order, version or None) the spec asks for."""
    f = spec_fields(spec_text, cfg["fields"])
    urls = [tmpl.format(**f) for _, tmpl in cfg["slots"]]
    version = cfg["version"].format(**f) if cfg["version"] else None
    return urls, version


def parse(cfg, text):
    """-> (lines, {slot: (url line index, sha line index)}, version line index or None)."""
    lines = text.split("\n")
    slots, owned = {}, set()
    url_lines = [i for i, line in enumerate(lines) if URL_LINE.match(line)]
    for k, (rx, _) in enumerate(cfg["slots"]):
        hits = [i for i in url_lines if re.fullmatch(rx, URL_LINE.match(lines[i]).group(2))]
        if len(hits) != 1:
            raise ValueError(f"slot {k} ({rx}): {len(hits)} url lines match, expected 1")
        i = hits[0]
        # Its sha256 is the first one after it and before the next url (Homebrew
        # puts a `version` line between them at the top of a formula).
        nxt = min([j for j in url_lines if j > i], default=len(lines))
        shas = [j for j in range(i + 1, nxt) if SHA_LINE.match(lines[j])]
        if not shas:
            raise ValueError(f"line {i + 1}: url without a sha256 line before the next url")
        slots[k] = (i, shas[0])
        owned.add(i)
    stray = [i + 1 for i in url_lines if i not in owned]
    if stray:
        raise ValueError(f"url line(s) {stray} belong to no slot: unknown source, refusing to guess")
    vers = [i for i, line in enumerate(lines) if VERSION_LINE.match(line)]
    if cfg["version"] is None:
        if vers:
            raise ValueError("has a version line, but the url gives the version")
        return lines, slots, None
    if len(vers) != 1:
        raise ValueError(f"{len(vers)} version lines, expected 1")
    return lines, slots, vers[0]


def drift(cfg, formula_text, spec_text):
    """List of differences between formula and spec; empty when in step."""
    want_urls, want_version = expected(cfg, spec_text)
    lines, slots, vi = parse(cfg, formula_text)
    out = []
    for k, (ui, _) in slots.items():
        have = URL_LINE.match(lines[ui]).group(2)
        if have != want_urls[k]:
            out.append(f"url {have} -- spec says {want_urls[k]}")
    if vi is not None:
        have = VERSION_LINE.match(lines[vi]).group(2)
        if have != want_version:
            out.append(f"version {have} -- spec says {want_version}")
    return out


def sha256_of(url):
    h = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as r:
        for chunk in iter(lambda: r.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def rewrite(cfg, formula_text, spec_text, fetch=sha256_of):
    """-> new formula text in step with the spec; fetch(url) -> sha256 for changed urls."""
    want_urls, want_version = expected(cfg, spec_text)
    lines, slots, vi = parse(cfg, formula_text)
    for k, (ui, si) in slots.items():
        m = URL_LINE.match(lines[ui])
        if m.group(2) == want_urls[k]:
            continue
        digest = fetch(want_urls[k])
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"{want_urls[k]}: no sha256 ({digest!r})")
        lines[ui] = f'{m.group(1)}url "{want_urls[k]}"'
        lines[si] = f'{SHA_LINE.match(lines[si]).group(1)}sha256 "{digest}"'
    if vi is not None:
        lines[vi] = f'{VERSION_LINE.match(lines[vi]).group(1)}version "{want_version}"'
    new = "\n".join(lines)
    left = drift(cfg, new, spec_text)
    if left:
        raise AssertionError(f"rewrite left drift behind: {left}")
    return new


def main(argv):
    if len(argv) < 2 or argv[1] not in ("--check", "--write"):
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        return 2
    mode, names = argv[1], argv[2:] or (sorted(FORMULAE) if argv[1] == "--check" else [])
    if not names:
        print("--write needs at least one formula name", file=sys.stderr)
        return 2
    os.chdir(subprocess.run(["git", "-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse",
                             "--show-toplevel"], check=True, capture_output=True, text=True).stdout.strip())
    present = sorted(f[:-3] for f in os.listdir("Formula") if f.endswith(".rb"))
    if mode == "--check" and present != sorted(FORMULAE):
        print(f"STALE: Formula/ holds {present}, this script knows {sorted(FORMULAE)}")
        return 1
    rc = 0
    for name in names:
        if name not in FORMULAE:
            print(f"unknown formula {name}", file=sys.stderr)
            return 2
        cfg = FORMULAE[name]
        path = f"Formula/{name}.rb"
        with open(cfg["spec"], encoding="utf-8") as fh:
            spec = fh.read()
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if mode == "--write":
            new = rewrite(cfg, text, spec)
            if new != text:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new)
                print(f"{path}: rewritten from {cfg['spec']}")
            else:
                print(f"{path}: already in step")
            continue
        try:
            diffs = drift(cfg, text, spec)
        except ValueError as e:
            diffs = [f"cannot read: {e}"]
        for d in diffs:
            print(f"STALE: {path}: {d} -- run scripts/brew-sync.py --write {name}")
            rc = 1
    if mode == "--check" and rc == 0:
        print(f"brew-sync --check: {len(names)} formula(e) name the sources their specs name")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
