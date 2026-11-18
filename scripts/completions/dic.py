"""DiscImageCreator: read the command line out of the source, render a bash completion.

The parser is checkArg() in DiscImageCreator.cpp: argv[1] is the mode, matched
exactly; a fixed number of positional arguments follows; then options, each a
word starting with '/'. An option takes its values from the following words
that do not start with '/', each value optional. What a mode accepts is read
from its option loop (`for (INT i = N; i <= argc; i++)`: N - 3 positionals,
then one if/else-if clause per option); what an option takes is read from its
SetOption*() handler. printUsage() names the positionals and is compared with
the parser: the header lists where the two disagree.
"""
import re

import clex

FILES = ["DiscImageCreator/DiscImageCreator.cpp", "DiscImageCreator/execTapeCmd.cpp"]

# what each positional name in printUsage() is
POSITIONAL_KINDS = [
    (r"DriveLetter", "drive"),
    (r"Filename|plextor image file|optiarc image file", "file"),
    (r"Subfile", "file:sub"),
    (r"Mdsfile", "file:mds"),
    (r"DriveSpeed\(\d+-\d+\)|StartLBA|EndLBA\+1|AllSectorLength|StartLBAOfSecuritySector\d+", "int"),
]
# modes whose DriveLetter is a floppy or other removable disk, not an optical drive
DISK_MODES = ("fd", "disk")
# printUsage() lists these for the mode, the parser rejects them ("Unknown
# option"). Known at the pin this was written for; anything new stops the
# generator, so a parser that changed shape cannot pass as a usage mistake.
KNOWN_DOC_ONLY = {("gd", "/c2new"), ("data", "/c2new"), ("audio", "/c2new")}

SMOKE = [
    ("{cmd} ", {"cd", "swap", "dvd", "bd", "fd", "merge", "sub", "/v"}, {"tape"}),
    ("{cmd} cd d f 8 ", {"/be", "/c2", "/fdesc", "/am", "/mr"}, {"/74"}),
    ("{cmd} swap d f 8 /", {"/74", "/toc"}, set()),
    ("{cmd} cd d f ", set(), "*"),
    ("{cmd} cd d f 8 /be ", {"raw", "pack"}, {"/q"}),
    ("{cmd} cd d f 8 /fdesc sync ", {"edc", "ecc"}, {"sync", "/q"}),
    ("{cmd} cd d f 8 /c2 ", set(), "*"),
    ("{cmd} cd d f 8 /c2 1 2 3 4 5 6 ", {"/q"}, set()),
    ("{cmd} gd d f 8 /", {"/be"}, {"/c2new"}),
    ("{cmd} sacd d f 8 /", set(), "*"),
    ("{cmd} dvd d f 8 /r ", set(), "*"),
    ("{cmd} data d f 8 0 100 /r ", {"/q", "/t"}, set()),
    ("{cmd} stop d ", set(), "*"),
]


class ParseError(Exception):
    pass


def die(msg):
    raise ParseError(f"DiscImageCreator: {msg}")


def handler_slots(src, name):
    """(kind, number of values, enum words) of SetOption<name>()."""
    try:
        body = clex.function_body(src, "SetOption" + name)
    except clex.CError as e:
        die(str(e))
    bl = clex.blank(body)
    takes = [m.start() for m in re.finditer(r"\(\*i\)\+\+", bl)]
    ints = re.findall(r"_tcsto(?:u)?l\(argv\[\(\*i\)\+\+\]", body)
    words = []
    for w in re.findall(r'_tcsncmp\(argv\[\*i\], _T\("([^"]*)"\)', body):
        if w != "/" and w not in words:
            words.append(w)
    if ints and words:
        die(f"SetOption{name}() mixes numbers and words")
    if takes and not ints and not words:
        die(f"SetOption{name}() takes a value the generator cannot classify")
    # one value per nesting level that consumes one (/c2: six, /be: one of two)
    n = len({clex.depth_at(bl, p) for p in takes})
    return ("enum" if words else "int" if n else "none", n, tuple(words))


