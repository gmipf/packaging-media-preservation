#!/usr/bin/env bash
# add-repo.sh <repo-name> <upstream-project> <upstream-repo> <rustc> [--apply]
#
#   scripts/obs/add-repo.sh xUbuntu_26.10 Ubuntu:26.10 universe-update 1.95
#
# Adds a distribution to the OBS project. Dry run unless --apply is given.
#
# WHY THIS EXISTS. Adding a <repository> block writes the OBS PROJECT META, and no
# OBS token can do that (`osc token --operation` knows runservice / branch /
# release / rebuild / workflow, and there is no separate API password -- it is the
# same account). That is measured and it is not going to change, so this step keeps
# a human. Task #42 point 3, the one part that stays.
#
# 🔴 BUT THE HUMAN'S REAL PROBLEM WAS NEVER THE XML BLOCK. Measured 2026-07-22
# against the live project: the deb repositories are DISABLED at project level and
# ENABLED per package. Adding a new Ubuntu series is therefore
#
#     1 <repository> block  +  1 project-level <disable>  +  8 package metas
#
# and if you write the block and stop, you get a repository that exists, builds
# nothing, and looks exactly like OBS being slow. That is a silent failure with a
# nine-step recipe, which is the worst possible thing to leave to memory.
#
# ⭐ So the split is: the DECISION stays human (adopting a release is a judgement
# call), the MECHANICS do not. This script does the nine writes, derives which
# packages get an enable FROM THE FILESYSTEM rather than a list, and decides
# redumper-gui from data instead of asking.
#
# The rustc version is a required ARGUMENT and not looked up, on purpose:
# rust-targets.tsv says its numbers are measured in clean containers, not read off
# a distribution's website. Measure it, then pass it.
#
# Exit codes:
#   0  dry run printed, or --apply succeeded and verified
#   2  bad usage, unreadable inventory, upstream project/repository not found,
#      or the repository already exists
#   3  applied, but the verification read-back disagreed -- look before retrying
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${OBS_PROJECT:-home:gmipf:media-preservation}"
TARGETS="$REPO/scripts/rust-targets.tsv"

if [ "$#" -lt 4 ]; then
    sed -n '2,4p' "${BASH_SOURCE[0]}" | sed 's/^# \?//' >&2
    exit 2
fi
NAME="$1"; UP_PRJ="$2"; UP_REPO="$3"; RUSTC="$4"; APPLY="${5:-}"

case "$APPLY" in ""|--apply) : ;; *) echo "unknown flag: $APPLY" >&2; exit 2 ;; esac
[[ "$RUSTC" =~ ^[0-9]+\.[0-9]+$ ]] || { echo "rustc must be MAJOR.MINOR, got '$RUSTC'" >&2; exit 2; }
[ -r "$TARGETS" ] || { echo "cannot read $TARGETS -- refusing to decide anything" >&2; exit 2; }

# --- does the upstream repository actually exist? ------------------------------
# An unverified path produces a repository that is permanently `broken`, which
# reads like our mistake somewhere else entirely. Ask OBS before writing.
if ! UP_META=$(osc meta prj "$UP_PRJ" 2>/dev/null); then
    echo "ERROR: OBS does not know a project '$UP_PRJ' (or the API is unreachable)." >&2
    echo "       Nothing was written." >&2
    exit 2
fi
# 🐛 NOT `printf "%s" "$UP_META" | grep -q ...`. Measured 2026-07-22, 5 runs out of
# 5: that pipeline returns **141** on a HIT. `grep -q` exits at the first match,
# printf still has ~74 KB of project meta to push into a 64 KB pipe, takes SIGPIPE,
# and `pipefail` promotes the hit to a failure. The script then refuses a
# repository that exists -- and does so while PRINTING it in the "it offers" list
# below, because sed reads its input to the end and does not race.
# ⭐ This exact trap is already documented in this repository (status.sh, the
# auto-tracking check) WITH an exemption: "the other six sites feed grep from a
# printf builtin, which writes in one go and does not race". That exemption was
# measured on short strings. At 74 KB it is simply false. An exemption needs its
# own boundary measured, or it quietly becomes the rule's loophole.
# The builtin match has no pipe, no second process and no exit code to promote.
if [[ "$UP_META" != *"<repository name=\"${UP_REPO}\""* ]]; then
    echo "ERROR: project '$UP_PRJ' has no repository '$UP_REPO'. It offers:" >&2
    printf '%s' "$UP_META" | sed -n 's/.*<repository name="\([^"]*\)".*/         \1/p' >&2
    exit 2
fi

OUR_META=$(osc meta prj "$PROJECT")

