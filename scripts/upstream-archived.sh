#!/bin/bash
# upstream-archived.sh github|codeberg OWNER/REPO PACKAGE_DIR
#
# Asks an upstream repository whether it is archived. A watcher otherwise asks
# only for the newest release, tag or commit, and an archived project never has
# a new one: its watcher would stay green for ever although nothing will come
# again. So every watcher runs this for each repository it follows, before it
# asks for anything else (scripts/test-upstream-archived.py checks that).
#
# The marker is PACKAGE_DIR/.upstream-archived.REPO (REPO without the owner):
# one package can follow several repositories (discimagecreator follows four),
# and a marker for one must not speak for another.
#
#   upstream archived    marker     exit
#   no                   absent     0
#   yes                  present    0  known; the package is kept on purpose
#   yes                  absent     1  new: keep, replace or retire the package
#   no                   present    1  the marker is wrong: upstream is active again
#   no answer            either     1  never taken for "not archived"
#
# To keep a package whose upstream is archived, commit the marker saying since
# when and why; its content is for people, only its presence counts.
set -euo pipefail

if [ $# -ne 3 ]; then
  echo "::error::usage: upstream-archived.sh github|codeberg OWNER/REPO PACKAGE_DIR"
  exit 1
fi
kind=$1 project=$2 dir=$3
marker=$dir/.upstream-archived.${project#*/}

case $kind in
  github) fetch() { gh api "repos/$project"; } ;;
  codeberg) fetch() { curl -fsSL "https://codeberg.org/api/v1/repos/$project"; } ;;
  *) echo "::error::upstream-archived.sh: unknown kind '$kind' (github or codeberg)"; exit 1 ;;
esac

# A failed request, a body that is not JSON and an answer without the field all
# end up as something other than true or false, and that is red below.
archived=$(fetch | jq -r '.archived') || archived=unreadable

case $archived in
  true)
    if [ -f "$marker" ]; then
      echo "Upstream $project is archived; $marker keeps the package on purpose"
      exit 0
    fi
    echo "::error::Upstream $project is archived: nothing new will come. Keep the package (commit $marker saying since when and why), package a successor, or retire it"
    exit 1
    ;;
  false)
    if [ -f "$marker" ]; then
      echo "::error::$marker says $project is archived, but upstream is active again: remove the file"
      exit 1
    fi
    echo "Upstream $project is not archived"
    ;;
  *)
    echo "::error::Could not tell whether upstream $project is archived (answer: ${archived:-empty})"
    exit 1
    ;;
esac
