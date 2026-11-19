#!/usr/bin/env python3
"""Tests for scripts/upstream-archived.sh and for how the watchers use it.

Part 1 runs the script against stub gh and curl answers: every row of its
table, the answers that are not an answer (null, field missing, not JSON,
empty, request failed), and a marker that belongs to another repository.

Part 2 reads the watchers. Each one calls the script for exactly the
repositories in WIRING, before it asks upstream anything else (an early
"nothing new, exit 0" would otherwise skip it); a new watcher must be added
to WIRING or to EXEMPT; and every marker in fedora/ belongs to one call,
since a marker no call reads is never checked.

UPSTREAM_ARCHIVED_SH points part 1 at another copy of the script, so that a
broken copy can be shown to turn this test red.
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = pathlib.Path(os.environ.get("UPSTREAM_ARCHIVED_SH", ROOT / "scripts" / "upstream-archived.sh"))
WORKFLOWS = ROOT / ".github" / "workflows"

DIC = "fedora/discimagecreator"
WIRING = {
    "watch-redumper-releases.yml": [("github", "superg/redumper", "fedora/redumper")],
    "watch-aaru-releases.yml": [("github", "aaru-dps/Aaru", "fedora/aaru")],
    "watch-dic-releases.yml": [
        ("github", "saramibreak/DiscImageCreator", DIC),
        ("github", "saramibreak/EccEdc", DIC),
        ("github", "saramibreak/unscrambler", DIC),
        ("github", "saramibreak/DVDAuth", DIC),
    ],
    "watch-mpf-rolling.yml": [("github", "SabreTools/MPF", "fedora/mpf")],
    "watch-redumper-gui.yml": [("github", "Deterous/Redumper-GUI", "fedora/redumper-gui")],
    "watch-consumer-pins.yml": [("codeberg", "MoriGM/dreamdump", "fedora/dreamdump")],
}
EXEMPT = {
    "watch-distro-lifecycle.yml": "follows distribution end-of-life dates, no upstream project",
}

STUB = """#!/bin/sh
case "$(basename "$0")" in
  gh) want="api repos/$STUB_PROJECT" ;;
  curl) want="-fsSL https://codeberg.org/api/v1/repos/$STUB_PROJECT" ;;
esac
if [ "$*" != "$want" ]; then
  echo "stub $(basename "$0"): unexpected arguments: $*" >&2
  exit 9
