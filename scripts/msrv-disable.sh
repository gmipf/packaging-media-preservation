#!/usr/bin/env bash
# msrv-disable.sh <declared-msrv>
#
# Implements decision D2/(c) of 2026-07-19 for the COPR lane: when an upstream
# release raises the Rust floor above a target we ship to, that target is
# switched OFF for the new version and the last package built for it stays in the
# repository and keeps being delivered. The alternative -- letting it go red
# forever -- was rejected for a reason worth repeating: a permanently red build
# gets ignored exactly like a check that never goes red.
#
# WHY THIS EXISTS AT ALL (the earlier reasoning was measured, but not far enough).
# On 2026-07-20 this was deferred as "protects no artifact today", and for the OBS
# half that is true: Debian_12 and xUbuntu_22.04/24.04 carry no redumper-gui .deb
# at all -- measured, zero binaries. But the search space was larger than the
# measurement. epel-8/9/10 sit at rustc 1.92, which is EXACTLY the floor with zero
# headroom, and they carry six real packages (redumper-gui-1.0.2-1.el{8,9,10} on
# x86_64 and aarch64). The day upstream declares 1.93, all three fall at once.
#
# THE SPLIT THAT MAKES THIS DOABLE: the COPR side of "switch a target off" is the
# `targets:` list in .packit.yaml, which is a plain git edit -- no token, no
# credential, nothing outside this repository. The OBS side is `build disable` in
# the package meta, which no OBS token can write. So the COPR half is automated
# here and the OBS half stays the declared exception it always was.
#
# Exit codes (the watcher branches on these):
#   0  floor holds, or nothing to do        -- no changes made
#  10  COPR targets disabled                -- changes made, commit them
#  11  COPR disabled AND obs rows fell too  -- changes made, but a human must run
#                                              the OBS half; the caller must fail
#                                              the run so the mail actually goes out
#   2  bad usage / inventory unreadable
#   3  cannot express the change             -- see the wildcard note below
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGETS="$REPO/scripts/rust-targets.tsv"
PACKIT="$REPO/.packit.yaml"

DECL="${1:-}"
if [ -z "$DECL" ]; then
    echo "usage: $0 <declared-msrv>   e.g. $0 1.93" >&2
    exit 2
fi
# Refuse to guess. An unreadable inventory is not "nothing to disable".
for f in "$TARGETS" "$PACKIT"; do
    [ -r "$f" ] || { echo "ERROR: cannot read $f -- refusing to decide anything" >&2; exit 2; }
done

python3 - "$DECL" "$TARGETS" "$PACKIT" <<'PY'
import re, sys, datetime

decl_s, targets_p, packit_p = sys.argv[1], sys.argv[2], sys.argv[3]

def ver(s):
    return tuple(int(x) for x in s.strip().split(".")[:2])

rows = []
with open(targets_p, encoding="utf-8") as fh:
    for n, line in enumerate(fh):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) < 4:
            continue
        rows.append({"n": n, "lane": f[0], "target": f[1], "rustc": f[2],
                     "status": f[3], "raw": line})

ship = [r for r in rows if r["status"] == "ship"]
if not ship:
    print("ERROR: no `ship` rows in the inventory -- refusing to derive a floor", file=sys.stderr)
    sys.exit(2)

decl = ver(decl_s)
floor = min(ver(r["rustc"]) for r in ship)
fs = "%d.%d" % floor
print(f"declared MSRV {decl_s}, derived floor {fs}")

if decl <= floor:
    print("floor holds -- every shipping target can still build this release")
    sys.exit(0)

falling = [r for r in ship if ver(r["rustc"]) < decl]
copr_fall = [r for r in falling if r["lane"] == "copr"]
obs_fall  = [r for r in falling if r["lane"] == "obs"]
for r in falling:
    print(f"  falls: {r['lane']}/{r['target']} (rustc {r['rustc']})")

# ---- map a COPR row to the packit target wildcard that carries it ----
# .packit.yaml does not list chroots one by one; it uses `epel-all-<arch>` and
# `fedora-all-<arch>`. That is deliberate (COPR resolves them at build time, which
# is how F44 appeared and F42 dropped out without us touching anything), and it
# has a consequence: a wildcard can only be removed WHOLE.
def family(target):
    if target.startswith("epel-"):
        return "epel-all"
    if target.startswith("fedora"):
        return "fedora-all"
    return None

