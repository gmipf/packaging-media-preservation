#!/usr/bin/env python3
"""Bash completions for the packaged tools, generated from the upstream source.

    gen.py write [<package>...]   fetch the source files at the revision the
                                  Fedora spec pins, render, write every lane copy
    gen.py check [<package>...]   the same, but only compare: 1 if a committed
                                  copy is not what the generator makes (network)
    gen.py lint                   offline: every lane copy exists, is identical,
                                  names the revision its spec pins, and every
                                  recipe installs it
    gen.py smoke                  offline: load each completion into a real bash
                                  with bash-completion and complete its SMOKE
                                  lines (needs bash-completion installed)
    gen.py has <package>          prints yes or no: does it ship completions
                                  (scripts/bump-pin.sh asks before `write`)

No package = all. One completion per command, in three copies that must stay
byte-identical (lint), because each lane builds from its own directory:

    fedora/<pkg>/<cmd>.bash-completion        packit Source (flat)
    opensuse/<pkg>/<cmd>.bash-completion      OBS: fetched by its raw URL
    ubuntu/<pkg>/debian/completions/<cmd>     travels in debian.tar.gz

A command installed under more names (dic for discimagecreator) gets a symlink
per alias next to the completion: bash-completion loads a completion by the
name typed, and the file registers all of them.

Why committed and not generated at build time: the build would need python and
the upstream source in every lane (EL8's python 3.6, the Debian lane's
DEBTRANSFORM step), and nobody would ever read the result. Here every change is
a diff in a commit. The watchers run `write` on each bump, BEFORE gen-deb.sh
(the Debian copy is part of debian.tar.gz). A parser that changed shape upstream
makes `write` fail, and with it the watcher run -- every hour until the
generator is fixed. It never writes a short list that looks complete.

The upstream files are only read as text, never executed. Set
MEDIAPRES_COMPLETION_CACHE to a directory to keep the downloads between runs.
"""
import difflib
import hashlib
import importlib
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.dont_write_bytecode = True  # no __pycache__ next to the generators in a checkout
sys.path.insert(0, str(HERE))

# One entry per completion file: the package that installs it (and the
# subpackage, when the command ships in one: mpf-cli is %files cli, Debian
# package mpf-cli), the command (and the other names it is installed as), the
# generator module, where the source lives, and the revision as an expression
# over the Fedora spec's macros.
COMPLETIONS = [
    dict(pkg="redumper", cmd="redumper", gen="redumper", host="github",
         repo="superg/redumper", ref="b%{version}"),
    dict(pkg="redumper-mpf", cmd="redumper-mpf", gen="redumper", host="github",
         repo="superg/redumper", ref="b%{rdbuild}"),
    dict(pkg="redumper-rgui", cmd="redumper-rgui", gen="redumper", host="github",
         repo="superg/redumper", ref="b%{rdbuild}"),
    dict(pkg="dreamdump", cmd="dreamdump", gen="dreamdump", host="codeberg",
         repo="MoriGM/dreamdump", ref="%{ddver}"),
    dict(pkg="discimagecreator", cmd="discimagecreator", aliases=["dic", "DiscImageCreator.out"],
         gen="dic", host="github", repo="saramibreak/DiscImageCreator", ref="%{diccommit}"),
    dict(pkg="discimagecreator", cmd="eccedc", gen="eccedc", host="github",
         repo="saramibreak/EccEdc", ref="%{eccedccommit}"),
    dict(pkg="discimagecreator", cmd="unscrambler", gen="unscrambler", host="github",
         repo="saramibreak/unscrambler", ref="%{unscramblcommit}"),
    dict(pkg="discimagecreator", cmd="dvdauth", gen="dvdauth", host="github",
         repo="saramibreak/DVDAuth", ref="%{dvdauthcommit}"),
    dict(pkg="aaru", cmd="aaru", gen="aaru", host="github", repo="aaru-dps/Aaru", ref="%{aarutag}"),
    dict(pkg="aaru5", cmd="aaru5", gen="aaru5", host="github", repo="aaru-dps/Aaru", ref="%{aarutag}"),
    dict(pkg="mpf", sub="cli", cmd="mpf-cli", gen="mpf_cli", host="github", repo="SabreTools/MPF",
         ref="%{mpfsnap}", ref_pick=r"[0-9]{14}\.([0-9a-f]{8,40})"),
    dict(pkg="mpf", sub="check", cmd="mpf-check", gen="mpf_check", host="github", repo="SabreTools/MPF",
         ref="%{mpfsnap}", ref_pick=r"[0-9]{14}\.([0-9a-f]{8,40})"),
]
PACKAGES = list(dict.fromkeys(c["pkg"] for c in COMPLETIONS))