fi
[ "$STUB_FAIL" = 1 ] && exit 22
printf '%s' "$STUB_BODY"
"""

BODIES = {
    "true": '{"archived":true}',
    "false": '{"archived":false}',
    "null": '{"archived":null}',
    "missing": '{"name":"x"}',
    "notjson": "<html>rate limited</html>",
    "empty": "",
}

failures = []
count = 0


def check(name, ok, detail=""):
    global count
    count += 1
    if not ok:
        failures.append(f"{name}: {detail}")


def run(stubdir, args, body="", fail=False, project="o/r"):
    env = dict(os.environ)
    env.update(PATH=f"{stubdir}:{env['PATH']}", STUB_PROJECT=project, STUB_BODY=body,
               STUB_FAIL="1" if fail else "0")
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True)


def part1():
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        stubs = t / "bin"
        stubs.mkdir()
        for name in ("gh", "curl"):
            (stubs / name).write_text(STUB)
            (stubs / name).chmod(0o755)
        pkg = t / "pkg"
        pkg.mkdir()
        marker = pkg / ".upstream-archived.r"
        other = pkg / ".upstream-archived.other"

        for kind in ("github", "codeberg"):
            # rows of the table: (answer, marker present) -> exit
            for answer, present, want in (
                ("false", False, 0),
                ("true", True, 0),
                ("true", False, 1),
                ("false", True, 1),
            ):
                if present:
                    marker.write_text("kept on purpose\n")
                elif marker.exists():
                    marker.unlink()
                r = run(stubs, [kind, "o/r", str(pkg)], BODIES[answer])
                check(f"{kind} archived={answer} marker={present}", r.returncode == want,
                      f"exit {r.returncode}, want {want}; {r.stdout.strip()} {r.stderr.strip()}")
                if want == 0 and answer == "true":
                    check(f"{kind} kept message", "on purpose" in r.stdout, r.stdout.strip())

            # no answer is never "not archived", with or without a marker
            for present in (False, True):
                if present:
                    marker.write_text("kept on purpose\n")
                elif marker.exists():
                    marker.unlink()
                for answer in ("null", "missing", "notjson", "empty"):
                    r = run(stubs, [kind, "o/r", str(pkg)], BODIES[answer])
                    check(f"{kind} answer={answer} marker={present}", r.returncode == 1,
                          f"exit {r.returncode}; {r.stdout.strip()}")
                r = run(stubs, [kind, "o/r", str(pkg)], BODIES["false"], fail=True)
                check(f"{kind} request failed marker={present}", r.returncode == 1,
                      f"exit {r.returncode}; {r.stdout.strip()}")
            if marker.exists():
                marker.unlink()

            # the script must ask for the repository it was given
            r = run(stubs, [kind, "o/r", str(pkg)], BODIES["false"], project="o/elsewhere")
            check(f"{kind} asks the named repository", r.returncode == 1, f"exit {r.returncode}")

            # a marker for another repository of the same package does not count
            other.write_text("kept on purpose\n")
            r = run(stubs, [kind, "o/r", str(pkg)], BODIES["true"])
            check(f"{kind} other repo's marker, archived", r.returncode == 1, f"exit {r.returncode}")
            r = run(stubs, [kind, "o/r", str(pkg)], BODIES["false"])
            check(f"{kind} other repo's marker, active", r.returncode == 0, f"exit {r.returncode}")
            other.unlink()

        # a wrong call is red anyway (unbound $3, no fetch); the guards are there
        # for the message, so the message is what is checked
        for args, says in ((["gitea", "o/r", str(pkg)], "unknown kind 'gitea'"),
                           (["github", "o/r"], "usage:")):
            r = run(stubs, args, BODIES["false"])
            check(f"bad call {args[:2]}", r.returncode == 1 and says in r.stdout,
                  f"exit {r.returncode}; {r.stdout.strip()} {r.stderr.strip()}")


CALL = re.compile(r"^\s*bash scripts/upstream-archived\.sh (\S+) (\S+) (\S+)\s*$")
ASKS = re.compile(r"\bgh (api|release)\b|\bcurl\b|\bgit ls-remote\b")


def part2():
    watchers = sorted(p.name for p in WORKFLOWS.glob("watch-*.yml"))
    for name in sorted(set(WIRING) | set(EXEMPT)):
        check(f"{name} exists", name in watchers, "listed here, but there is no such workflow")
    used = set()
    for name in watchers:
        lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
        calls = [(i, CALL.match(line).groups()) for i, line in enumerate(lines) if CALL.match(line)]
        if name in EXEMPT:
            check(f"{name} exempt", not calls, "exempt, but calls the script: drop it from EXEMPT")
            continue
        check(f"{name} listed", name in WIRING, "a new watcher: add its repositories to WIRING (or to EXEMPT)")
        want = WIRING.get(name, [])
        check(f"{name} calls", sorted(c for _, c in calls) == sorted(want),
              f"calls {[c for _, c in calls]}, want {want}")
        asks = [i for i, line in enumerate(lines)
                if ASKS.search(line) and not line.lstrip().startswith("#") and not CALL.match(line)]
        if calls and asks:
            check(f"{name} order", max(i for i, _ in calls) < min(asks),
                  f"line {min(asks) + 1} asks upstream before the check on line {max(i for i, _ in calls) + 1}")
        for _, (_kind, project, pkgdir) in calls:
            check(f"{name} {pkgdir}", (ROOT / pkgdir).is_dir(), "no such package directory")
            used.add(f"{pkgdir}/.upstream-archived.{project.split('/', 1)[1]}")
    for m in sorted(ROOT.glob("fedora/*/.upstream-archived*")):
        rel = m.relative_to(ROOT).as_posix()
        check(f"marker {rel}", rel in used, "no watcher reads this marker")


part1()
part2()
if failures:
    for f in failures:
        print(f"FAIL {f}")
    print(f"{len(failures)} of {count} checks failed")
    sys.exit(1)
print(f"ok: {count} checks")
