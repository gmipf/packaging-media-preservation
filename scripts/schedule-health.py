#!/usr/bin/env python3
"""schedule-health.py -- name a scheduled workflow that stopped firing.

Usage:
  scripts/schedule-health.py      report; exit 1 on any ERROR
                                  (scripts/status.sh prints the same report)

Why this exists
---------------
Every watcher here runs on a `schedule:`. A schedule that stops firing is the
quietest failure there is: no run means no red run, and the list of recent runs
in status.sh only shows runs that happened. It can stop for reasons outside this
repository: GitHub disables the schedules of a public repository after 60 days
without activity, a workflow can be disabled by hand, a cron can be edited into
one that never matches.

GitHub throttles schedules, so "late" needs a measured scale, not the plan.
Measured 2026-10-13 over the last 60 scheduled runs of each hourly watcher: a
median gap of 5.4-5.9 h and a longest gap of 10.6 h; the weekly lifecycle
watcher ran 9 h after its slot. A workflow is therefore red when its last
scheduled run is older than its planned interval plus SLACK (24 h), more than
twice the worst delay measured.

What it judges, per workflow with a cron on origin/main
-------------------------------------------------------
  ok      the last scheduled run is younger than interval + SLACK
  wait    no scheduled run under the current cron yet, and the cron took its
          current form less than interval + SLACK ago (a new workflow, or a
          changed schedule)
  ERROR   older than that; never fired although the cron is older than that;
          GitHub reports the workflow as anything but active; GitHub does not
          know the workflow; a cron this script cannot read; no answer

"Interval" is the longest gap between two firings of the workflow's crons
together, computed from the cron fields, so `11 3,9,15,21 * * *` is 6 h and a
weekly cron is 168 h.

Why status.sh and not CI
------------------------
The one failure that hits every schedule at once -- GitHub disabling them after
60 days without activity -- also stops every scheduled check, and without
activity there is no push to run one either. A person running status.sh is the
only reader that still exists then. The decision tests run in CI on every push
(check-repo.yml).
"""
import datetime
import itertools
import json
import os
import re
import subprocess
import sys
import time

GH_REPO = os.environ.get("GH_REPO", "gmipf/packaging-media-preservation")
REF = os.environ.get("SCHED_REF_GIT", "origin/main")
SLACK = 24 * 3600
CRON_LINE = re.compile(r"""^\s*-\s*cron:\s*(['"])(.+?)\1\s*(#.*)?$""")
SCHEDULE_KEY = re.compile(r"^\s*schedule:\s*(#.*)?$")


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True,
                          stdin=subprocess.DEVNULL).stdout.strip()


def gh_api(path, key):
    """The parsed JSON at api.github.com/<path>; raises unless it has <key>."""
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True,
                         stdin=subprocess.DEVNULL).stdout
    doc = json.loads(out)
    if not isinstance(doc, dict) or key not in doc:
        raise ValueError(f"{path}: no '{key}' in the answer")
    return doc


def parse_field(spec, lo, hi):
    """Values of one cron field: *, */n, a, a-b, a-b/n, comma lists. Anything else
    (names like MON, ?, L, W) raises: an unread cron is not a quiet one."""
    values = set()
    for part in spec.split(","):
        m = re.fullmatch(r"(\*|\d+(?:-\d+)?)(?:/(\d+))?", part)
        if not m:
            raise ValueError(f"cron field {spec!r}: cannot read {part!r}")
        rng, step = m.group(1), int(m.group(2) or 1)
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = map(int, rng.split("-"))
        else:
            a = b = int(rng)
            if m.group(2):
                b = hi
        if step < 1 or a < lo or b > hi or a > b:
            raise ValueError(f"cron field {spec!r}: {part!r} is outside {lo}-{hi}")
        values.update(range(a, b + 1, step))
    return values


def firings(exprs, start, days):
    """Sorted epoch seconds at which any of exprs fires in [start, start+days)."""
    out = set()
    for expr in exprs:
        f = expr.split()
        if len(f) != 5:
            raise ValueError(f"cron {expr!r}: expected 5 fields")
        mins, hours = parse_field(f[0], 0, 59), parse_field(f[1], 0, 23)
        doms, months = parse_field(f[2], 1, 31), parse_field(f[3], 1, 12)
        dows = {d % 7 for d in parse_field(f[4], 0, 7)}  # 7 is Sunday too
        # cron: if both day fields are restricted, EITHER may match
        either = not f[2].startswith("*") and not f[4].startswith("*")
        for n in range(days):
            day = start + datetime.timedelta(days=n)
            dom_ok, dow_ok = day.day in doms, (day.weekday() + 1) % 7 in dows
            if day.month not in months or not ((dom_ok or dow_ok) if either else (dom_ok and dow_ok)):
                continue
            base = int(day.timestamp())
            out.update(base + h * 3600 + m * 60 for h in hours for m in mins)
    return sorted(out)


