#!/usr/bin/env python3
"""The texts a reader sees, against what this repository ships.

  texts-check.py offline
      Every package is named in each text of its lanes, every formula in the
      README's brew line, every lane in the README and the GitHub About text,
      every workflow in docs/how-it-works.md. Runs in scripts/lint.sh, so in CI
      and in the pre-commit hook.

  texts-check.py live [--save DIR]
      The descriptions on GitHub (About), COPR and OBS equal their copies in
      docs/descriptions/, and every release and architecture COPR and OBS build
      for is named: all of them in CHANGELOG.md, the OBS ones in README.md and
      the OBS description, the EPEL ones in the COPR description. Reads the
      public APIs without a login (GH_TOKEN, when set, only lifts GitHub's rate
      limit). Runs in check-repo.yml on every push and in scripts/status.sh.
      --save DIR writes the live texts to DIR, to look at a drift.

Why: the recipes move and the texts stay behind. The live descriptions had no
copy in git at all, so nothing could compare them with anything; a new release
on COPR or OBS reached no text unless someone remembered. The per-commit half
(does a recipe change come with a text change?) is scripts/docs-gate.py.

Exit 0 ok, 1 with one line per finding, 2 when a text or a service could not
be read (not measured is not clean).
"""
import difflib
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESCR = "docs/descriptions"
GITHUB_API = "https://api.github.com/repos/gmipf/packaging-media-preservation"
COPR_API = "https://copr.fedorainfracloud.org/api_3/project?ownername=gmipf&projectname=media-preservation"
OBS_META = "https://api.opensuse.org/public/source/home:gmipf:media-preservation/_meta"

# docs/descriptions/<file> -> the live text it is the copy of
LIVE = {
    "github-about.txt": "github",
    "copr-description.md": "copr_description",
    "copr-instructions.md": "copr_instructions",
    "obs-title.txt": "obs_title",
    "obs-description.txt": "obs_description",
}

# Which texts must name the packages of which lanes. A lane is a recipe
# directory: fedora/ (Fedora, EPEL), opensuse/ (openSUSE), ubuntu/ (Debian,
# Ubuntu), Formula/ (macOS).
NAME_RULES = (
    (("README.md",), ("fedora", "opensuse", "ubuntu")),
    (("docs/how-it-works.md",), ("fedora", "opensuse", "ubuntu", "macos")),
    ((f"{DESCR}/copr-description.md", f"{DESCR}/copr-instructions.md"), ("fedora",)),
    ((f"{DESCR}/obs-description.txt",), ("opensuse",)),
    (("opensuse/README.md",), ("opensuse",)),
    (("ubuntu/README.md",), ("ubuntu",)),
)
LANE_WORDS = {"fedora": ("Fedora", "EPEL"), "opensuse": ("openSUSE",),
              "ubuntu": ("Debian", "Ubuntu"), "macos": ("macOS",)}
LANE_TEXTS = ("README.md", f"{DESCR}/github-about.txt")
BREW_LINE = "gmipf/media-preservation/{}"      # README: brew install <tap>/<formula>
WORKFLOWS_TEXT = "docs/how-it-works.md"

# The word a text uses for a distribution, next to its version.
WORD = {"Fedora": "Fedora", "EPEL": "EPEL", "openSUSE Leap": "Leap",
        "openSUSE Tumbleweed": "Tumbleweed", "Ubuntu": "Ubuntu", "Debian": "Debian"}


class Unmeasured(Exception):
    """A text or a service that could not be read."""


def git_files(root, *paths):
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *paths],
                       capture_output=True, text=True)
    if r.returncode:
        raise Unmeasured(f"git ls-files: {r.stderr.strip()}")
    return [f for f in r.stdout.split("\0") if f]


def packages(root=ROOT):
    """Lane -> the package names whose recipes git holds."""
    lanes = {"fedora": set(), "opensuse": set(), "ubuntu": set(), "macos": set()}
    for f in git_files(root, "fedora", "opensuse", "ubuntu", "Formula"):
        parts = f.split("/")
        if parts[0] in lanes and len(parts) >= 3:
            lanes[parts[0]].add(parts[1])
        elif parts[0] == "Formula" and len(parts) == 2 and parts[1].endswith(".rb"):
            lanes["macos"].add(parts[1][:-3])
    return lanes