def option_clauses(loop_body):
    """[(condition, body)] of the top-level if / else if clauses of a loop body."""
    bl = clex.blank(loop_body)
    out, pos = [], 0
    while True:
        m = re.compile(r"\bif\s*\(").search(bl, pos)
        if not m:
            return out
        if clex.depth_at(bl, m.start()) != 0:
            pos = m.end()
            continue
        close = clex.match(bl, m.end() - 1, "(", ")")
        ob = re.match(r"\s*\{", bl[close:])
        if not ob:
            die("an option clause without braces")
        open_at = close + ob.end() - 1
        end = clex.match(bl, open_at)
        out.append((loop_body[m.end():close - 1], loop_body[open_at + 1:end - 1]))
        pos = end


def parse_usage(text):
    """{mode: (positional names, documented options)} from printUsage()'s text."""
    lines = text.split("\n")
    if "Usage" not in lines:
        die("printUsage() no longer starts its list with 'Usage'")
    entries, cur = {}, None
    for line in lines[lines.index("Usage") + 1:]:
        if not line.startswith("\t"):
            break  # next section (Option ...)
        if line.startswith("\t\t"):
            continue  # description
        m = re.match(r"\t(\S+)([^\t]*)", line)
        if m:
            cur = m.group(1)
            entries.setdefault(cur, []).append(m.group(2))
        elif cur and re.match(r"\t +\S", line):
            entries[cur].append(line)
    out = {}
    for mode, parts in entries.items():
        s = " ".join(parts)
        pos = re.findall(r"<([^>]+)>|(?<!\S)(:)(?!\S)", s)
        names = [a or b for a, b in pos]
        opts = set(re.findall(r"(?<![\w<])(/[a-z0-9]+)", re.sub(r"<[^>]*>", "", s)))
        out[mode] = (names, opts)
    return out


def positional_kinds(mode, names, count):
    kinds = []
    for name in names:
        if name == ":":
            continue
        for rx, kind in POSITIONAL_KINDS:
            if re.fullmatch(rx, name):
                kinds.append("disk" if kind == "drive" and mode in DISK_MODES else kind)
                break
        else:
            die(f"positional <{name}> of {mode}: the generator does not know what it is")
    if ":" in names and kinds and len(kinds) <= count:
        kinds += [kinds[-1]] * (count - len(kinds))  # <...Sector1> : <...Sector16>
    if len(kinds) != count:
        die(f"{mode}: printUsage() names {len(kinds)} positionals, the parser reads {count}")
    return kinds


