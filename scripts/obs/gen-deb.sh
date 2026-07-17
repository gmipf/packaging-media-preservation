#!/bin/bash
#
# gen-deb.sh <tool> [<tool> ...]        (no args = every Debian/Ubuntu tool)
#
# Generate the three files OBS needs to build the .debs of <tool>:
#
#   opensuse/<tool>/<tool>.dsc      the debtransform template
#   opensuse/<tool>/debian.tar.gz   the debian/ dir, MINUS the changelog
#   opensuse/<tool>/_service        the deb block, rewritten between markers
#
#
# EVERY LANE BUILDS STRAIGHT FROM UPSTREAM. NOBODY RE-HOSTS ANYBODY'S BYTES.
#
# An RPM spec lists Source0:, Source1:, Source2: ... and rpmbuild assembles the
# tree in %prep. A Debian source package has ONE orig tarball, and the build root
# has no network -- which looks like it forces someone to pre-assemble a tarball
# and host it somewhere. It does not:
#
#   Debtransform-Tar:    the FIRST upstream archive  -> becomes the .orig tarball
#   Debtransform-Files:  every OTHER upstream file   -> dropped into the source tree
#   Debtransform-Files-Tar: our debian/ dir
#
# Debtransform-Files is the .dsc's answer to Source1:/Source2:, and debian/rules
# is its %prep (aaru unpacks the src tarball, mpf the CLI and GUI zips, dic the
# three sibling projects). Measured: dpkg-source accepts the non-debian/ paths and
# the resulting .deb is byte-for-byte what the pre-assembled orig produced.
#
# So the Debian lane needs NO assembled tarball and NO release asset of our own.
# It briefly took its orig from a Launchpad PPA, because that PPA assembled one
# anyway -- convenient, and wrong: it chained one lane's health to another's, and
# would have left us re-hosting 88 MB of MPF binaries several times a day the day
# that PPA went away. Which it since has. Every lane stands on its own.
#
#
# THE SOURCE LIST IS READ OUT OF THE SPEC, NOT WRITTEN DOWN TWICE
#
# OBS already downloads those very files: `download_files` reads the generated
# spec and fetches its Source: URLs. The .dsc only has to NAME them. Deriving the
# names from the spec means the two cannot drift -- a Source: added there is in
# the .dsc on the next run, and a list maintained by hand is a list that will be
# wrong. Local sources (manpages, udev rules, icons) carry no URL and are skipped:
# they belong to the RPM, and the deb has its own copies under debian/.
#
#
# WHY debian/ TRAVELS AS A TARBALL AND THE CHANGELOG DOES NOT
#
# debtransform also accepts debian/ as flat `debian.<file>` files, one per
# download_url. That is WRONG: HTTP carries no mode bit, so debian/rules would
# arrive 0644 and land 0644 INSIDE the source package. It still builds on Debian
# 12 and 13 -- their dpkg-source silently chmods debian/rules on extract -- but
# dpkg 1.23.7 does not, so the package is malformed and merely happens to work.
# A tarball carries the mode and is correct by construction.
#
# The changelog is the one file in debian/ that moves with every version bump and
# it needs no mode bit. Leaving it out of the tarball keeps that BINARY blob in
# git stable across bumps (mpf alone bumps ~4x a day); it is fetched flat instead.
# debtransform accepts the mix -- it only refuses a file present in BOTH places.
set -euo pipefail

REPO=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)

# redumper-gui IS generated, but it can only be BUILT on Ubuntu 26.04: eframe/egui
# needs rustc >= 1.92, and Debian 13 ships 1.85, Debian 12 ships 1.63, Ubuntu
# 22.04/24.04 top out at 1.91. That is a per-repository `build enable` in its OBS
# package meta, not an omission here -- generating its .dsc costs nothing and the
# day a target catches up, only the meta has to change.
#
# Its Source0 is a tarball of OUR making (cargo vendor: the build root has no
# network, so the crates must travel with the source) published on OUR release.
# That is not a re-host of someone else's bytes -- it is this lane's own build
# input, and the RPM spec names the very same file.
DEB_TOOLS=(redumper redumper-rgui redumper-mpf aaru aaru5 discimagecreator mpf redumper-gui)

