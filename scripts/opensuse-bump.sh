#!/bin/bash
#
# opensuse-bump.sh <tool> <changelog-version> <marker|-> <message> KEY=VAL [KEY=VAL ...]
#
# Advance the openSUSE/OBS recipe of <tool> to a new upstream revision, in the
# same commit as the fedora spec and ubuntu changelog bumps. Called by the
# watch-<tool> workflows so all three lanes track the same upstream revision.
#
#   KEY=VAL   rewrite a version macro in opensuse/<tool>/<tool>.spec.
#             KEY "Version" rewrites the `Version:` tag; any other KEY rewrites
#             the `%global <KEY> ...` line. The openSUSE specs deliberately use
#             the SAME macro names as the fedora ones (mpfver/mpfsnap,
#             dicsnap/diccommit, aaruver/aaruprerel), so the watcher passes the
#             values it already computed.
#   marker    new content of opensuse/<tool>/.upstream-tag, or "-" to leave it
#             alone (mpf's marker is the constant rolling tag, not a revision).
#
# Release: is NEVER touched. Unlike the fedora lane (bare-N + %{?dist}), the
# openSUSE specs pin `Release: 0` and let OBS supply its own build counter, so
# there is no packaging-iteration counter to reset.
#
# Every rewrite is VERIFIED: if a KEY is absent from the spec, or the line does
# not carry the new value afterwards, the script fails loudly. A silent sed
# no-op is exactly how the openSUSE lane drifted behind fedora/ubuntu before
# (redumper b729 vs b731, mpf 3.8.2 vs 3.8.3 — both had to be fixed by hand).
set -euo pipefail

TOOL=${1:?tool}
CLVER=${2:?changelog-version}
MARKER=${3:?marker or -}
MSG=${4:?message}
shift 4

DIR="opensuse/$TOOL"
SPEC="$DIR/$TOOL.spec"
[ -f "$SPEC" ] || { echo "no spec at $SPEC" >&2; exit 1; }
[ $# -gt 0 ] || { echo "no KEY=VAL rewrites given" >&2; exit 1; }

for KV in "$@"; do
  KEY=${KV%%=*}
  VAL=${KV#*=}
  [ "$KEY" != "$KV" ] || { echo "malformed rewrite '$KV' (want KEY=VAL)" >&2; exit 1; }

  if [ "$KEY" = "Version" ]; then
    PATTERN='^Version:[[:space:]]+'
    sed -i -E "s|^(Version:[[:space:]]+).*|\1${VAL}|" "$SPEC"
  else
    PATTERN="^%global[[:space:]]+${KEY}[[:space:]]+"
    grep -Eq "$PATTERN" "$SPEC" || {
      echo "error: $SPEC has no '%global $KEY' line — the openSUSE spec has drifted" >&2
      echo "       from the fedora one (macro renamed?). Fix the recipes, not this script." >&2
      exit 1
    }
    sed -i -E "s|^(%global[[:space:]]+${KEY}[[:space:]]+).*|\1${VAL}|" "$SPEC"
  fi

  # Prove the rewrite landed — never trust an unverified sed.
  grep -Eq "${PATTERN}${VAL}\$" "$SPEC" || {
    echo "error: rewrite of '$KEY' to '$VAL' did not land in $SPEC" >&2
    exit 1
  }
  echo ":: $SPEC: $KEY -> $VAL"
done

if [ "$MARKER" != "-" ]; then
  printf '%s\n' "$MARKER" > "$DIR/.upstream-tag"
  echo ":: $DIR/.upstream-tag -> $MARKER"
fi

# Prepend a %changelog entry. EVR is <version>-0, matching the existing
# hand-written entries (LC_ALL=C so the weekday/month are English, which rpm
# checks against the date).
CL_ENTRY=$(mktemp)
{
  printf '* %s gmipf <gmipf64@gmail.com> - %s-0\n' \
    "$(LC_ALL=C date -u +'%a %b %d %Y')" "$CLVER"
  printf -- '- %s\n' "$MSG"
  printf '\n'
} > "$CL_ENTRY"
sed -i "/^%changelog/r $CL_ENTRY" "$SPEC"
rm -f "$CL_ENTRY"

echo ":: bumped $SPEC -> ${CLVER}-0"