def extract(src):
    cpp = src["DiscImageCreator/DiscImageCreator.cpp"]
    try:
        body = clex.function_body(cpp, "checkArg")
        usage_src = clex.function_body(cpp, "printUsage")
        tape = clex.function_body(src["DiscImageCreator/execTapeCmd.cpp"], "ReadTape")
    except clex.CError as e:
        die(str(e))
    for name, b in (("checkArg", body), ("printUsage", usage_src)):
        if re.search(r"^\s*#\s*if", b, re.M):
            die(f"{name}() gained an #if: the generator reads it as one platform")
    usage = parse_usage(clex.c_strings(usage_src))

    bl = clex.blank(body)
    lits = [(m.start(), m.end(), m.group(1))
            for m in re.finditer(r'_tcsncmp\(argv\[1\], _T\("([^"]+)"\)', body)]
    if len(lits) < 20:
        die(f"only {len(lits)} modes found in checkArg()")
    groups = []  # [[mode...], start, end]: modes that share one branch
    for start, end, name in lits:
        if groups and "{" not in bl[groups[-1][2]:start]:
            groups[-1][0].append(name)
            groups[-1][2] = end
        else:
            groups.append([[name], start, end])

    modes, dead, hidden, doc_only, slots = {}, [], [], [], {}
    for gi, (names, _start, end) in enumerate(groups):
        stop = groups[gi + 1][1] if gi + 1 < len(groups) else len(body)
        block, bblock = body[end:stop], bl[end:stop]
        loops = list(re.finditer(r"for \(INT i = (\d+); i <= argc; i\+\+\) \{", block))
        if len(loops) > 1:
            die(f"{'/'.join(names)}: more than one option loop")
        per_mode = {n: [] for n in names}
        count = None
        if loops:
            loop = loops[0]
            count = int(loop.group(1)) - 3
            lb_end = clex.match(bblock, loop.end() - 1)
            loop_body = block[loop.end():lb_end - 1]
            sets_len = re.search(r"cmdLen = _tcslen\(argv\[i - 1\]\)", loop_body)
            for cond, cbody in option_clauses(loop_body):
                opts = re.findall(r'_tcsncmp\(argv\[i - 1\], _T\("(/[^"]*)"\)', cond)
                if not opts:
                    die(f"{'/'.join(names)}: an option clause with no option in it: {cond.strip()[:80]}")
                gate = re.findall(r"\*pExecType == (\w+)", cond)
                for g in gate:
                    if g not in names:
                        die(f"{'/'.join(names)}: option gated on exec type {g}, not one of the branch's modes")
                if re.search(r"(?<![*\w])i\s*(\+\+|\+=)|\+\+\s*i\b", cbody):
                    die(f"{'/'.join(names)}: {opts} reads a value inline, not through a SetOption*() handler")
                handlers = sorted(set(re.findall(r"SetOption(\w+)\(", cbody)))
                if len(handlers) > 1:
                    die(f"{'/'.join(names)}: {opts} calls more than one handler")
                sl = handler_slots(cpp, handlers[0]) if handlers else ("none", 0, ())
                for n in gate or names:
                    for o in dict.fromkeys(opts):
                        if not sets_len and "cmdLen ==" in cond:
                            dead.append((n, o))  # compared against a stale cmdLen: never matches
                            continue
                        if o not in per_mode[n]:
                            per_mode[n].append(o)
                            slots[(n, o)] = sl
        for n in names:
            if n not in usage:
                continue
            doc_names, doc_opts = usage[n]
            pcount = count if count is not None else len(doc_names)
            modes[n] = {"kinds": positional_kinds(n, doc_names, pcount), "opts": per_mode[n]}
            hidden += [(n, o) for o in per_mode[n] if o not in doc_opts]
            doc_only += [(n, o) for o in sorted(doc_opts) if o not in per_mode[n] and (n, o) not in dead]
        for n in names:
            if n in usage:
                continue
            if n == "tape" and re.search(r"#else\s+UNREFERENCED_PARAMETER\(pszFullPath\);\s+return TRUE;\s+#endif\s*$", tape):
                continue  # ReadTape() is an empty stub on Linux
            die(f"mode {n} is not in printUsage(): the generator does not know its positionals")
    for n in usage:
        if n not in modes:
            die(f"printUsage() lists mode {n}, the parser does not accept it")
    new = sorted(set(doc_only) - KNOWN_DOC_ONLY)
    if new:
        die(f"printUsage() lists options the parser rejects, new since the generator was written: {new}")
    if "tape" in modes or "cd" not in modes or len(modes["cd"]["opts"]) < 20:
        die("the mode table does not look like DiscImageCreator's")
    return {"modes": modes, "slots": slots, "hidden": hidden, "doc_only": doc_only, "dead": dead,
            "noop": ["tape"] if "tape" in [x[2] for x in lits] else []}


def pairs(items):
    """'cd: /am /mr; swap: /toc' from [(mode, opt)...], grouped by mode, source order."""
    by = {}
    for m, o in items:
        by.setdefault(m, []).append(o)
    return [f"{m}: {' '.join(os_)}" for m, os_ in by.items()]


def wrap(prefix, parts, width=79):
    lines, cur = [], prefix
    for p in parts:
        piece = p if cur == prefix else "; " + p
        if len(cur) + len(piece) > width and cur != prefix:
            lines.append(cur + ";")
            cur = "#   " + p
        else:
            cur += piece
    lines.append(cur)
    return "\n".join(lines)