def read(root, rel):
    try:
        return (root / rel).read_text(encoding="utf-8")
    except OSError as e:
        raise Unmeasured(f"{rel}: {e.strerror or e}") from e


def names(text, name):
    """Is `name` in `text` as a name of its own? `redumper` is not in `redumper-mpf`."""
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.I) is not None


COMMENT = re.compile(r"<!--.*?-->", re.S)
STARTS = re.compile(r"(?:[-*]|\d+\.)\s")


def units(text):
    """Paragraphs, bullets and headings, each joined into one line. HTML comments drop out."""
    text = COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    out, cur = [], []
    for line in text.split("\n"):
        s = line.strip()
        if (not s or s.startswith("#") or STARTS.match(s)) and cur:
            out.append(" ".join(cur))
            cur = []
        if s:
            cur.append(s)
        if s.startswith("#"):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def mentions(text, distro, version):
    """Does one paragraph, bullet or heading carry the distribution's word and its version?"""
    word = WORD[distro]
    ver = re.compile(rf"(?<![\d.]){re.escape(version)}(?!\d|\.\d)") if version else None
    return any(word in u and (ver is None or ver.search(u)) for u in units(text))


def label(distro, version):
    return f"{distro} {version}".strip()


# --- offline ---------------------------------------------------------------------

def offline(root=ROOT):
    lanes = packages(root)
    if not any(lanes.values()):
        raise Unmeasured("no recipe found in fedora/, opensuse/, ubuntu/ or Formula/ -- the layout moved")
    findings = []
    for texts, want in NAME_RULES:
        body = "\n".join(read(root, t) for t in texts)
        for lane in want:
            for pkg in sorted(lanes[lane]):
                if not names(body, pkg):
                    findings.append(f"{' + '.join(texts)}: does not name `{pkg}` ({lane}/ builds it)")
    for t in LANE_TEXTS:
        body = read(root, t)
        for lane, words in LANE_WORDS.items():
            if lanes[lane]:
                findings += [f"{t}: does not name {w} ({lane}/ builds for it)" for w in words if w not in body]
    readme = read(root, "README.md")
    findings += [f"README.md: no `brew install {BREW_LINE.format(f)}` (Formula/{f}.rb)"
                 for f in sorted(lanes["macos"]) if BREW_LINE.format(f) not in readme]
    flows = [f for f in git_files(root, ".github/workflows") if f.endswith((".yml", ".yaml"))]
    if not flows:
        raise Unmeasured("no workflow found in .github/workflows -- the layout moved")
    doc = read(root, WORKFLOWS_TEXT)
    findings += [f"{WORKFLOWS_TEXT}: does not name {pathlib.Path(f).name}"
                 for f in sorted(flows) if pathlib.Path(f).name not in doc]
    n = sum(len(v) for v in lanes.values())
    return findings, f"texts name every package ({n} recipes), lane and workflow ({len(flows)})"


# --- live ------------------------------------------------------------------------

