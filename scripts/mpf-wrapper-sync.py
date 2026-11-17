#!/usr/bin/env python3
"""mpf-wrapper-sync.py -- the three mpf launcher wrappers are one script.

ubuntu/mpf/debian/mpf-wrapper.in is the source: debian/rules substitutes @TARGET@
once per role. The two RPM specs write the same script from an unquoted heredoc
in %install, one loop pass per role. This script derives that heredoc body from
the template, so the three copies cannot drift apart:

  scripts/mpf-wrapper-sync.py check   exit 1 if a spec's heredoc differs (lint.sh)
  scripts/mpf-wrapper-sync.py write   rewrite the heredoc in both specs

Edit the template, run `write`, commit all three. The conversion escapes what
the build would otherwise expand: `\\`, `$` and backticks for the shell (the
heredoc is unquoted, so `$target` is the only build-time variable), and `%`
for rpm, which expands macros inside %install as well -- `${x%%.*}` would reach
the shell as `${x%.*}`.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "ubuntu/mpf/debian/mpf-wrapper.in"
SPECS = [ROOT / "fedora/mpf/mpf.spec", ROOT / "opensuse/mpf/mpf.spec"]
START = "    cat > %{buildroot}%{_bindir}/$name <<EOF\n"
END = "\nEOF\n"


def heredoc_body(template: str) -> str:
    if template.count("@TARGET@") < 1:
        raise SystemExit(f"{TEMPLATE.relative_to(ROOT)}: no @TARGET@ -- the template moved")
    s = template.replace("\\", "\\\\").replace("$", "\\$").replace("`", "\\`")
    s = s.replace("%", "%%")
    s = s.replace("@TARGET@", "$target")
    return s.rstrip("\n")


def split(spec: pathlib.Path, text: str):
    if text.count(START) != 1:
        raise SystemExit(f"{spec.relative_to(ROOT)}: expected exactly one wrapper heredoc "
                         f"({START.strip()!r}), found {text.count(START)}")
    head, rest = text.split(START, 1)
    if END not in rest:
        raise SystemExit(f"{spec.relative_to(ROOT)}: wrapper heredoc has no closing EOF line")
    body, tail = rest.split(END, 1)
    return head, body, tail


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in ("check", "write"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    want = heredoc_body(TEMPLATE.read_text())
    if not re.search(r"^exec \$target \"\\\$@\"$", want, re.M):
        raise SystemExit("template does not end in `exec @TARGET@ \"$@\"` -- conversion would be wrong")
    stale = []
    for spec in SPECS:
        text = spec.read_text()
        head, body, tail = split(spec, text)
        if body == want:
            continue
        if mode == "check":
            stale.append(str(spec.relative_to(ROOT)))
        else:
            spec.write_text(head + START + want + END + tail)
            print(f"wrote {spec.relative_to(ROOT)}")
    if stale:
        print("mpf wrappers: the heredoc in " + ", ".join(stale) + " differs from "
              f"{TEMPLATE.relative_to(ROOT)}; edit the template and run "
              "scripts/mpf-wrapper-sync.py write", file=sys.stderr)
        return 1
    if mode == "check":
        print(f"mpf wrappers: both specs carry {TEMPLATE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