fams = {}
for r in copr_fall:
    fam = family(r["target"])
    if fam is None:
        print(f"ERROR: no packit wildcard known for copr target {r['target']}", file=sys.stderr)
        sys.exit(3)
    fams.setdefault(fam, []).append(r)

# A partial fall cannot be expressed by deleting a wildcard: dropping `epel-all`
# when only epel-8 fell would also take epel-9 and epel-10, which still build.
# Expressing it would mean expanding the wildcard into explicit chroots, and that
# means knowing the full chroot list -- a network call and a second source of
# truth. This case has never occurred (all three EPEL rows sit at the same rustc),
# so it fails LOUDLY rather than doing something half-right and calling it done.
for fam, members in fams.items():
    total = [r for r in ship if r["lane"] == "copr" and family(r["target"]) == fam]
    if len(members) != len(total):
        kept = [r["target"] for r in total if r not in members]
        print(f"ERROR: only part of the `{fam}` family falls below {decl_s}.", file=sys.stderr)
        print(f"       falling: {[r['target'] for r in members]}", file=sys.stderr)
        print(f"       still fine: {kept}", file=sys.stderr)
        print("       .packit.yaml carries a wildcard, so removing it would also drop", file=sys.stderr)
        print("       the targets that still build. Expand the wildcard into explicit", file=sys.stderr)
        print("       chroots by hand, then re-run. Refusing to guess.", file=sys.stderr)
        sys.exit(3)

changed = False

# ---- 1. remove the wildcard lines from the redumper-gui job ONLY ----
# The same four target lines appear in all eight jobs. Editing the file globally
# would silently disable EPEL for every package here, and only redumper-gui is
# built from Rust source. So the block is located first and the edit is bounded
# to it.
lines = open(packit_p, encoding="utf-8").read().split("\n")
start = None
for i, l in enumerate(lines):
    if re.match(r"\s*packages:\s*\[redumper-gui\]\s*$", l):
        start = i
        break
if start is None:
    print("ERROR: could not find the redumper-gui job in .packit.yaml", file=sys.stderr)
    sys.exit(2)
end = len(lines)
for i in range(start + 1, len(lines)):
    if re.match(r"\s*-\s*job:", lines[i]):
        end = i
        break

drop = set()
for fam in fams:
    for arch in ("x86_64", "aarch64"):
        drop.add(f"{fam}-{arch}")

kept_lines, removed = [], []
for i, l in enumerate(lines):
    if start <= i < end:
        m = re.match(r"\s*-\s*([a-z0-9._+-]+)\s*$", l)
        if m and m.group(1) in drop:
            removed.append(m.group(1))
            continue
    kept_lines.append(l)

if removed:
    open(packit_p, "w", encoding="utf-8").write("\n".join(kept_lines))
    print(f"  .packit.yaml: removed {', '.join(sorted(removed))} from the redumper-gui job")
    changed = True
else:
    print("ERROR: the wildcards to drop were not present in the redumper-gui job "
          f"({sorted(drop)}) -- inventory and packit config disagree", file=sys.stderr)
    sys.exit(3)

# ---- 2. flip the inventory rows ship -> out, in the same change ----
# Two statements of one fact drifting apart is what rust-targets.tsv exists to
# prevent, so the row moves in the same commit as the target it describes.
today = datetime.date.today().isoformat()
src = open(targets_p, encoding="utf-8").read().split("\n")
for r in copr_fall:
    old = src[r["n"]]
    f = old.split("\t")
    f[3] = "out"
    note = f"MSRV rose to {decl_s} on {today}; last build kept in the repo (D2/c)"
    if len(f) >= 6:
        f[5] = note
    else:
        f = f[:5] + [note]
    src[r["n"]] = "\t".join(f)
    print(f"  rust-targets.tsv: {r['target']} ship -> out")
open(targets_p, "w", encoding="utf-8").write("\n".join(src))
changed = True

if obs_fall:
    print("")
    print("OBS targets fell too and CANNOT be switched off from here:")
    for r in obs_fall:
        print(f"  {r['target']} (rustc {r['rustc']})")
    print("`build disable` writes the OBS package meta and no OBS token can do that")
    print("(runservice/branch/release/rebuild/workflow only). Run it by hand:")
    print("  osc meta pkg -e home:gmipf:media-preservation redumper-gui")
    sys.exit(11)

sys.exit(10 if changed else 0)
PY