APPLY="$APPLY" NAME="$NAME" UP_PRJ="$UP_PRJ" UP_REPO="$UP_REPO" RUSTC="$RUSTC" \
PROJECT="$PROJECT" OUR_META="$OUR_META" \
python3 - "$REPO" "$TARGETS" <<'PY'
import datetime, os, re, subprocess, sys

repo, targets_p = sys.argv[1], sys.argv[2]
name    = os.environ["NAME"]
up_prj  = os.environ["UP_PRJ"]
up_repo = os.environ["UP_REPO"]
rustc   = os.environ["RUSTC"]
project = os.environ["PROJECT"]
meta    = os.environ["OUR_META"]
apply_  = os.environ["APPLY"] == "--apply"

RUST_PKG = "redumper-gui"


def vt(s):
    return tuple(int(x) for x in s.split("."))


if f'<repository name="{name}"' in meta:
    print(f"ERROR: {project} already has a repository named {name}.", file=sys.stderr)
    print("       Nothing was written. Remove it first if you really mean to redo it.",
          file=sys.stderr)
    sys.exit(2)

# --- 1. the floor decides whether the Rust package ships there ------------------
# NOT "add it as ship and see": a new row marked ship with a LOWER rustc would drag
# the derived floor down, and msrv-sync.sh would then lower BuildRequires in every
# recipe -- silently shipping a package that cannot compile. The floor is a
# property of what upstream needs; a target either clears it or it does not.
rows = []
with open(targets_p, encoding="utf-8") as fh:
    tsv_lines = fh.read().split("\n")
for line in tsv_lines:
    if line.startswith("#") or not line.strip():
        continue
    f = line.split("\t")
    if len(f) >= 4 and f[3] == "ship":
        rows.append(f[2])
floor = min(rows, key=vt)
ships = vt(rustc) >= vt(floor)
status = "ship" if ships else "out"

# --- 2. is this a lane whose repositories are project-disabled? -----------------
# Derived, not assumed: look at the SIBLINGS from the same upstream family
# (Ubuntu:*, Debian:*, openSUSE:*) and copy how they are configured. That is the
# fact that bites -- deb repositories are disabled at project level and enabled per
# package, rpm ones are not -- and reading it off the live project means a change
# in that convention cannot silently invalidate this script.
family = up_prj.split(":")[0]
sib_of_family = []
for block in re.findall(r"<repository name=\"[^\"]+\">.*?</repository>", meta, re.S):
    rn = re.search(r'name="([^"]+)"', block).group(1)
    if re.search(rf'<path project="{re.escape(family)}:', block):
        sib_of_family.append(rn)

disabled = set(re.findall(r'<build>.*?</build>', meta, re.S))
proj_disabled = set(re.findall(r'<disable repository="([^"]+)"/>', "".join(disabled)))
needs_project_disable = bool(sib_of_family) and all(s in proj_disabled for s in sib_of_family)

if not sib_of_family:
    print(f"NOTE: no existing repository points at {family}:* -- this is a new lane.")
    print("      Falling back to: no project-level disable, no per-package enables.")
    print("      Check that by hand before --apply if that is not what you expect.")

# --- 3. which packages get an <enable>? ----------------------------------------
# From the FILESYSTEM: every package with a debian/ recipe. A hand-written list is
# how two of four Rust-floor copies stayed unguarded for weeks; the same mistake
# here costs a package that silently never builds for the new series.
pkgs = sorted(
    d for d in os.listdir(os.path.join(repo, "fedora"))
    if os.path.isfile(os.path.join(repo, "ubuntu", d, "debian", "control"))
)
if needs_project_disable:
    enable_in = [p for p in pkgs if p != RUST_PKG or ships]
    skipped = [p for p in pkgs if p not in enable_in]
else:
    enable_in, skipped = [], []

arches = re.findall(r"<arch>([^<]+)</arch>",
                    re.search(rf'<repository name="{re.escape(sib_of_family[0])}">.*?</repository>',
                              meta, re.S).group(0)) if sib_of_family else ["x86_64", "aarch64"]

block = (f'  <repository name="{name}">\n'
         f'    <path project="{up_prj}" repository="{up_repo}"/>\n'
         + "".join(f"    <arch>{a}</arch>\n" for a in arches)
         + "  </repository>\n")

print(f"repository   {name}  ->  {up_prj}/{up_repo}   arches: {', '.join(arches)}")
print(f"rust floor   {floor} (derived) vs measured {rustc}  ->  rust-targets.tsv row `{status}`")
print(f"project      {'add <disable> (this lane is per-package enabled)' if needs_project_disable else 'no project-level disable (rpm-style lane)'}")
if enable_in:
    print(f"packages     enable in {len(enable_in)}: {', '.join(enable_in)}")
