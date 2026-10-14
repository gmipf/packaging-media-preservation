#!/usr/bin/env python3
"""CHANGELOG.md against the recipes: what the log says ships is what the tree builds.

The log lists milestones only: a package, distribution or architecture added or
dropped. Its "Added", "Removed" and "Renamed" lines name packages and the
distributions they reached. Replayed oldest first, they must end in exactly the
set the tree builds:

  fedora/<pkg>/      Fedora, EPEL
  opensuse/<pkg>/    openSUSE
  ubuntu/<pkg>/      Debian, Ubuntu
  Formula/<pkg>.rb   macOS

So a new recipe without an "Added" line is red, and so is a recipe that is gone
while the log still ships it. The watchers never add or drop a package; a person
does, and the log is the step a person forgets. Without this check the log
would be one more copy that drifts.

Exit 0 when log and tree agree, 1 with one line per finding, 2 when the log or
the tree cannot be read at all (not measured is not clean).
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = "CHANGELOG.md"
LANES = {"fedora": ("Fedora", "EPEL"), "opensuse": ("openSUSE",), "ubuntu": ("Debian", "Ubuntu")}
DISTROS = ("Fedora", "EPEL", "openSUSE", "Debian", "Ubuntu", "macOS")

SEP = r"(?:, and |, | and )"
PKG = r"`[^`\s]+`"
PAIR = rf"{PKG} to {PKG}"
RE_HEAD = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")
RE_VERB = re.compile(r"^- (Added|Removed|Renamed)\b")
# The distribution list ends at the first period; a version number ("16.0")
# cannot hide in it, a line that tries does not parse and is reported.
RE_ADDREM = re.compile(rf"^- (?P<verb>Added|Removed) (?P<pkgs>{PKG}(?:{SEP}{PKG})*) on (?P<lanes>[^.]+)\.(?:\s|$)")
RE_RENAME = re.compile(rf"^- Renamed (?P<pairs>{PAIR}(?:{SEP}{PAIR})*) on (?P<lanes>[^.]+)\.(?:\s|$)")


def where(pkg, distro):
    if distro == "macOS":
        return f"Formula/{pkg}.rb"
    lane = next(d for d, names in LANES.items() if distro in names)
    return f"{lane}/{pkg}/"


def lines(text):
    """Yield (line number, kind, value) in order: kind "heading" or "bullet".

    HTML comments are dropped first (blanked, so line numbers stay true). A
    bullet starts with "- " in column 0; indented lines right after it continue
    it.
    """
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    cur, start = None, 0
    for n, line in enumerate(text.splitlines(), 1):
        if cur is not None and line[:1].isspace() and line.strip():
            cur += " " + line.strip()
            continue
        if cur is not None:
            yield start, "bullet", cur
            cur = None
        if line.startswith("## "):
            yield n, "heading", line.rstrip()
        elif line.startswith("- "):
            cur, start = line.rstrip(), n
    if cur is not None:
        yield start, "bullet", cur


def lanes_of(text, n, findings):
    out = []
    for word in re.split(SEP, text.strip()):
        if word in DISTROS:
            out.append(word)
        else:
            findings.append(f"{LOG}:{n}: unknown distribution {word!r} (known: {', '.join(DISTROS)})")
    return out


def parse(text):
    """Return ([(date, [(line, verb, args, lanes)])], findings), sections newest first as written."""
    sections, findings, last = [], [], None
    for n, kind, value in lines(text):
        if kind == "heading":
            m = RE_HEAD.match(value)
            if not m:
                findings.append(f"{LOG}:{n}: heading {value!r} is not '## YYYY-MM-DD'")
                continue
            date = m.group(1)
            if last is not None and date >= last:
                findings.append(f"{LOG}:{n}: {date} after {last} -- newest first, one section per day")
            last = date
            sections.append((date, []))
            continue
        bullet = value
        if not RE_VERB.match(bullet):
            continue
        m = RE_ADDREM.match(bullet) or RE_RENAME.match(bullet)
        if not m:
            findings.append(f"{LOG}:{n}: cannot read this line (form: see the comment at the top): {bullet[:90]}")
            continue
        if not sections:
            findings.append(f"{LOG}:{n}: entry before the first dated section")
            continue
        lanes = lanes_of(m.group("lanes"), n, findings)
        if "pairs" in m.groupdict():
            args = re.findall(r"`([^`]+)` to `([^`]+)`", m.group("pairs"))
            sections[-1][1].append((n, "Renamed", args, lanes))
        else:
            args = re.findall(r"`([^`]+)`", m.group("pkgs"))
            sections[-1][1].append((n, m.group("verb"), args, lanes))
    return sections, findings


def replay(sections):
    """Apply the entries oldest day first; return (shipped set, findings)."""
    state, findings = set(), []

    def add(n, pkg, distro):
        if (pkg, distro) in state:
            findings.append(f"{LOG}:{n}: adds `{pkg}` on {distro}, which an older line already added")
        state.add((pkg, distro))

    def drop(n, pkg, distro, verb):
        if (pkg, distro) not in state:
            findings.append(f"{LOG}:{n}: {verb.lower()} `{pkg}` on {distro}, which no older line added")
        state.discard((pkg, distro))

    for _date, entries in reversed(sections):
        for n, verb, args, lanes in entries:
            for distro in lanes:
                if verb == "Added":
                    for pkg in args:
                        add(n, pkg, distro)
                elif verb == "Removed":
                    for pkg in args:
                        drop(n, pkg, distro, verb)
                else:
                    for old, new in args:
                        drop(n, old, distro, verb)
                        add(n, new, distro)
    return state, findings


def tree(root=ROOT):
    """The (package, distribution) pairs the recipes in git build."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", "fedora", "opensuse", "ubuntu", "Formula"],
                         capture_output=True, text=True, check=True).stdout
    have = set()
    for f in filter(None, out.split("\0")):
        parts = f.split("/")
        if parts[0] in LANES and len(parts) >= 3:
            have.update((parts[1], d) for d in LANES[parts[0]])
        elif parts[0] == "Formula" and len(parts) == 2 and parts[1].endswith(".rb"):
            have.add((parts[1][:-3], "macOS"))
    return have