def render(model, cmd, origin, names):
    fn = "_mediapres_" + re.sub(r"[^A-Za-z0-9]", "_", cmd)
    modes = model["modes"]
    head = []
    if model["hidden"]:
        head.append(wrap("# Not in its usage text: ", pairs(model["hidden"])))
    if model["doc_only"]:
        head.append(wrap("# In its usage text, but rejected by the parser (not offered): ",
                         pairs(model["doc_only"])))
    if model["dead"]:
        head.append(wrap("# Parsed, but never matched (not offered): ", pairs(model["dead"])))
    if model["noop"]:
        head.append(f"# Accepted, but does nothing on Linux (not offered): {' '.join(model['noop'])}")

    # one case arm per distinct (positional kinds, options)
    arms = {}
    for m, d in modes.items():
        arms.setdefault((tuple(d["kinds"]), tuple(d["opts"])), []).append(m)
    case_modes = []
    for (kinds, opts), ms in arms.items():
        pat = " | ".join(ms)
        case_modes.append(f"        {pat})\n            kinds=({' '.join(kinds)})\n"
                          f"            opts='{' '.join(opts)}'\n            ;;")
    # one arm per option and value signature
    sig = {}
    for (m, o), (kind, n, words) in model["slots"].items():
        if kind == "none" or o not in modes.get(m, {"opts": []})["opts"]:
            continue
        sig.setdefault((o, kind, n, tuple(words)), []).append(m)
    case_vals = []
    for (o, kind, n, words), ms in sig.items():
        what = f"vals='{' '.join(words)}' nval={n}" if kind == "enum" else f"nint={n}"
        case_vals.append(f"            @({'|'.join(ms)}):{o}) {what} ;;")

    title = f"# bash completion for {cmd}".ljust(64) + "-*- shell-script -*-"
    return f"""{title}
# shellcheck shell=bash
#
# GENERATED by scripts/completions/gen.py from {origin}.
# Do not edit: change the generator, then run `scripts/completions/gen.py write`.
#
# DiscImageCreator takes a mode, the mode's positional arguments, then options.
# An option's values are the words after it that do not start with '/', each
# one optional.
{chr(10).join(head)}

{fn}_drives()
{{
    local d
    COMPREPLY=()
    for d in /dev/sr[0-9]*; do
        [[ -e $d && $d == "$cur"* ]] && COMPREPLY+=("$d")
    done
    ((${{#COMPREPLY[@]}})) || _filedir
}}

# fd and disk read a whole block device: floppy drives and other removable disks
{fn}_disks()
{{
    local s d
    COMPREPLY=()
    for s in /sys/block/fd[0-9]* /sys/block/sd[a-z]*; do
        [[ -r $s/removable && $(<"$s/removable") == 1 ]] || continue
        d=/dev/${{s##*/}}
        [[ -e $d && $d == "$cur"* ]] && COMPREPLY+=("$d")
    done
    ((${{#COMPREPLY[@]}})) || _filedir
}}

{fn}()
{{
    # shellcheck disable=SC2034  # words is filled in by _init_completion
    local cur prev words cword
    _init_completion || return

    if ((cword == 1)); then
        mapfile -t COMPREPLY < <(compgen -W '{" ".join(modes)}' -- "$cur")
        return
    fi

    local -a kinds
    local opts
    case ${{words[1]}} in
{chr(10).join(case_modes)}
        *)
            return
            ;;
    esac

    local n=$((cword - 2))
    if ((n < ${{#kinds[@]}})); then
        case ${{kinds[n]}} in
            drive) {fn}_drives ;;
            disk) {fn}_disks ;;
            file) _filedir ;;
            file:sub) _filedir sub ;;
            file:mds) _filedir mds ;;
        esac
        return
    fi

    # inside an option's values?
    local j opt=""
    for ((j = cword - 1; j >= 2 + ${{#kinds[@]}}; j--)); do
        if [[ ${{words[j]}} == /* ]]; then
            opt=${{words[j]}}
            break
        fi
    done
    if [[ -n $opt && $cur != /* ]]; then
        local k=$((cword - j - 1)) nint=0 nval=0 vals="" w used
        case ${{words[1]}}:$opt in
{chr(10).join(case_vals)}
        esac
        if ((k < nval)); then
            used=" ${{words[*]:j+1:k}} "
            COMPREPLY=()
            for w in $vals; do
                [[ $used != *" $w "* && $w == "$cur"* ]] && COMPREPLY+=("$w")
            done
            return
        fi
        ((k < nint)) && return
    fi
    mapfile -t COMPREPLY < <(compgen -W "$opts" -- "$cur")
}} &&
    complete -F {fn} {" ".join(names)}

# ex: filetype=sh
"""
