#!/bin/bash
#
# gen-deb.sh <tool> [<tool> ...]        (no args = every Debian-enabled tool)
#
# Generate the three files OBS needs to build the Debian packages of <tool>:
#
#   opensuse/<tool>/debian.tar.gz   the debian/ dir, MINUS the changelog
#   opensuse/<tool>/<tool>.dsc      the debtransform template
#   opensuse/<tool>/_service        the deb block, rewritten between markers
#
# OBS fetches all of them itself (download_url), so git stays the single source
# of truth exactly as it is for the RPM lane. The debian/ recipe is NOT copied:
# ubuntu/<tool>/debian/ remains the one place it lives, and this script only
# repackages it.
#
#
# WHY A TARBALL, AND NOT ONE download_url PER debian/ FILE
#
# The flat route debtransform also offers -- a `debian.<file>` per file in the
# package dir -- looks simpler and is WRONG: HTTP carries no mode bit, so
# debian/rules would arrive 0644 and land 0644 INSIDE the source package. It
# still builds on Debian 12 and 13, because their dpkg-source silently chmods
# debian/rules on extract. Newer dpkg (1.23.7, measured on Fedora 43) does not,
# so the package is malformed and merely happens to work -- until it doesn't.
# A tarball carries the mode, and is correct by construction.
#
#
# WHY THE CHANGELOG IS *NOT* IN THAT TARBALL
#
# It is the only file in debian/ that moves with every version bump, and it
# needs no mode bit. Leaving it out keeps debian.tar.gz -- a BINARY blob in git
# -- stable across bumps: it changes only when the recipe itself changes. mpf
# alone bumps ~4x a day; a blob per bump would be noise in the history for no
# gain. It is fetched flat instead, straight from ubuntu/<tool>/debian/changelog.
# debtransform accepts the mix; it only refuses a file present in BOTH places.
#
#
# WHY THE .orig TARBALL COMES FROM LAUNCHPAD
#
# It has to be assembled (aaru merges two upstream tarballs, mpf three binaries)
# and no OBS source service can do that -- OBS can only download files. The PPA
# lane already assembles it, and Launchpad stores one immutable copy per upstream
# version under a series-independent URL. Reusing it costs nothing, needs no
# release asset of our own (mpf's orig is 88 MB and would land there ~4x a day),
# and it GUARANTEES the Debian and Ubuntu packages are built from byte-identical
# upstream payloads.
#
# The price is an ordering constraint: a version can only be built on Debian once
# its orig is in Launchpad. obs-trigger.yml therefore waits for exactly the URL
# OBS will fetch before it runs the services.
#
# NOTE the filename it is saved under: <tool>-<ver>.tar.xz, with a HYPHEN.
# Handing debtransform a file that is ALREADY named <tool>_<ver>.orig.tar.xz
# makes it die with "link: File exists" -- it renames the archive to exactly that
# name itself, and hardlinking a file onto itself fails.
set -euo pipefail

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
LP_OWNER=${LP_OWNER:-dreunion61}
LP_PPA=${LP_PPA:-media-preservation}

# redumper-gui is absent on purpose: eframe/egui needs rustc >= 1.92 and Debian
# 13 ships 1.85 (12 ships 1.63), so it cannot be built on either target. Its
# absence here IS the answer -- do not "fix" it by adding it.
DEB_TOOLS=(redumper redumper729 redumper732 aaru aaru5 discimagecreator mpf)