def compare(state, have):
    findings = []
    missing, stale = {}, {}
    for pkg, distro in have - state:
        missing.setdefault(pkg, []).append(distro)
    for pkg, distro in state - have:
        stale.setdefault(pkg, []).append(distro)
    order = {d: i for i, d in enumerate(DISTROS)}
    for pkg in sorted(missing):
        ds = sorted(missing[pkg], key=order.get)
        findings.append(f"{LOG}: `{pkg}` is built for {', '.join(ds)} ({where(pkg, ds[0])}), "
                        f"but no line adds it there")
    for pkg in sorted(stale):
        ds = sorted(stale[pkg], key=order.get)
        findings.append(f"{LOG}: the log still ships `{pkg}` on {', '.join(ds)}, but {where(pkg, ds[0])} "
                        f"is gone -- add a Removed or Renamed line")
    return findings


def check(text, have):
    sections, findings = parse(text)
    state, more = replay(sections)
    return findings + more + compare(state, have)


def main():
    try:
        text = (ROOT / LOG).read_text(encoding="utf-8")
    except OSError as e:
        print(f"{LOG}: cannot read it ({e}) -- not measured")
        return 2
    try:
        have = tree()
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"git ls-files failed ({e}) -- not measured")
        return 2
    if not have:
        print("no recipe found in fedora/, opensuse/, ubuntu/ or Formula/ -- the layout moved")
        return 2
    findings = check(text, have)
    for f in findings:
        print(f)
    if findings:
        return 1
    print(f"{LOG}: every recipe has its line ({len(have)} package/distribution pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