def get(url, token=None):
    req = urllib.request.Request(url, headers={"User-Agent": "packaging-media-preservation texts-check"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8")
    except OSError as e:
        raise Unmeasured(f"{url}: {e}") from e


def fetch():
    """Every live text and build target this check compares."""
    got = {}
    try:
        gh = json.loads(get(GITHUB_API, os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")))
        got["github"] = gh.get("description") or ""
        copr = json.loads(get(COPR_API))
        got["copr_description"] = copr["description"] or ""
        got["copr_instructions"] = copr["instructions"] or ""
        got["copr_chroots"] = sorted(copr["chroot_repos"])
        meta = ET.fromstring(get(OBS_META))
    except (ValueError, KeyError, TypeError, ET.ParseError) as e:
        raise Unmeasured(f"unexpected answer: {e!r}") from e
    got["obs_title"] = meta.findtext("title") or ""
    got["obs_description"] = meta.findtext("description") or ""
    got["obs_repos"] = {r.get("name"): [a.text for a in r.findall("arch")] for r in meta.findall("repository")}
    if not got["copr_chroots"] or not got["obs_repos"]:
        raise Unmeasured("COPR or OBS listed no build target")
    return got


def norm(text):
    """Line ends and trailing blanks are not content; COPR and OBS do not keep them alike."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").strip("\n").split("\n"))


def targets(chroots, repos):
    """(source, distro, version) for every release, the architectures, and what is not understood."""
    rel, arches, unknown = set(), set(), []
    for c in chroots:
        m = re.fullmatch(r"(fedora|epel)-(\d+)-(x86_64|aarch64)", c)
        if m:
            rel.add(("COPR", "Fedora" if m[1] == "fedora" else "EPEL", m[2]))
            arches.add(m[3])
        elif m := re.fullmatch(r"(?:fedora-rawhide|rhel\+epel-\d+)-(x86_64|aarch64)", c):
            arches.add(m[1])        # rawhide has no number; rhel+epel-N is EPEL N again
        else:
            unknown.append(f"COPR chroot {c}")
    for name, archs in repos.items():
        if re.fullmatch(r"\d+\.\d+", name):
            rel.add(("OBS", "openSUSE Leap", name))
        elif re.fullmatch(r"openSUSE_Tumbleweed(?:_ARM)?", name):
            rel.add(("OBS", "openSUSE Tumbleweed", ""))
        elif m := re.fullmatch(r"xUbuntu_(\d+\.\d+)", name):
            rel.add(("OBS", "Ubuntu", m[1]))
        elif m := re.fullmatch(r"Debian_(\d+)", name):
            rel.add(("OBS", "Debian", m[1]))
        else:
            unknown.append(f"OBS repository {name}")
            continue
        for a in archs:
            if a in ("x86_64", "aarch64"):
                arches.add(a)
            else:
                unknown.append(f"OBS repository {name}: architecture {a}")
    return rel, arches, unknown


# text -> (which releases it must name, whether it must name the architectures)
RELEASE_RULES = (
    ("CHANGELOG.md", lambda src, distro: True, True),
    ("README.md", lambda src, distro: src == "OBS", False),
    (f"{DESCR}/obs-description.txt", lambda src, distro: src == "OBS", False),
    (f"{DESCR}/copr-description.md", lambda src, distro: distro == "EPEL", False),
)


def live(got, root=ROOT):
    findings = []
    for fname, key in LIVE.items():
        rel = f"{DESCR}/{fname}"
        want, have = norm(read(root, rel)), norm(got[key])
        if want != have:
            diff = list(difflib.unified_diff(want.split("\n"), have.split("\n"), f"{rel} (git)", f"{key} (live)",
                                             n=1, lineterm=""))
            more = f"\n    ... {len(diff) - 30} more diff lines" if len(diff) > 30 else ""
            findings.append(f"{rel}: the live text differs; publish the git copy, or take a deliberate "
                            f"live edit into git:\n    " + "\n    ".join(diff[:30]) + more)
    rel, arches, unknown = targets(got["copr_chroots"], got["obs_repos"])
    findings += [f"{u}: form not understood -- teach scripts/texts-check.py (targets) what it is" for u in unknown]
    for text, wanted, with_arch in RELEASE_RULES:
        body = read(root, text)
        for src, distro, version in sorted(rel):
            if wanted(src, distro) and not mentions(body, distro, version):
                findings.append(f"{text}: does not name {label(distro, version)} ({src} builds it)")
        if with_arch:
            findings += [f"{text}: does not name {a} ({'/'.join(sorted(arches))} are built)"
                         for a in sorted(arches) if a not in body]
    return findings, (f"live descriptions equal {DESCR}/ ({len(LIVE)} texts); every release COPR and OBS build "
                      f"({len(rel)}) and architecture ({len(arches)}) is named")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if argv else ""
    try:
        if mode == "offline" and len(argv) == 1:
            findings, ok = offline()
        elif mode == "live" and (len(argv) == 1 or (len(argv) == 3 and argv[1] == "--save")):
            got = fetch()
            if len(argv) == 3:
                out = pathlib.Path(argv[2])
                out.mkdir(parents=True, exist_ok=True)
                for fname, key in LIVE.items():
                    (out / fname).write_text(got[key].rstrip("\n") + "\n", encoding="utf-8")
                print(f"live texts saved to {out}")
            findings, ok = live(got)
        else:
            print(__doc__.split("\n\n")[1], file=sys.stderr)
            return 2
    except Unmeasured as e:
        print(f"texts-check: NOT MEASURED -- {e}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"texts-check: {f}")
    if findings:
        return 1
    print(f"texts-check: ok -- {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
