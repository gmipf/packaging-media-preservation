#!/usr/bin/env python3
"""Decision tests for schedule-health.py -- run in CI on every push (check-repo.yml).

The functions under test are the script's own, unmodified; GitHub is replaced by a
fake `gh` on PATH, git is not needed. Exit 1 if any case disagrees.

SCHEDH=<path> runs the cases against another copy of the script; each group was
seen to fail against a deliberately broken one (see the commit message).
"""
import importlib.util
import os
import pathlib
import sys
import tempfile

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("schedh", os.environ.get("SCHEDH", HERE / "schedule-health.py"))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

failures = 0
H = 3600


def check(label, got, want):
    global failures
    ok = got == want
    failures += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got!r}" + ("" if ok else f" (expected {want!r})"))


def outcome(fn, *args):
    """fn(*args), or the name of the exception it raised."""
    try:
        return fn(*args)
    except Exception as e:
        return type(e).__name__


# --- interval from the cron fields ------------------------------------------
G = [
    ("hourly", ["22 * * * *"], 1 * H),
    ("every 6 h as a step", ["41 */6 * * *"], 6 * H),
    ("every 6 h as a list", ["11 3,9,15,21 * * *"], 6 * H),
    ("daily", ["23 5 * * *"], 24 * H),
    ("weekly", ["43 7 * * 1"], 168 * H),
    ("Sunday spelled 7", ["0 0 * * 7"], 168 * H),
    ("two crons together", ["0 0 * * *", "0 12 * * *"], 12 * H),
    ("monthly: the longest month counts", ["0 0 1 * *"], 31 * 24 * H),
    ("day-of-month OR day-of-week when both are set", ["0 0 1 * 1"], 168 * H),
    ("range with step, weekdays only (Fri 18:00 -> Mon 08:00)", ["0 8-18/2 * * 1-5"], 62 * H),
]
for label, exprs, want in G:
    check(f"interval: {label}", outcome(s.max_gap, exprs), want)

BAD = [
    ("a name instead of a number", ["0 0 * * MON"]),
    ("minute out of range", ["61 * * * *"]),
    ("four fields", ["0 0 * *"]),
    ("a day that never comes (Feb 30)", ["0 0 30 2 *"]),
]
for label, exprs in BAD:
    check(f"interval refuses: {label}", outcome(s.max_gap, exprs), "ValueError")


# --- reading the workflow file ----------------------------------------------
WF = """name: x
on:
  schedule:
    # a comment line
    - cron: '22 * * * *'   # hourly
    - cron: "0 5 * * 1"
  workflow_dispatch:
"""
check("crons: both quote styles, trailing comment", outcome(s.crons, WF), ["22 * * * *", "0 5 * * 1"])
check("crons: no schedule at all", outcome(s.crons, "on:\n  push:\n"), [])
check("crons: schedule key but no readable cron",
      outcome(s.crons, "on:\n  schedule:\n    - cron: 22 * * * *\n"), "ValueError")


# --- the verdict --------------------------------------------------------------
NOW = 1_000_000_000
J = [
    ("hourly, last run 10 h ago (throttled, alive)", (1 * H, NOW - 10 * H, NOW - 900 * H, "active"), "ok"),
    ("hourly, last run 26 h ago", (1 * H, NOW - 26 * H, NOW - 900 * H, "active"), "ERROR"),
    ("exactly at the limit", (1 * H, NOW - 25 * H, NOW - 900 * H, "active"), "ok"),
    ("weekly, 180 h ago", (168 * H, NOW - 180 * H, NOW - 900 * H, "active"), "ok"),
    ("weekly, 200 h ago", (168 * H, NOW - 200 * H, NOW - 900 * H, "active"), "ERROR"),
    ("new cron, no run yet", (6 * H, None, NOW - 2 * H, "active"), "wait"),
    ("cron 40 h old, never fired", (6 * H, None, NOW - 40 * H, "active"), "ERROR"),
    ("cron changed after the last run", (1 * H, NOW - 100 * H, NOW - 2 * H, "active"), "wait"),
    ("cron changed long ago, nothing since", (1 * H, NOW - 100 * H, NOW - 60 * H, "active"), "ERROR"),
    ("disabled after 60 days without activity", (1 * H, NOW - 1 * H, NOW - 900 * H, "disabled_inactivity"),
     "ERROR"),
    ("disabled by hand, last run recent", (1 * H, NOW - 1 * H, NOW - 900 * H, "disabled_manually"), "ERROR"),
]
for label, (interval, last, since, state), want in J:
    check(f"verdict: {label}", s.judge(NOW, interval, last, since, state)[0], want)


# --- an answer is an answer, not just output --------------------------------
with tempfile.TemporaryDirectory() as tmp:
    body = pathlib.Path(tmp, "body")
    fake = pathlib.Path(tmp, "gh")
    fake.write_text(f'#!/bin/sh\ncat "{body}"\n')
    fake.chmod(0o755)
    os.environ["PATH"] = f"{tmp}:{os.environ['PATH']}"
    A = [
        ("an HTML error page", "<html>rate limited</html>", "JSONDecodeError"),
        ("JSON without the key", '{"message": "Not Found"}', "ValueError"),
        ("a JSON list", "[]", "ValueError"),
        ("the document asked for", '{"workflow_runs": []}', {"workflow_runs": []}),
    ]
    for label, text, want in A:
        body.write_text(text)
        check(f"answer: {label}", outcome(s.gh_api, "x", "workflow_runs"), want)
    body.unlink()
    check("answer: gh fails", outcome(s.gh_api, "x", "workflow_runs"), "CalledProcessError")

print(f"\n{failures} of the cases above disagree" if failures else "\nall cases agree")
sys.exit(1 if failures else 0)