gen_one() {
    local tool=$1
    local recipe="$REPO/ubuntu/$tool"
    local obsdir="$REPO/opensuse/$tool"
    local spec="$REPO/fedora/$tool/$tool.spec"
    [ -d "$recipe/debian" ] || { echo "no debian/ recipe: $tool" >&2; return 1; }
    [ -f "$spec" ]          || { echo "no spec to read sources from: $tool" >&2; return 1; }

    local fullver
    fullver=$(dpkg-parsechangelog -l "$recipe/debian/changelog" -SVersion)

    # ---- the upstream archives, straight out of the spec ----
    # rpmspec -P expands the macros, so this sees the same URLs download_files
    # will fetch. `#/name` overrides the saved filename -- honour it, that IS the
    # name the file lands under.
    local sources
    sources=$(rpmspec -P "$spec" 2>/dev/null \
        | sed -n 's/^Source[0-9]*:[[:space:]]*//p' \
        | grep -E '^[a-z]+://' \
        | sed 's|.*#/||; s|.*/||')
    [ -n "$sources" ] || { echo "$tool: no remote Source: in the spec" >&2; return 1; }

    local main others
    main=$(head -1 <<<"$sources")
    others=$(tail -n +2 <<<"$sources" | tr '\n' ' ' | sed 's/ *$//')

    # ---- debian.tar.gz (deterministic: same recipe -> same bytes, so a stale
    #      blob is a byte diff and status.sh can see it) ----
    tar -C "$recipe" --sort=name --owner=0 --group=0 --numeric-owner \
        --mtime=@0 --format=gnu --exclude=debian/changelog \
        -cf - debian | gzip -n9 > "$obsdir/debian.tar.gz"

    # ---- <tool>.dsc ----
    python3 - "$recipe/debian/control" "$obsdir/$tool.dsc" "$fullver" "$main" "$others" <<'PY'
import sys
control, out, fullver, main, others = sys.argv[1:6]

# deb822: fold continuations, drop comments. dpkg allows '#' lines in control;
# a parser that does not skip them silently corrupts Build-Depends.
stanzas, cur, key = [], {}, None
for line in open(control):
    line = line.rstrip('\n')
    if line.startswith('#'):
        continue
    if not line.strip():
        if cur:
            stanzas.append(cur); cur, key = {}, None
        continue
    if line[0] in ' \t' and key:
        cur[key] += ' ' + line.strip(); continue
    k, _, v = line.partition(':')
    key = k.strip(); cur[key] = v.strip()
if cur:
    stanzas.append(cur)

src, bins = stanzas[0], stanzas[1:]

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
    # UPPERCASE, and that is load-bearing. debtransform reads these headers
    # case-insensitively, but obs-build greps the .dsc for a literal
    # '^DEBTRANSFORM-FILES:' to decide whether to pass --include-binaries to
    # dpkg-source. Spell it 'Debtransform-Files:' and the transform still works
    # -- and then dpkg-source refuses the extra upstream archives with
    # "cannot represent change ... add it to debian/source/include-binaries".
    # One header, two readers, only one of them case-blind.
    ('DEBTRANSFORM-TAR',       main),
    ('DEBTRANSFORM-FILES',     others),
    ('DEBTRANSFORM-FILES-TAR', 'debian.tar.gz'),
]
with open(out, 'w') as f:
    for k, v in fields:
        if v:
            f.write(f'{k}: {v}\n')
PY

    # ---- _service: the deb block. Only OUR three files -- the upstream archives
    #      are already there, download_files fetched them for the spec. ----
    local raw="https://raw.githubusercontent.com/gmipf/packaging-media-preservation/main"
    local block
    block=$(cat <<EOF
  <!-- BEGIN deb · generated by scripts/obs/gen-deb.sh · do not edit by hand.
       Keep double hyphens out of this comment: XML forbids them inside a
       comment, and OBS then rejects the whole _service file, not just it.

       No upstream archive is fetched here. download_files above already pulled
       the spec's Source: URLs, and the .dsc names those very files: the RPM and
       the .deb are built from the same upstream bytes, downloaded once. -->
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
  <!-- END deb -->
EOF
)
    python3 - "$obsdir/_service" "$block" <<'PY'
import sys, re
path, block = sys.argv[1], sys.argv[2]
s = open(path).read()
if '  <!-- BEGIN deb' in s:
    s = re.sub(r'  <!-- BEGIN deb.*?  <!-- END deb -->\n', block + '\n', s, flags=re.S)
else:
    s = s.replace('</services>', block + '\n</services>')
open(path, 'w').write(s)
PY

    printf '  %-18s %-32s tar=%s\n' "$tool" "$fullver" "$main"
    [ -n "$others" ] && printf '  %-18s %-32s files=%s\n' "" "" "$others"
    return 0
}

tools=("$@")
[ ${#tools[@]} -gt 0 ] || tools=("${DEB_TOOLS[@]}")
for t in "${tools[@]}"; do gen_one "$t"; done