RAW = {
    "github": "https://raw.githubusercontent.com/{repo}/{ref}/{path}",
    "codeberg": "https://codeberg.org/{repo}/raw/tag/{ref}/{path}",
}
COMPLETIONS_DIR = "/usr/share/bash-completion/completions"
BASH_COMPLETION = "/usr/share/bash-completion/bash_completion"
ORIGIN_RE = re.compile(r"^# GENERATED by scripts/completions/gen\.py from (\S+) at (\S+)\.$", re.M)
# EL8's rpm config has no %{bash_completions_dir}; every spec that uses it says what it stands for
FALLBACK_RE = re.compile(r"^%\{!\?bash_completions_dir:%global bash_completions_dir "
                         r"%\{_datadir\}/bash-completion/completions\}\s*$", re.M)
SECTION_RE = re.compile(r"^%(package|description|prep|build|install|check|clean|files|changelog|"
                        r"pre|post|preun|postun|pretrans|posttrans|verifyscript|"
                        r"trigger\w*|filetrigger\w*|transfiletrigger\w*)\b(.*)$", re.M)


def die(msg):
    sys.exit(f"gen.py: {msg}")


def spec_ref(c):
    """The upstream revision the Fedora spec builds, from the entry's 'ref'."""
    path = ROOT / "fedora" / c["pkg"] / f"{c['pkg']}.spec"
    text = path.read_text(encoding="utf-8")
    macros = dict(re.findall(r"^%global\s+(\w+)\s+(\S+)\s*$", text, re.M))
    m = re.search(r"^Version:\s*(\S+)\s*$", text, re.M)
    if not m:
        die(f"{path}: no Version:")
    macros["version"] = m.group(1)

    def expand(s, depth=0):
        if depth > 8:
            die(f"{path}: macro recursion in {s!r}")

        def one(mm):
            if mm.group(1) not in macros:
                die(f"{path}: macro %{{{mm.group(1)}}} is not defined")
            return macros[mm.group(1)]
        out = re.sub(r"%\{\??(\w+)\}", one, s)
        return expand(out, depth + 1) if "%" in out else out
    ref = expand(c["ref"])
    if "ref_pick" in c:  # the part of a macro that names the revision
        m = re.fullmatch(c["ref_pick"], ref)
        if not m:
            die(f"{path}: {ref!r} does not match {c['ref_pick']!r}")
        ref = m.group(1)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ref):
        die(f"{path}: odd revision {ref!r}")
    return ref


def origin(c, ref):
    return f"{c['repo']} at {ref}"


def targets(pkg, cmd):
    return [ROOT / "fedora" / pkg / f"{cmd}.bash-completion",
            ROOT / "opensuse" / pkg / f"{cmd}.bash-completion",
            ROOT / "ubuntu" / pkg / "debian" / "completions" / cmd]