def max_gap(exprs):
    """Longest gap in seconds between two consecutive firings of exprs together,
    over two years (every weekday/month-day combination comes round)."""
    start = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    t = firings(exprs, start, 731)
    if len(t) < 3:
        raise ValueError(f"crons {exprs} fire fewer than 3 times in two years")
    return max(b - a for a, b in itertools.pairwise(t))


def crons(text):
    """The cron expressions of a workflow file; raises on a schedule without one."""
    found = []
    for line in text.splitlines():
        m = CRON_LINE.match(line)
        if m:
            found.append(m.group(2).strip())
    if not found and any(SCHEDULE_KEY.match(line) for line in text.splitlines()):
        raise ValueError("has a schedule: key but no cron line this script can read")
    return found


def judge(now, interval, last_run, since, state):
    """-> (state, detail). last_run: epoch of the newest scheduled run or None;
    since: epoch at which the crons took their current form on main."""
    def h(seconds):
        return f"{seconds / 3600:.1f} h"

    limit = interval + SLACK
    if state != "active":
        why = " (60 days without activity)" if state == "disabled_inactivity" else ""
        return "ERROR", f"GitHub reports the workflow as {state}{why}: no schedule fires"
    if last_run is None or last_run < since:
        age = now - since
        if age <= limit:
            return "wait", f"no scheduled run under this cron yet, cron is {h(age)} old (red after {h(limit)})"
        return "ERROR", f"never fired under this cron, which is {h(age)} old (plan: every {h(interval)})"
    age = now - last_run
    if age <= limit:
        return "ok", f"last scheduled run {h(age)} ago (plan: every {h(interval)}, red after {h(limit)})"
    return "ERROR", f"last scheduled run {h(age)} ago (plan: every {h(interval)}, red after {h(limit)})"


def epoch(iso):
    return int(datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def main():
    os.chdir(git("-C", os.path.dirname(os.path.abspath(__file__)), "rev-parse", "--show-toplevel"))
    now = int(time.time())
    tally = {}

    def report(state, name, detail):
        tally[state] = tally.get(state, 0) + 1
        if state == "ERROR" and os.environ.get("GITHUB_ACTIONS"):
            print(f"::error::{name}: {detail}")
        print(f"{state:<9} {name:<28} {detail}")

    try:
        git("fetch", "-q", "origin")
        files = [p for p in git("ls-tree", "--name-only", REF, ".github/workflows/").split("\n")
                 if p.endswith((".yml", ".yaml"))]
        if not files:
            raise ValueError(f"no workflow files on {REF}")
        known = {w["path"]: w for w in gh_api(f"repos/{GH_REPO}/actions/workflows?per_page=100",
                                              "workflows")["workflows"]}
    except Exception as e:  # without the list there is nothing to judge: stop here
        report("ERROR", "setup", f"could not read workflows: {type(e).__name__}: {e}")
        sys.exit(1)

    for path in files:
        name = os.path.basename(path)
        try:
            exprs = crons(git("show", f"{REF}:{path}"))
            if not exprs:
                continue
            interval = max_gap(exprs)
            since = max(int(git("log", "-1", "--format=%ct", "-S", e, REF, "--", path) or 0) for e in exprs)
            if not since:
                raise ValueError(f"git log finds no commit that added {exprs} to {path}")
            if path not in known:
                raise ValueError(f"GitHub does not know {path}")
            wf = known[path]
            runs = gh_api(f"repos/{GH_REPO}/actions/workflows/{wf['id']}/runs?event=schedule&per_page=1",
                          "workflow_runs")["workflow_runs"]
            last = epoch(runs[0]["created_at"]) if runs else None
            state, detail = judge(now, interval, last, since, wf["state"])
        except Exception as e:
            state, detail = "ERROR", f"could not measure: {type(e).__name__}: {e}"
        report(state, name, detail)

    if not tally:
        report("ERROR", "setup", f"no workflow on {REF} has a cron: nothing was judged")
    print("summary   " + " · ".join(f"{v}x {k}" for k, v in sorted(tally.items())))
    sys.exit(1 if tally.get("ERROR") else 0)


if __name__ == "__main__":
    main()
