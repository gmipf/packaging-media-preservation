#!/bin/bash
#
# push-retry.sh <git push arguments...>
#
# `git push`, retried. Used by every watcher for the COPR trigger-branch push.
#
# On 2026-10-12 16:10 UTC GitHub answered three pushes in a row with
# "Internal Server Error". The watchers already retried the push to main, and
# it went through on the third attempt -- but the trigger-branch push right
# after it had no retry. It failed once, the job went red, the OBS job was
# skipped, and the mpf 3.11.0 build was LOST rather than late: the next run
# found main already bumped and had nothing left to do. A failure BEHIND the
# state write is not healed by the next run; only a retry here is.
#
# Every caller pushes with -f to a branch it owns, so repeating the push cannot
# do harm.
set -u
attempts=4
for attempt in $(seq 1 "$attempts"); do
    git push "$@" && exit 0
    [ "$attempt" -lt "$attempts" ] || break
    echo "::warning::git push $* failed (attempt $attempt/$attempts), retrying in $((attempt * 15))s"
    sleep $((attempt * 15))
done
echo "::error::git push $* failed $attempts times"
exit 1