def fetch(url):
    cache = os.environ.get("MEDIAPRES_COMPLETION_CACHE")
    hit = Path(cache) / hashlib.sha256(url.encode()).hexdigest() if cache else None
    if hit and hit.is_file():
        return hit.read_bytes().decode("utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "packaging-media-preservation"})
    for attempt in range(4):
        time.sleep(5 * attempt)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except OSError as e:  # HTTPError and URLError are OSErrors
            code = getattr(e, "code", None)
            if attempt == 3 or (code is not None and code < 500 and code != 429):
                die(f"{url}: {e}")
    if hit:
        hit.parent.mkdir(parents=True, exist_ok=True)
        hit.write_bytes(data)
    # some upstream files are Latin-1 (unscrambler.c); only ASCII is parsed
    return data.decode("utf-8", errors="replace")


def names(c):
    return [c["cmd"], *c.get("aliases", [])]


def binary_package(c):
    """The package a user installs to get the command (Debian's name too)."""
    return f"{c['pkg']}-{c['sub']}" if c.get("sub") else c["pkg"]


def files_section(spec, c):
    """The body of the %files section that ships the entry's command: the main
    package's, or `%files <sub>` / `%files -n <pkg>-<sub>`. None if missing."""
    heads = list(SECTION_RE.finditer(spec))
    for i, h in enumerate(heads):
        if h.group(1) != "files":
            continue
        args = re.sub(r"(^|\s)-f\s+\S+", " ", h.group(2)).split()
        wanted = ([c["sub"]], ["-n", binary_package(c)]) if c.get("sub") else ([],)
        if args in wanted:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(spec)
            return spec[h.end():end]
    return None


def generate(c):
    """The completion text for one entry, from the revision its spec pins."""
    mod = importlib.import_module(c["gen"])
    ref = spec_ref(c)
    src = {f: fetch(RAW[c["host"]].format(repo=c["repo"], ref=ref, path=f)) for f in mod.FILES}
    # libraries the upstream source pins itself (mpf: the NuGet versions in its csproj)
    try:
        for repo, dref, f in mod.deps(src) if hasattr(mod, "deps") else []:
            src[f"{repo}/{f}"] = fetch(RAW["github"].format(repo=repo, ref=dref, path=f))
    except mod.ParseError as e:
        die(f"{c['cmd']} at {ref}: {e} -- fix scripts/completions/{c['gen']}.py")
    try:
        model = mod.extract(src)
    except mod.ParseError as e:
        die(f"{c['cmd']} at {ref}: {e} -- the upstream parser changed shape; fix scripts/completions/{c['gen']}.py")
    text = mod.render(model, c["cmd"], origin(c, ref), names(c))
    if ORIGIN_RE.findall(text) != [(c["repo"], ref)]:
        die(f"{c['gen']}.py: the header does not name {origin(c, ref)} the way lint reads it")
    return text


def selected(args):
    """The entries of the packages named (all without arguments)."""
    if not args or args == ["all"]:
        return COMPLETIONS
    for a in args:
        if a not in PACKAGES:
            die(f"unknown package {a!r} (known: {' '.join(PACKAGES)})")
    return [c for c in COMPLETIONS if c["pkg"] in args]


def cmd_write(args):
    for c in selected(args):
        text = generate(c)
        for t in targets(c["pkg"], c["cmd"]):
            t.parent.mkdir(parents=True, exist_ok=True)
            old = t.read_text(encoding="utf-8") if t.exists() else None
            if old != text:
                t.write_text(text, encoding="utf-8")
                print(f"wrote {t.relative_to(ROOT)}")
    return 0


def cmd_check(args):
    rc, n = 0, 0
    for c in selected(args):
        text = generate(c)
        for t in targets(c["pkg"], c["cmd"]):
            n += 1
            old = t.read_text(encoding="utf-8") if t.exists() else ""
            if old != text:
                rc = 1
                print(f"{t.relative_to(ROOT)}: not what the generator makes -- run scripts/completions/gen.py write {c['pkg']}")
                sys.stdout.writelines(difflib.unified_diff(
                    old.splitlines(True), text.splitlines(True), "committed", "generated", n=1))
    if rc == 0:
        print(f"completions: {n} files are what the generator makes from the pinned source")
    return rc


def cmd_lint(_args):
    bad = []
    expected = set()
    n = 0
    for c in COMPLETIONS:
        pkg, cmd, bpkg = c["pkg"], c["cmd"], binary_package(c)
        ref = spec_ref(c)
        fspec = (ROOT / "fedora" / pkg / f"{pkg}.spec").read_text(encoding="utf-8")
        ospec = (ROOT / "opensuse" / pkg / f"{pkg}.spec").read_text(encoding="utf-8")
        inst = ROOT / "ubuntu" / pkg / "debian" / f"{bpkg}.install"
        dinst = inst.read_text(encoding="utf-8") if inst.exists() else ""
        links = ROOT / "ubuntu" / pkg / "debian" / f"{bpkg}.links"
        dlinks = links.read_text(encoding="utf-8").splitlines() if links.exists() else []
        copies = targets(pkg, cmd)
        expected.update(str(f.relative_to(ROOT)) for f in copies)
        texts = []
        for f in copies:
            if not f.is_file():
                bad.append(f"{f.relative_to(ROOT)}: missing -- run scripts/completions/gen.py write {pkg}")
                continue
            texts.append((f, f.read_text(encoding="utf-8")))
        for f, t in texts[1:]:
            if t != texts[0][1]:
                bad.append(f"{f.relative_to(ROOT)}: differs from {texts[0][0].relative_to(ROOT)}")
        for f, t in texts[:1]:
            n += 1
            got = ORIGIN_RE.findall(t)
            if got != [(c["repo"], ref)]:
                bad.append(f"{f.relative_to(ROOT)}: generated from {got or 'nothing it names'}, "
                           f"but the spec builds {c['repo']} at {ref} -- run scripts/completions/gen.py write {pkg}")
        # every recipe installs it, under the command's name, in the package that ships the command:
        # its Source: line, an install of exactly that Source, and the path in that package's %files
        src_re = re.compile(r"^Source(\d+):\s*\S*/?" + re.escape(f"{cmd}.bash-completion") + r"\s*$", re.M)
        section = f"%files {c['sub']}" if c.get("sub") else "%files"
        for lane, spec in (("fedora", fspec), ("opensuse", ospec)):
            where = f"{lane}/{pkg}/{pkg}.spec"
            m = src_re.search(spec)
            if not m:
                bad.append(f"{where}: no Source: line for {cmd}.bash-completion")
            elif not re.search(r"^install\s.*%\{SOURCE" + m.group(1) + r"\}\s+%\{buildroot\}%\{bash_completions_dir\}/"
                               + re.escape(cmd) + r"\s*$", spec, re.M):
                bad.append(f"{where}: does not install Source{m.group(1)} as %{{bash_completions_dir}}/{cmd}")
            if not FALLBACK_RE.search(spec):
                bad.append(f"{where}: no %{{bash_completions_dir}} fallback for EL8's rpm config")
            listed = files_section(spec, c)
            if listed is None:
                bad.append(f"{where}: no {section} section, which would ship {cmd}")
            else:
                for name in names(c):
                    if not re.search(r"^%\{bash_completions_dir\}/" + re.escape(name) + r"\s*$", listed, re.M):
                        bad.append(f"{where}: {section} does not list %{{bash_completions_dir}}/{name}")
        want = f"debian/completions/{cmd} {COMPLETIONS_DIR.lstrip('/')}/"
        if want not in dinst.splitlines():
            bad.append(f"ubuntu/{pkg}/debian/{bpkg}.install: missing the line '{want}'")
        # every other name it is installed as: a symlink to it in every lane
        for alias in c.get("aliases", []):
            link_re = re.compile(r"^ln -s " + re.escape(cmd) + r" %\{buildroot\}%\{bash_completions_dir\}/"
                                 + re.escape(alias) + r"\s*$", re.M)
            for lane, spec in (("fedora", fspec), ("opensuse", ospec)):
                if not link_re.search(spec):
                    bad.append(f"{lane}/{pkg}/{pkg}.spec: does not link .../completions/{alias} -> {cmd}")
            want = f"{COMPLETIONS_DIR.lstrip('/')}/{cmd} {COMPLETIONS_DIR.lstrip('/')}/{alias}"
            if want not in dlinks:
                bad.append(f"ubuntu/{pkg}/debian/{bpkg}.links: missing the line '{want}'")
    # and nothing completes a command no entry declares
    tracked = subprocess.run(["git", "-C", str(ROOT), "ls-files", "*.bash-completion", "ubuntu/*/debian/completions/*"],
                             capture_output=True, text=True, check=True).stdout.split()
    for t in tracked:
        if t not in expected:
            bad.append(f"{t}: no entry in scripts/completions/gen.py COMPLETIONS declares it")
    if n == 0:
        bad.append("no completion checked -- COMPLETIONS is empty or the layout moved")
    for b in bad:
        print(b)
    if bad:
        return 1
    print(f"completions: {n} commands, three identical copies each, at the revision their spec pins, installed by every recipe")
    return 0


def readline_words(line):
    """Split like readline with the default COMP_WORDBREAKS as far as we need it:
    blanks separate words, and a run of '=' or ':' is a word of its own."""
    words, tok, prev = [], "", None
    for ch in line:
        if ch == " ":
            if tok:
                words.append(tok)
            tok, prev = "", None
            continue
        cls = "brk" if ch in "=:" else "word"
        if prev is not None and cls != prev and tok:
            words.append(tok)
            tok = ""
        tok += ch
        prev = cls
    if tok:
        words.append(tok)
    if line.endswith(" "):
        words.append("")
    return words


def cmd_smoke(_args):
    if not Path(BASH_COMPLETION).is_file():
        print(f"smoke: {BASH_COMPLETION} is not installed -- not measured is not clean")
        return 2
    bad, n = [], 0
    for c in COMPLETIONS:
        mod = importlib.import_module(c["gen"])
        cmd = c["cmd"]
        f = targets(c["pkg"], cmd)[0]
        lines = [(line.format(cmd=cmd), inc, exc) for line, inc, exc in mod.SMOKE]
        script = [f"source {shlex.quote(BASH_COMPLETION)} || exit 3",
                  f"source {shlex.quote(str(f))} || exit 3",
                  "compopt() { :; }",
                  *[f"complete -p {shlex.quote(a)} >/dev/null || exit 4" for a in names(c)],
                  f"spec=$(complete -p {shlex.quote(cmd)}) || exit 4",
                  'fn=${spec#*-F }; fn=${fn%% *}']
        for line, _inc, _exc in lines:
            w = readline_words(line)
            script += [f"COMP_WORDS=({' '.join(shlex.quote(x) for x in w)})",
                       f"COMP_CWORD={len(w) - 1}",
                       f"COMP_LINE={shlex.quote(line)}",
                       f"COMP_POINT={len(line)}",
                       "COMPREPLY=()",
                       '"$fn" "${COMP_WORDS[0]}" "${COMP_WORDS[COMP_CWORD]}" "${COMP_WORDS[COMP_CWORD-1]:-}"',
                       "printf '%s\\n' \"${COMPREPLY[@]}\"",
                       "echo '\x1e'"]
        r = subprocess.run(["bash", "--norc", "--noprofile", "-c", "\n".join(script)],
                           capture_output=True, text=True, cwd=ROOT, timeout=60)
        outs = r.stdout.split("\x1e\n")
        if r.returncode != 0 or r.stderr.strip() or len(outs) != len(lines) + 1:
            bad.append(f"{f.relative_to(ROOT)}: bash rc={r.returncode} stderr={r.stderr.strip()[:500]!r}")
            continue
        for (line, inc, exc), out in zip(lines, outs[:-1], strict=True):
            n += 1
            got = set(x for x in out.split("\n") if x)
            if not inc <= got:
                bad.append(f"{cmd}: {line!r} does not offer {sorted(inc - got)} (offered: {sorted(got)[:12]})")
            if exc == "*" and got:
                bad.append(f"{cmd}: {line!r} must offer nothing, offered {sorted(got)[:12]}")
            elif exc != "*" and got & exc:
                bad.append(f"{cmd}: {line!r} offers {sorted(got & exc)}")
    for b in bad:
        print(b)
    if bad:
        return 1
    if n == 0:
        print("smoke: no case run")
        return 1
    print(f"completions: {n} smoke completions answered as expected")
    return 0


def cmd_has(args):
    if len(args) != 1:
        die("usage: gen.py has <package>")
    print("yes" if args[0] in PACKAGES else "no")
    return 0


def main():
    cmds = {"write": cmd_write, "check": cmd_check, "lint": cmd_lint, "smoke": cmd_smoke, "has": cmd_has}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        die(__doc__.strip().split("\n\n")[1])
    return cmds[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
