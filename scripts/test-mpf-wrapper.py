#!/usr/bin/env python3
"""Behaviour tests for the mpf launcher wrapper -- run in CI on every push
(check-repo.yml).

The template ubuntu/mpf/debian/mpf-wrapper.in, rendered the way debian/rules
renders it (@TARGET@ -> the role's binary), runs in a real POSIX shell against
stubs: the target prints RAN, `getconf GNU_LIBC_VERSION` prints the glibc the
case asks for, and HOME is a scratch directory. Each case runs under every
shell found of dash and bash (Debian's /bin/sh is dash, Fedora's is bash).
MPFWRAPPER=<path> runs the cases against another copy of the template.
mpf-wrapper-sync.py keeps the two RPM heredocs identical to the template, so
this tests all three copies. Exit 1 if any case disagrees.

What is tested is the glibc guard (MPF-GLIBC-GUARD in the template): below
glibc 2.34 the wrapper refuses to start MPF.Check when MPF would compress the
logs, and refuses to start MPF next to a log archive MPF would extract.
MPF.Check reads its flags with SabreTools.CommandLine, where a flag also
matches as `flag=anything` (so `--zip=false` turns compression ON), and the
last of --zip/--no-zip wins.
"""
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = pathlib.Path(os.environ.get("MPFWRAPPER", ROOT / "ubuntu/mpf/debian/mpf-wrapper.in"))
SHELLS = [s for s in ("dash", "bash") if shutil.which(s)] or ["sh"]

failures = 0


def zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in entries:
            z.writestr(name, "log\n")
    return buf.getvalue()


def setup(tmp: pathlib.Path):
    stub = tmp / "stub"
    stub.mkdir()
    getconf = stub / "getconf"
    getconf.write_text('#!/bin/sh\n[ "$1" = GNU_LIBC_VERSION ] && echo "glibc $TEST_GLIBC"\n')
    getconf.chmod(0o755)
    wrappers = {}
    template = TEMPLATE.read_text()
    for role, binary in (("mpf-check", "MPF.Check"), ("mpf-cli", "MPF.CLI")):
        target = tmp / "lib" / role / binary
        target.parent.mkdir(parents=True)
        target.write_text('#!/bin/sh\necho RAN "$@"\n')
        target.chmod(0o755)
        wrapper = tmp / "bin" / role
        wrapper.parent.mkdir(exist_ok=True)
        wrapper.write_text(template.replace("@TARGET@", str(target)))
        wrapper.chmod(0o755)
        wrappers[role] = wrapper
    work = tmp / "work"
    work.mkdir()
    (work / "full.bin").write_text("dump\n")
    (work / "full_logs.zip").write_bytes(zip_bytes(["full.log"]))
    (work / "empty.bin").write_text("dump\n")
    (work / "empty_logs.zip").write_bytes(zip_bytes([]))
    return stub, wrappers, work


# (label, role, glibc, args, expect[, env]) -- expect "run" or the text the refusal must contain
CASES = [
    ("-z refused", "mpf-check", "2.28", ["-z", "x.bin"], "-z/--zip"),
    ("--zip refused", "mpf-check", "2.28", ["--zip", "x.bin"], "-z/--zip"),
    ("-z=1 refused (the parser takes flag=value as the flag)", "mpf-check", "2.28", ["-z=1", "x.bin"], "-z/--zip"),
    ("--zip=false refused (it turns compression ON)", "mpf-check", "2.28", ["--zip=false", "x.bin"], "-z/--zip"),
    ("--no-zip runs", "mpf-check", "2.28", ["--no-zip", "x.bin"], "run"),
    ("no flag runs", "mpf-check", "2.28", ["x.bin"], "run"),
    ("no flag runs with zip=1 in the environment", "mpf-check", "2.28", ["x.bin"], "run", {"zip": "1"}),
    ("-z then --no-zip runs (last wins)", "mpf-check", "2.28", ["-z", "--no-zip", "x.bin"], "run"),
    ("--no-zip then -z refused (last wins)", "mpf-check", "2.28", ["--no-zip", "-z", "x.bin"], "-z/--zip"),
    ("-z then --no-zip=1 runs", "mpf-check", "2.28", ["-z", "--no-zip=1", "x.bin"], "run"),
    ("glibc 2.34: --zip runs", "mpf-check", "2.34", ["--zip", "x.bin"], "run"),
    ("MPF.CLI has no -z: runs", "mpf-cli", "2.28", ["-z", "x.bin"], "run"),
    ("archive with entries next to the input refused", "mpf-check", "2.28", ["{work}/full.bin"], "would extract"),
    ("the archive itself refused", "mpf-check", "2.28", ["{work}/full_logs.zip"], "would extract"),
    ("archive in an option value refused", "mpf-cli", "2.28", ["--file={work}/full.bin"], "would extract"),
    ("archive without entries runs", "mpf-check", "2.28", ["{work}/empty.bin"], "run"),
    ("glibc 2.34: archive with entries runs", "mpf-check", "2.34", ["{work}/full.bin"], "run"),
]


def main():
    global failures
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        stub, wrappers, work = setup(tmp)
        for shell in SHELLS:
            for label, role, glibc, args, expect, *extra in CASES:
                home = tmp / "home"
                shutil.rmtree(home, ignore_errors=True)
                home.mkdir()
                env = {"HOME": str(home), "PATH": f"{stub}:/usr/bin:/bin", "TEST_GLIBC": glibc,
                       **(extra[0] if extra else {})}
                argv = [a.format(work=work) for a in args]
                r = subprocess.run([shell, str(wrappers[role]), *argv], check=False, env=env, cwd=work,
                                   capture_output=True, text=True, timeout=30)
                ran = r.stdout.startswith("RAN")
                if expect == "run":
                    ok = r.returncode == 0 and ran
                    got = f"rc={r.returncode} ran={ran}"
                else:
                    ok = r.returncode == 1 and not ran and expect in r.stderr
                    got = f"rc={r.returncode} ran={ran} stderr={r.stderr.strip()[:90]!r}"
                failures += not ok
                print(f"{'ok  ' if ok else 'FAIL'} [{shell}] {label}" + ("" if ok else f": {got}"))
    if failures:
        print(f"{failures} case(s) failed", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