gen_one() {
    local tool=$1
    local recipe="$REPO/ubuntu/$tool"
    local obsdir="$REPO/opensuse/$tool"
    [ -d "$recipe/debian" ] || { echo "no debian/ recipe: $tool" >&2; return 1; }
    [ -d "$obsdir" ]        || { echo "no OBS package dir: $tool" >&2; return 1; }

    local fullver ver
    fullver=$(dpkg-parsechangelog -l "$recipe/debian/changelog" -SVersion)
    ver=${fullver%-*}

    # ---- debian.tar.gz (deterministic: identical recipe -> identical bytes,
    #      so a stale blob is a byte diff and status.sh can see it) ----
    tar -C "$recipe" --sort=name --owner=0 --group=0 --numeric-owner \
        --mtime=@0 --format=gnu --exclude=debian/changelog \
        -cf - debian | gzip -n9 > "$obsdir/debian.tar.gz"

    # ---- <tool>.dsc ----
    python3 - "$recipe/debian/control" "$obsdir/$tool.dsc" "$fullver" "$tool" "$ver" <<'PY'
import sys, re
control, out, fullver, tool, ver = sys.argv[1:6]

# deb822: fold continuations, drop comments. dpkg allows '#' lines in control;
# a parser that does not skip them silently corrupts Build-Depends.
stanzas, cur = [], {}
key = None
for line in open(control):
    line = line.rstrip('\n')
    if line.startswith('#'):
        continue
    if not line.strip():
        if cur:
            stanzas.append(cur); cur, key = {}, None
        continue
    if line[0] in ' \t' and key:
        cur[key] += ' ' + line.strip()
        continue
    k, _, v = line.partition(':')
    key = k.strip()
    cur[key] = v.strip()
if cur:
    stanzas.append(cur)

src = stanzas[0]
bins = stanzas[1:]

# Union of the binary stanzas' architectures, order preserved. 'any' or 'all'
# alone is fine; a mix is what dpkg-source expects to see spelled out.
archs = []
for b in bins:
    for a in b.get('Architecture', '').split():
        if a not in archs:
            archs.append(a)

fields = [
    ('Format',                 '3.0 (quilt)'),
    ('Source',                 src['Source']),
    ('Binary',                 ', '.join(b['Package'] for b in bins)),
    ('Architecture',           ' '.join(archs)),
    ('Version',                fullver),
    ('Maintainer',             src.get('Maintainer', '')),
    ('Homepage',               src.get('Homepage', '')),
    ('Standards-Version',      src.get('Standards-Version', '')),
    ('Build-Depends',          src.get('Build-Depends', '')),
    ('Debtransform-Tar',       f'{tool}-{ver}.tar.xz'),
    ('Debtransform-Files-Tar', 'debian.tar.gz'),
]
with open(out, 'w') as f:
    for k, v in fields:
        if v:
            f.write(f'{k}: {v}\n')
PY

    # ---- _service: rewrite the deb block between the markers ----
    local url="https://launchpad.net/~${LP_OWNER}/+archive/ubuntu/${LP_PPA}/+files/${tool}_${ver}.orig.tar.xz"
    local raw="https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main"
    local block
    block=$(cat <<EOF
  <!-- BEGIN deb · generated by scripts/obs/gen-deb.sh · do not edit by hand.
       Keep double hyphens out of this comment: XML forbids them inside a
       comment, and OBS then rejects the whole _service file, not just it. -->
  <service name="download_url">
    <param name="url">${raw}/opensuse/${tool}/${tool}.dsc</param>
    <param name="filename">${tool}.dsc</param>
  </service>
  <service name="download_url">
    <param name="url">${raw}/opensuse/${tool}/debian.tar.gz</param>
    <param name="filename">debian.tar.gz</param>
  </service>
  <service name="download_url">
    <param name="url">${raw}/ubuntu/${tool}/debian/changelog</param>
    <param name="filename">debian.changelog</param>
  </service>
  <service name="download_url">
    <param name="url">${url}</param>
    <param name="filename">${tool}-${ver}.tar.xz</param>
  </service>
  <!-- END deb -->
EOF
)
    python3 - "$obsdir/_service" "$block" <<'PY'
import sys, re
path, block = sys.argv[1], sys.argv[2]
s = open(path).read()
begin = '  <!-- BEGIN deb'
if begin in s:
    s = re.sub(r'  <!-- BEGIN deb.*?  <!-- END deb -->\n', block + '\n', s, flags=re.S)
else:
    s = s.replace('</services>', block + '\n</services>')
open(path, 'w').write(s)
PY

    printf '  %-18s %-30s dsc + debian.tar.gz + _service\n' "$tool" "$fullver"
}

tools=("$@")
[ ${#tools[@]} -gt 0 ] || tools=("${DEB_TOOLS[@]}")
for t in "${tools[@]}"; do gen_one "$t"; done