if skipped:
    print(f"             NOT enabled: {', '.join(skipped)}  (below the Rust floor)")
print()

# --- 4. build the new metas ----------------------------------------------------
new_meta = meta.replace("</project>", block + "</project>")
assert new_meta != meta, "repository block insertion was a no-op"
if needs_project_disable:
    if "<build>" in new_meta:
        m2 = new_meta.replace("<build>", f'<build>\n    <disable repository="{name}"/>', 1)
    else:
        m2 = new_meta.replace("  <repository ",
                              f'  <build>\n    <disable repository="{name}"/>\n  </build>\n  <repository ', 1)
    assert m2 != new_meta, "project-level disable insertion was a no-op"
    new_meta = m2

if not apply_:
    print("--- project meta (dry run, nothing written) ---")
    print(new_meta)
    print("--- rust-targets.tsv row ---")
    print("\t".join(["obs", name, rustc, status, datetime.date.today().isoformat(),
                     "added with scripts/obs/add-repo.sh"]))
    if enable_in:
        print(f"--- and <enable repository=\"{name}\"/> in {len(enable_in)} package metas ---")
    print()
    print("Re-run with --apply to write this. Nothing has been changed.")
    sys.exit(0)


def osc_meta(kind, args, payload=None):
    cmd = ["osc", "meta", kind] + args
    if payload is not None:
        cmd += ["-F", "-"]
        return subprocess.run(cmd, input=payload, text=True, capture_output=True)
    return subprocess.run(cmd, text=True, capture_output=True)


r = osc_meta("prj", [project], new_meta)
if r.returncode != 0:
    print("ERROR: writing the project meta failed:", r.stderr.strip(), file=sys.stderr)
    sys.exit(3)
print(f"  project meta written ({name} added)")

for p in enable_in:
    cur = osc_meta("pkg", [project, p])
    if cur.returncode != 0:
        print(f"ERROR: cannot read package meta for {p}: {cur.stderr.strip()}", file=sys.stderr)
        sys.exit(3)
    src = cur.stdout
    if f'<enable repository="{name}"/>' in src:
        print(f"  {p}: already enabled")
        continue
    if "<build>" in src:
        out = src.replace("<build>", f'<build>\n    <enable repository="{name}"/>', 1)
    else:
        out = src.replace("</package>",
                          f'  <build>\n    <enable repository="{name}"/>\n  </build>\n</package>')
    assert out != src, f"{p}: enable insertion was a no-op"
    w = osc_meta("pkg", [project, p], out)
    if w.returncode != 0:
        print(f"ERROR: writing package meta for {p} failed: {w.stderr.strip()}", file=sys.stderr)
        sys.exit(3)
    print(f"  {p}: enabled")

# --- 5. the inventory row, in the same operation -------------------------------
row = "\t".join(["obs", name, rustc, status, datetime.date.today().isoformat(),
                 "added with scripts/obs/add-repo.sh"])
last = max(i for i, l in enumerate(tsv_lines) if l.startswith("obs\t"))
tsv_lines.insert(last + 1, row)
open(targets_p, "w", encoding="utf-8").write("\n".join(tsv_lines))
print(f"  rust-targets.tsv: row added ({status})")

# --- 6. read back. Writing is not the same as having written. ------------------
back = subprocess.run(["osc", "meta", "prj", project], text=True, capture_output=True).stdout
if f'<repository name="{name}"' not in back:
    print("ERROR: read-back does not show the repository. Look before retrying.", file=sys.stderr)
    sys.exit(3)
missing = []
for p in enable_in:
    m = subprocess.run(["osc", "meta", "pkg", project, p], text=True, capture_output=True).stdout
    if f'<enable repository="{name}"/>' not in m:
        missing.append(p)
if missing:
    print(f"ERROR: read-back shows no enable for: {', '.join(missing)}", file=sys.stderr)
    sys.exit(3)
print("  read-back ok")

# --- 7. what this script deliberately does NOT do ------------------------------
# Prose. Three documents name the supported series, and they drift INDEPENDENTLY;
# rewriting sentences automatically is a worse failure than leaving them. So they
# are CHECKED and reported, never edited.
print()
print("Still yours -- the series is named in prose in three places that drift apart:")
for rel in ("ubuntu/README.md", "opensuse/README.md"):
    path = os.path.join(repo, rel)
    try:
        hit = name in open(path, encoding="utf-8").read()
    except OSError:
        hit = False
    print(f"  {'ok  ' if hit else 'TODO'} {rel}")
print("  TODO OBS project description (osc meta prj -e) -- it lists the series too")
print("       and is the copy no check in this repository can see.")
PY
