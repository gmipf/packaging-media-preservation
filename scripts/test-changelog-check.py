#!/usr/bin/env python3
"""Decision tests for changelog-check.py -- run in CI on every push (check-repo.yml).

The functions under test are the script's own, unmodified, on the real
CHANGELOG.md and the real tree of this repository, edited in memory. Exit 1 if
any case disagrees. CHANGELOGCHECK=<path> runs the cases against another copy of
the script.
"""
import importlib.util
import os
import pathlib
import sys

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location("changelogcheck",
                                              os.environ.get("CHANGELOGCHECK", HERE / "changelog-check.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

failures = 0


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


def edited(old, new):
    s = LOG.replace(old, new, 1)
    assert s != LOG, f"test setup: {old!r} not found in CHANGELOG.md"
    return s


def has(findings, *words):
    return any(all(w in f for w in words) for f in findings)


LOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
TREE = c.tree()
DREAMDUMP = "- Added `dreamdump` on Fedora, EPEL, openSUSE, Debian and Ubuntu. The"

# --- the tree as the check sees it ---------------------------------------------
check("tree: 9 Linux packages x 5 distributions + 2 formulae", len(TREE), 47)
check("tree: ubuntu/<pkg> builds Debian", ("dreamdump", "Debian") in TREE, True)
check("tree: ubuntu/<pkg> builds Ubuntu", ("dreamdump", "Ubuntu") in TREE, True)
check("tree: fedora/<pkg> builds EPEL", ("aaru5", "EPEL") in TREE, True)
check("tree: Formula/<pkg>.rb is macOS", ("discimagecreator", "macOS") in TREE, True)
check("tree: no formula, no macOS", ("aaru", "macOS") in TREE, False)
check("tree: a lane's README is no package", ("README.md", "openSUSE") in TREE, False)

# --- green ---------------------------------------------------------------------
check("the real log against the real tree", c.check(LOG, TREE), [])

# --- red: log and tree disagree --------------------------------------------------
f = c.check(edited(DREAMDUMP, "- Something about dreamdump. The"), TREE)
check("a recipe with no Added line is named", has(f, "`dreamdump`", "Fedora, EPEL, openSUSE, Debian, Ubuntu",
                                                  "no line adds it"), True)
f = c.check(LOG, TREE | {("newtool", "Fedora"), ("newtool", "EPEL")})
check("a new recipe in the tree is named", has(f, "`newtool`", "Fedora, EPEL", "fedora/newtool/"), True)
f = c.check(LOG, TREE - {("redumper-gui", "Debian"), ("redumper-gui", "Ubuntu")})
check("a recipe that is gone while the log ships it", has(f, "`redumper-gui`", "Debian, Ubuntu",
                                                          "ubuntu/redumper-gui/", "Removed or Renamed"), True)
f = c.check(LOG, TREE - {("redumper", "macOS")})
check("a formula that is gone", has(f, "`redumper`", "Formula/redumper.rb"), True)

# --- red: the log contradicts itself ----------------------------------------------
f = c.check(edited("## 2026-07-02", "## 2026-07-20"), TREE)
check("dates out of order", has(f, "2026-07-20 after 2026-07-03", "newest first"), True)
f = c.check(edited("## 2026-07-02", "## 2026-07-03"), TREE)
check("the same day twice", has(f, "2026-07-03 after 2026-07-03"), True)
f = c.check(edited("## 2026-07-02", "## July 2nd"), TREE)
check("a heading that is no date", has(f, "'## July 2nd'", "YYYY-MM-DD"), True)
f = c.check(edited("## 2026-10-13\n", "## 2026-10-13\n\n- Removed `ghost` on Fedora.\n"), TREE)
check("removing what was never added", has(f, "removed `ghost` on Fedora", "no older line added"), True)
f = c.check(edited("## 2026-10-13\n", "## 2026-10-13\n\n- Added `redumper` on Fedora.\n"), TREE)
check("adding what is already there", has(f, "adds `redumper` on Fedora", "already added"), True)
f = c.check(edited("## 2026-10-13\n", "## 2026-10-13\n\n- Renamed `ghost` to `spook` on Fedora.\n"), TREE)
check("renaming what was never added", has(f, "renamed `ghost` on Fedora", "no older line added"), True)
check("... and the new name is then shipped without a recipe", has(f, "`spook`", "fedora/spook/ is gone"), True)

# --- red: a line the check cannot read is a finding, never skipped ------------------
f = c.check(edited(DREAMDUMP, "- Added dreamdump on Fedora, EPEL, openSUSE, Debian and Ubuntu. The"), TREE)
check("a package without backticks", has(f, "cannot read this line"), True)
check("... and the package then counts as missing", has(f, "`dreamdump`", "no line adds it"), True)
f = c.check(edited(DREAMDUMP, "- Added `dreamdump` on Fedora, EPEL, openSUSE Leap 16.0, Debian and Ubuntu. The"),
            TREE)
check("a version number in the distribution list", has(f, "cannot read this line"), True)
f = c.check(edited(DREAMDUMP, "- Added `dreamdump` on Fedora, EPEL, Arch, openSUSE, Debian and Ubuntu. The"), TREE)
check("an unknown distribution", has(f, "unknown distribution 'Arch'"), True)
f = c.check("- Added `redumper` on Fedora.\n\n" + LOG, TREE)
check("an entry before the first date", has(f, "entry before the first dated section"), True)

# --- the reader ---------------------------------------------------------------------
s, f = c.parse("## 2026-01-02\n\n- Added `a` and\n  `b` on Fedora\n  and EPEL. Text.\n")
check("a wrapped line reads as one", (s, f), ([("2026-01-02", [(3, "Added", ["a", "b"], ["Fedora", "EPEL"])])], []))
s, f = c.parse("## 2026-01-02\n\n- Added `a`, `b`, and `c` on Fedora. Text.\n")
check("an Oxford comma", s[0][1][0][2], ["a", "b", "c"])
s, f = c.parse("## 2026-01-02\n\n- Renamed `a` to `b` and `c` to `d` on Ubuntu. Text.\n")
check("two renames in one line", s[0][1][0][2], [("a", "b"), ("c", "d")])
s, f = c.parse("<!--\n- Added `x` on Fedora.\n-->\n## 2026-01-02\n\n- Added `y` on Fedora.\n")
check("lines inside a comment are not entries, line numbers stay true", (s, f),
      ([("2026-01-02", [(6, "Added", ["y"], ["Fedora"])])], []))
s, f = c.parse("## 2026-01-02\n\n- Ubuntu moved from the PPA to OBS. Added `x` on Fedora.\n")
check("free text is not an entry", (s, f), ([("2026-01-02", [])], []))

# --- main: not measured is not clean --------------------------------------------------
saved_root, saved_tree = c.ROOT, c.tree
c.ROOT = pathlib.Path("/nonexistent-changelog-check")
check("no CHANGELOG.md: exit 2", c.main(), 2)
c.ROOT, c.tree = saved_root, (lambda: set())
check("no recipe found: exit 2", c.main(), 2)
c.tree = saved_tree
check("the real repository: exit 0", c.main(), 0)

print(f"\n{'FAILED' if failures else 'all passed'}: {failures} case(s) disagree")
sys.exit(1 if failures else 0)
