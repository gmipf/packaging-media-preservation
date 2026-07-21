#!/usr/bin/env bash
# msrv-sync.sh [--check]
#
# Writes the derived Rust floor into every recipe that DECLARES it.
#
# WHY THIS EXISTS. rust-targets.tsv was introduced to end "one fact, two places":
# the floor is the lowest rustc among the `ship` rows, and rust-vendor-tarball.sh
# DERIVES it instead of restating it. That fix stopped one file short. The number
# is also a literal in the recipes -- rpm cannot read a TSV, and neither can
# debian/control -- and NOTHING wrote those. msrv-disable.sh flips inventory rows
# and edits .packit.yaml; it never touched a recipe.
#
# 🔴 That gap is not cosmetic, and it is the reason "the resolver protects the
# artifact" was only half true. `BuildRequires: rust >= 1.92` says "anything from
# 1.92 up may build". If upstream needs 1.94 and the literal stays at 1.92, every
# target still SATISFIES it: the build starts and dies in the middle of cargo with
# a message about some crate. The clean `unresolvable` state -- the one that makes
# a below-floor target switch itself off, with no package meta and no credential
# -- only ever happens if this number is raised. This script raises it.
#
# ⭐ THE FILE LIST IS DISCOVERED, NEVER DECLARED. A hand-written list is exactly
# how the openSUSE spec and debian/control came to hold an unchecked copy while
# only the Fedora spec was guarded. Every file under the lane directories is
# searched for a DECLARATION of the floor; whatever is found is what gets written.
# A fourth copy added tomorrow is covered without editing this script.
#
# Exit codes:
#   0  every declaration already states the floor -- nothing written
#  10  at least one declaration was rewritten (caller must commit)
#   2  the inventory is unreadable, or NOT ONE declaration was found anywhere
#      (an empty search result is not "all clear" -- it is a broken search)
#   1  --check only: a declaration disagrees with the floor
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS="$REPO/scripts/rust-targets.tsv"

MODE="${1:-}"
case "$MODE" in
    ""|--check) : ;;
    *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

[ -r "$TARGETS" ] || { echo "ERROR: cannot read $TARGETS -- refusing to guess a floor" >&2; exit 2; }

python3 - "$REPO" "$TARGETS" "$MODE" <<'PY'
import os, re, sys

repo, targets_p, mode = sys.argv[1], sys.argv[2], sys.argv[3]
check_only = (mode == "--check")

# ---- the one source of the number ----
rows = []
with open(targets_p, encoding="utf-8") as fh:
    for line in fh:
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) >= 4 and f[3] == "ship":
            rows.append(f[2])
if not rows:
    print("ERROR: no `ship` rows in the inventory -- there is no floor to derive", file=sys.stderr)
    sys.exit(2)


def vt(s):
    return tuple(int(x) for x in s.split("."))


floor = min(rows, key=vt)
if not re.fullmatch(r"\d+\.\d+", floor):
    print(f"ERROR: derived floor {floor!r} is not a MAJOR.MINOR version", file=sys.stderr)
    sys.exit(2)

# ---- the declarations we know how to write ----
# Anchored to DECLARATION syntax, so prose that merely mentions a version is not
# touched. Prose drifts too, but silently rewriting sentences is a different and
# much worse failure mode than leaving them to the doc checks in status.sh.
PATTERNS = [
    # rpm:  BuildRequires:  rust >= 1.92
    re.compile(r"^(BuildRequires:\s+rust\s*>=\s*)(\d+\.\d+)(\s*)$"),
    # deb:  cargo (>= 1.92),   /   rustc (>= 1.92),
    re.compile(r"^(\s*(?:cargo|rustc)\s*\(>=\s*)(\d+\.\d+)(\).*)$"),
]

LANES = ("fedora", "opensuse", "ubuntu")
SKIP_SUFFIX = (".tar.gz", ".tar.xz", ".zip", ".png", ".gz")

hits = 0
changed = []
disagree = []

for lane in LANES:
    root = os.path.join(repo, lane)
    if not os.path.isdir(root):
        continue
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            if fn.endswith(SKIP_SUFFIX):
                continue
            path = os.path.join(dirpath, fn)
            try:
                src = open(path, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            lines = src.split("\n")
            touched = False
            for i, line in enumerate(lines):
                for pat in PATTERNS:
                    m = pat.match(line)
                    if not m:
                        continue
                    hits += 1
                    rel = os.path.relpath(path, repo)
                    if m.group(2) == floor:
                        break
                    disagree.append((rel, i + 1, m.group(2)))
                    if not check_only:
                        new = m.group(1) + floor + m.group(3)
                        # An edit that reports success without changing anything is
                        # the failure this assert exists for.
                        assert new != line, f"{rel}:{i+1} substitution was a no-op"
                        lines[i] = new
                        touched = True
                        changed.append((rel, i + 1, m.group(2)))
                    break
            if touched:
                open(path, "w", encoding="utf-8").write("\n".join(lines))

# An empty result looks exactly like "nothing to do". It is not: it means the
# search is broken, and a broken search here silently stops raising the floor.
if hits == 0:
    print("ERROR: not one Rust floor declaration found under " + "/, ".join(LANES) + "/.",
          file=sys.stderr)
    print("       Either the recipes stopped declaring it or the patterns rotted.",
          file=sys.stderr)
    sys.exit(2)

print(f"derived floor {floor} (lowest rustc among the ship rows); {hits} declaration(s) inspected")

if check_only:
    if disagree:
        for rel, ln, got in disagree:
            print(f"  DRIFT {rel}:{ln} declares {got}, floor is {floor}")
        sys.exit(1)
    print("  all declarations state the floor")
    sys.exit(0)

if changed:
    for rel, ln, old in changed:
        print(f"  {rel}:{ln}  {old} -> {floor}")
    sys.exit(10)

print("  all declarations already state the floor -- nothing written")
sys.exit(0)
PY
