"""aaru5 (Aaru 5.x, System.CommandLine 2.0.0-beta1): the root from Aaru/Main.cs,
the rest from the Command classes under Aaru/Commands, which build the tree in
their constructors (base("name", ...), AddAlias, AddCommand, Add(new Option
...), AddArgument, Handler = CommandHandler.Create(... Invoke)).

System.CommandLine passes an option to the handler by name: the option's name
without its dashes against the handler's parameter names. An option that no
parameter matches is parsed and then dropped (measured: `image decode --start
1` reaches the command as 0), so it is not offered; the header names it. -v and
-d are global and work before and after the command. --pause is global too, but
Main reads it from the root only, so it is offered there only. A global option
given at two levels makes System.CommandLine throw (measured: `aaru5 -d image
-d info x`), so one that is already on the line is not offered again.

What the source cannot say is a table here, and anything new stops the
generator: a string option or an argument nobody classified, a constructor
statement or option property this file does not know, a System.CommandLine
version whose built-in help, version option and directives nobody looked at.
Values aaru5 only knows at run time (image formats, encodings, filesystem
namespaces, -O keys) are not offered; its own listing commands print them.
"""
import re
import textwrap

from aaru import ParseError, blank_strings, close, literal, no_comments, q, wrap

__all__ = ["FILES", "SMOKE", "ParseError", "extract", "render"]

COMMANDS = ["Configure.cs", "Database/DatabaseFamily.cs", "Database/Statistics.cs", "Database/Update.cs",
            "Device/DeviceFamily.cs", "Device/DeviceReport.cs", "Device/Info.cs", "Device/List.cs",
            "Filesystem/ExtractFiles.cs", "Filesystem/FilesystemFamily.cs", "Filesystem/Info.cs",
            "Filesystem/Ls.cs", "Filesystem/Options.cs", "Formats.cs", "Image/Checksum.cs", "Image/Compare.cs",
            "Image/Convert.cs", "Image/CreateSidecar.cs", "Image/Decode.cs", "Image/Entropy.cs",
            "Image/ImageFamily.cs", "Image/Info.cs", "Image/Options.cs", "Image/Print.cs", "Image/Verify.cs",
            "ListEncodings.cs", "ListNamespaces.cs", "Media/Dump.cs", "Media/Info.cs", "Media/MediaFamily.cs",
            "Media/Scan.cs", "Remote.cs"]
MAIN = "Aaru/Main.cs"
CSPROJ = "Aaru/Aaru.csproj"
DEVICE = "Aaru.Devices/Device/Constructor.cs"
FILES = [MAIN, CSPROJ, DEVICE] + [f"Aaru/Commands/{f}" for f in COMMANDS]

SMOKE = [
    ("{cmd} ", {"database", "db", "image", "i", "media", "fs", "fi", "remote", "list-encodings"},
     {"-v", "convert", "gui"}),
    ("{cmd} -", {"-v", "--verbose", "-d", "--debug", "--pause", "--version", "-h", "--help"}, {"-?", "/h"}),
    ("{cmd} image -", {"-v", "--debug", "-h"}, {"--pause", "--version", "--format"}),
    ("{cmd} image convert -", {"--format", "-O", "--fix-subchannel-position", "--media-sequence", "-v"},
     {"--drive-revision", "--drive-serial", "--media-lastsequence", "--media-serial", "--pause"}),
    ("{cmd} -v image convert -", {"-d", "--format"}, {"-v", "--verbose"}),
    ("{cmd} i -d convert --", {"--format", "--verbose"}, {"--debug"}),
    ("{cmd} image convert -fd --", {"--format"}, {"--debug"}),
    ("{cmd} image decode -", {"--length", "-l", "-p"}, {"--start", "-s"}),
    ("{cmd} image create-sidecar -", {"--block-size", "-b"}, {"--encoding", "-e"}),
    ("{cmd} media dump --subchannel ", {"any", "rw", "rw-or-pq", "pq", "none"}, set()),
    ("{cmd} m dump --subchannel=r", {"rw", "rw-or-pq"}, {"any"}),
    ("{cmd} media dump --trim ", {"false", "true"}, set()),
    ("{cmd} media dump --force ", set(), {"false", "true"}),
    ("{cmd} image checksum -c ", {"false", "true"}, set()),
    ("{cmd} image decode -l ", {"all"}, set()),
    ("{cmd} image convert -c ", set(), "*"),
    ("{cmd} image convert -p ", set(), "*"),
    ("{cmd} image convert -fc ", set(), "*"),
    ("{cmd} image convert -c64 ", {"README.md"}, {"-v", "false"}),
    ("{cmd} [parse] image ", {"convert", "info"}, {"image"}),
    ("{cmd} image info -- ", set(), "*"),
    ("{cmd} image info @args ", set(), "*"),
    ("{cmd} IMAGE ", set(), "*"),
    ("{cmd} fs ls -", {"--long-format", "--namespace", "-O"}, {"--pause"}),
]

# System.CommandLine adds help, --version and directives of its own (no code in
# the aaru tree). Read from the binary at this version; a new one must be looked
# at before it is trusted.
SCL = {
    "2.0.0-beta1.20104.2": dict(help=["-h", "--help"], version="--version", unoffered_help="-?, /h, /?",
                                directives="[parse], [suggest], [debug], [env:NAME=VALUE]"),
}
# What a string option's value is, by its long name: file, dir, text (free text
# or a number), words (the strings the handler compares it with), or runtime
# (a list aaru5 builds from its plugins; not offered).
STRING_OPTIONS = {
    "--output-prefix": "file", "--cicm-xml": "file", "--resume-file": "file", "--mhdd-log": "file",
    "--ibg-log": "file",
    "--comments": "text", "--creator": "text", "--drive-manufacturer": "text", "--drive-model": "text",
    "--drive-revision": "text", "--drive-serial": "text", "--media-barcode": "text",
    "--media-manufacturer": "text", "--media-model": "text", "--media-partnumber": "text",
    "--media-serial": "text", "--media-title": "text", "--options": "text", "--geometry": "text",
    "--format": "runtime", "--encoding": "runtime", "--namespace": "runtime",
    "--subchannel": "words", "--length": "words",
}
# Argument names: what goes there.
ARGUMENTS = {
    "image-path": "file", "image-path1": "file", "image-path2": "file", "input-path": "file",
    "output-path": "file", "output-dir": "dir", "device-path": "device", "host": "host",
    "aaru-remote-host": "host",
}
ARITIES = {"ExactlyOne": False, "ZeroOrOne": True}
NUMBER_TYPES = {"int", "uint", "long", "ulong", "short", "ushort", "byte", "sbyte", "double", "float"}
ROOT_CALLS = {"AddGlobalOption", "AddCommand", "Description", "Invoke", "Parse"}


def statements(text, start, end):
    """The top-level statements of text[start:end] (a block's inside), stripped."""
    bl = blank_strings(text)
    out, s, i = [], start, start
    while i < end:
        ch = bl[i]
        if ch in "({[":
            i = close(bl, i, ch, {"(": ")", "{": "}", "[": "]"}[ch]) + 1
            continue
        if ch == ";":
            out.append(text[s:i].strip())
            s = i + 1
        i += 1
    if text[s:end].strip():
        raise ParseError(f"statement without `;`: {text[s:end].strip()[:60]!r}")
    return out


def top_split(text):
    """Split at the commas that are not inside brackets or strings."""
    bl = blank_strings(text)
    parts, s, i = [], 0, 0
    while i < len(text):
        ch = bl[i]
        if ch in "({[":
            i = close(bl, i, ch, {"(": ")", "{": "}", "[": "]"}[ch]) + 1
            continue
        if ch == ",":
            parts.append(text[s:i].strip())
            s = i + 1
        i += 1
    parts.append(text[s:].strip())
    return [p for p in parts if p]


def call_args(text, open_paren):
    """(inside, index past the ')') of the call whose '(' is at open_paren."""
    end = close(blank_strings(text), open_paren, "(", ")")
    return text[open_paren + 1:end], end + 1


def initializer(where, text):
    """`{ A = x, B = y }` -> {'A': 'x', 'B': 'y'}"""
    m = re.fullmatch(r"\{(.*)\}", text.strip(), re.S)
    if not m:
        raise ParseError(f"{where}: odd object initializer {text.strip()[:60]!r}")
    out = {}
    for part in top_split(m.group(1)):
        kv = re.fullmatch(r"(\w+)\s*=\s*(.+)", part, re.S)
        if not kv:
            raise ParseError(f"{where}: odd initializer entry {part[:60]!r}")
        out[kv.group(1)] = kv.group(2).strip()
    return out


def new_option(where, expr):
    """`new Option(names, "desc") { Argument = new Argument<T>(() => d), Required = b }`
    -> dict(names, type, default)"""
    m = re.match(r"new\s+Option\s*\(", expr)
    if not m:
        raise ParseError(f"{where}: not a `new Option(...)`: {expr[:60]!r}")
    inside, past = call_args(expr, m.end() - 1)
    args = top_split(inside)
    if len(args) != 2:
        raise ParseError(f"{where}: Option({inside[:60]!r}) does not take names and a description")
    arr = re.fullmatch(r"new\s*(?:string\s*)?\[\]\s*\{(.*)\}", args[0], re.S)
    names = [literal(x) for x in top_split(arr.group(1))] if arr else [literal(args[0])]
    if not all(re.fullmatch(r"-[A-Za-z]|--[a-z0-9][a-z0-9-]*", n) for n in names):
        raise ParseError(f"{where}: odd option names {names}")
    init = initializer(where, expr[past:]) if expr[past:].strip() else {}
    if set(init) - {"Argument", "Required"}:
        raise ParseError(f"{where}: {names[0]}: option property {sorted(set(init) - {'Argument', 'Required'})}")
    a = re.fullmatch(r"new\s+Argument<([\w.]+)>\s*\(\s*(?:\(\)\s*=>\s*(.+?))?\s*\)", init.get("Argument", ""), re.S)
    if not a:
        raise ParseError(f"{where}: {names[0]}: Argument {init.get('Argument')!r}")
    if init.get("Required", "false") not in ("false", "true"):
        raise ParseError(f"{where}: {names[0]}: Required = {init['Required']}")
    return dict(names=names, type=a.group(1), default=(a.group(2) or "").strip())


def new_argument(where, expr):
    m = re.fullmatch(r"new\s+Argument<([\w.]+)>\s*(\{.*\})", expr, re.S)
    if not m:
        raise ParseError(f"{where}: odd argument {expr[:60]!r}")
    init = initializer(where, m.group(2))
    if set(init) - {"Arity", "Description", "Name"}:
        raise ParseError(f"{where}: argument property {sorted(set(init) - {'Arity', 'Description', 'Name'})}")
    arity = re.fullmatch(r"ArgumentArity\.(\w+)", init.get("Arity", ""))
    if not arity or arity.group(1) not in ARITIES:
        raise ParseError(f"{where}: argument arity {init.get('Arity')!r}")
    name = literal(init.get("Name", "''"))
    kind = ARGUMENTS.get(name)
    if kind is None:
        raise ParseError(f"{where}: argument <{name}> is not in ARGUMENTS")
    return dict(name=name, kind=kind, optional=ARITIES[arity.group(1)])


def params(where, text, method):
    """The parameter names of the one method `method` in text."""
    hits = list(re.finditer(rf"\b(?:int|void|Task<int>)\s+{method}\s*\(", text))
    if len(hits) != 1:
        raise ParseError(f"{where}: {len(hits)} methods named {method}")
    inside, _ = call_args(text, hits[0].end() - 1)
    out = []
    for p in top_split(inside):
        # @namespace: a keyword used as a name; the method's parameter is `namespace`
        m = re.fullmatch(r"(?:\[[^\]]*\]\s*)*[\w.<>?\[\]]+\s+@?(\w+)(?:\s*=.+)?", p, re.S)
        if not m:
            raise ParseError(f"{where}: odd parameter {p!r}")
        out.append(m.group(1))
    return out


def norm(name):
    return name.lstrip("-").replace("-", "").lower()


def bound_param(where, names, plist):
    """The handler parameter an option or argument binds to, or None."""
    by_long = [p for p in plist if p.lower() == norm(max(names, key=len))]
    by_any = [p for p in plist if p.lower() in {norm(n) for n in names}]
    if by_long != by_any:
        raise ParseError(f"{where}: {names} would bind through a short name only ({by_any}); measure that")
    return by_long[0] if by_long else None


def words_for(where, text, param):
    """The strings the handler compares a parameter with (it lower-cases it first)."""
    vals = []
    sw = re.search(rf"switch\s*\(\s*{param}\??\.ToLowerInvariant\(\)\s*\)\s*\{{", text)
    if sw:
        bl = blank_strings(text)
        end = close(bl, sw.end() - 1)
        vals += re.findall(r'\bcase\s+"([^"]+)"\s*:', text[sw.end():end])
    vals += re.findall(rf'\b{param}\??\.ToLowerInvariant\(\)\s*==\s*"([^"]+)"', text)
    if not vals:
        raise ParseError(f"{where}: no `switch({param}.ToLowerInvariant())` or `{param}.ToLowerInvariant() == \"x\"`")
    return list(dict.fromkeys(vals))


def classify(where, opt, param, text):
    """An option's kind for the completion: flag (with default) or value (with what goes there)."""
    names, typ = opt["names"], opt["type"].rstrip("?")
    if typ == "bool":
        if opt["default"] not in ("", "true", "false"):
            raise ParseError(f"{where}: {names[0]}: bool default {opt['default']!r}")
        return dict(names=names, kind="flag", default=opt["default"] == "true", value=None, values=[])
    if typ in NUMBER_TYPES:
        return dict(names=names, kind="value", value="text", values=[])
    if typ != "string":
        raise ParseError(f"{where}: {names[0]}: option of type {opt['type']}")
    kind = STRING_OPTIONS.get(max(names, key=len))
    if kind is None:
        raise ParseError(f"{where}: string option {names} is not in STRING_OPTIONS")
    values = words_for(f"{where} {names[0]}", text, param) if kind == "words" and param else []
    return dict(names=names, kind="value", value=kind, values=values)


def command_class(path, text):
    """{class name: dict(name, aliases, children, options, args, handler)} of a file."""
    out = {}
    for m in re.finditer(r"\bclass\s+(\w+)\s*:\s*Command\s*\{", text):
        cls = m.group(1)
        where = f"{path}: {cls}"
        start = m.end() - 1
        end = close(blank_strings(text), start)
        body = text[start:end + 1]
        ctors = list(re.finditer(rf"\b(?:public|internal)\s+{cls}\s*\(([^)]*)\)\s*:\s*base\s*\(", body))
        if len(ctors) != 1:
            raise ParseError(f"{where}: {len(ctors)} constructors")
        base_args, past = call_args(body, ctors[0].end() - 1)
        name = literal(top_split(base_args)[0])
        head = re.match(r"\s*(\{|=>)", body[past:])
        if not head:
            raise ParseError(f"{where}: odd constructor head")
        if head.group(1) == "{":
            open_b = past + head.end() - 1
            stmts = statements(body, open_b + 1, close(blank_strings(body), open_b))
        else:  # => one statement;
            semi = body.index(";", past + head.end())
            stmts = statements(body, past + head.end(), semi + 1)
        node = dict(name=name, aliases=[], children=[], options=[], args=[], handler=None, where=where)
        for st in stmts:
            if a := re.fullmatch(r'AddAlias\(\s*"([\w-]+)"\s*\)', st):
                node["aliases"].append(a.group(1))
            elif a := re.fullmatch(r"AddCommand\(\s*new\s+(\w+)\s*\([^()]*\)\s*\)", st, re.S):
                node["children"].append(a.group(1))
            elif a := re.fullmatch(r"(?:Add|AddOption)\((.*)\)", st, re.S):
                node["options"].append(new_option(where, a.group(1).strip()))
            elif a := re.fullmatch(r"AddArgument\((.*)\)", st, re.S):
                node["args"].append(new_argument(where, a.group(1).strip()))
            elif a := re.fullmatch(r"Handler\s*=\s*CommandHandler\.Create\((.*)\)", st, re.S):
                h = re.fullmatch(rf"(?:GetType\(\)|typeof\({cls}\))\.GetMethod\(nameof\((\w+)\)\)"
                                 r"|\(Func<[\w\s,<>]+>\)(\w+)", a.group(1).strip())
                if not h:
                    raise ParseError(f"{where}: odd handler {a.group(1)[:60]!r}")
                node["handler"] = params(where, body, h.group(1) or h.group(2))
            elif not re.fullmatch(r"_\w+\s*=\s*\w+", st):
                raise ParseError(f"{where}: constructor statement {st[:60]!r}")
        if node["handler"] is not None and node["children"]:
            raise ParseError(f"{where}: a handler and subcommands")
        out[cls] = node
    return out


def extract(src):
    texts = {f: no_comments(src[f]) for f in FILES if f.endswith(".cs")}
    v = re.search(r'<PackageReference\s+Include="System\.CommandLine"\s+Version="([^"]+)"', src[CSPROJ])
    if not v:
        raise ParseError(f"{CSPROJ}: no System.CommandLine version")
    if v.group(1) not in SCL:
        raise ParseError(f"System.CommandLine {v.group(1)}: look at its help and version options, its directives "
                         f"and its value syntax, then add it to SCL")
    devices = sorted(set(re.findall(r'devicePath\.StartsWith\("/dev/(\w+)"', texts[DEVICE])))
    if not devices:
        raise ParseError(f"{DEVICE}: no /dev/ prefixes")

    classes, file_ns = {}, {}
    for f in FILES:
        if not f.endswith(".cs"):
            continue
        ns = re.findall(r"^\s*namespace\s+([\w.]+)", texts[f], re.M)
        if len(ns) != 1:
            raise ParseError(f"{f}: {len(ns)} namespaces")
        file_ns[f] = ns[0]
        if f.startswith("Aaru/Commands/"):
            for cls, node in command_class(f, texts[f]).items():
                if f"{ns[0]}.{cls}" in classes:
                    raise ParseError(f"{f}: class {ns[0]}.{cls} twice")
                classes[f"{ns[0]}.{cls}"] = (f, node)

    def resolve(f, cls):
        """The class a name in file f means: C# looks in the file's namespace and
        the ones around it, innermost first, then in the namespaces it uses."""
        scope = file_ns[f].split(".")
        while scope:
            if ".".join([*scope, cls]) in classes:
                return ".".join([*scope, cls])
            scope.pop()
        hits = [f"{u}.{cls}" for u in re.findall(r"^using\s+([\w.]+)\s*;", texts[f], re.M)
                if f"{u}.{cls}" in classes]
        if len(hits) != 1:
            raise ParseError(f"{f}: command class {cls} matches {hits or 'nothing in COMMANDS'}")
        return hits[0]

    # the root: Main builds it, then runs it with the default configuration
    main = texts[MAIN]
    if "CommandLineBuilder" in main or not re.search(r"\brootCommand\.Invoke\(\s*args\s*\)", main):
        raise ParseError(f"{MAIN}: not `rootCommand.Invoke(args)` with the defaults")
    if len(re.findall(r"\bvar\s+rootCommand\s*=\s*new\s+RootCommand\(\s*\)\s*;", main)) != 1:
        raise ParseError(f"{MAIN}: no `var rootCommand = new RootCommand();`")
    unknown = set(re.findall(r"\brootCommand\.(\w+)", main)) - ROOT_CALLS
    if unknown:
        raise ParseError(f"{MAIN}: rootCommand.{sorted(unknown)}")
    globals_, top = [], []
    for m in re.finditer(r"\brootCommand\.(AddGlobalOption|AddCommand)\(", main):
        inside, _ = call_args(main, m.end() - 1)
        if m.group(1) == "AddGlobalOption":
            globals_.append(new_option(f"{MAIN}: global option", inside.strip()))
        else:
            c = re.fullmatch(r"new\s+(\w+)\s*\([^()]*\)", inside.strip())
            if not c:
                raise ParseError(f"{MAIN}: odd AddCommand({inside[:60]!r})")
            top.append(c.group(1))
    root_read = set(re.findall(r'RootCommandResult\.ValueForOption\("(--[\w-]+)"\)', main))

    nodes, unbound = {}, []

    def walk(path, qual):
        f, n = classes[qual]
        if path in nodes:
            raise ParseError(f"{f}: {' '.join(path)} twice")
        if n["options"] and n["handler"] is None:
            raise ParseError(f"{n['where']}: options on a command without a handler")
        opts = []
        for o in n["options"]:
            param = bound_param(n["where"], o["names"], n["handler"] or [])
            c = classify(n["where"], o, param, texts[f])
            c["bound"] = param is not None
            if not c["bound"]:
                unbound.append(f"{' '.join(path)} {max(o['names'], key=len)}")
            opts.append(c)
        seen = [x for o in opts for x in o["names"]]
        if len(seen) != len(set(seen)) or set(seen) & {x for g in globals_ for x in g["names"]}:
            raise ParseError(f"{n['where']}: an option name twice")
        if any(a["optional"] for a in n["args"][:-1]):
            raise ParseError(f"{n['where']}: an optional argument before the last")
        nodes[path] = dict(aliases=n["aliases"], options=opts, args=n["args"], handler=n["handler"])
        for child in n["children"]:
            q_child = resolve(f, child)
            walk((*path, classes[q_child][1]["name"]), q_child)

    for cls in top:
        q_top = resolve(MAIN, cls)
        walk((classes[q_top][1]["name"],), q_top)
    nodes[()] = dict(aliases=[], options=[], args=[], handler=None)

    # where each global option works: at a command whose handler takes it, or,
    # if no handler does and Main reads it from the root, at the root only
    leaves = [p for p, nd in nodes.items() if nd["handler"] is not None]
    glob = []
    for g in globals_:
        c = classify(MAIN, g, None, main)
        if c["kind"] != "flag":
            raise ParseError(f"{MAIN}: global option {g['names']} takes a value")
        at = {p for p in leaves if bound_param(MAIN, g["names"], nodes[p]["handler"])}
        long_name = max(g["names"], key=len)
        if at:
            if long_name in root_read:
                raise ParseError(f"{MAIN}: {long_name} is read from the root and by handlers")
            c["where"] = "all" if len(at) == len(leaves) else at
        elif long_name in root_read:
            c["where"] = "root"
        else:
            raise ParseError(f"{MAIN}: global option {long_name} reaches nothing")
        glob.append(c)
    if any(g["where"] not in ("all", "root") for g in glob):
        raise ParseError(f"{MAIN}: a global option some handlers take and others not")
    return dict(scl=v.group(1), nodes=nodes, globals=glob, unbound=unbound, devices=devices)


def render(model, cmd, origin, names):
    fn = "_mediapres_" + re.sub(r"\W", "_", cmd)
    nodes, scl = model["nodes"], SCL[model["scl"]]
    children = {}
    for p in nodes:
        if p:
            children.setdefault(p[:-1], []).append(p)
    runtime = sorted({max(o["names"], key=len) for nd in nodes.values() for o in nd["options"]
                      if o["bound"] and o["kind"] == "value" and o["value"] == "runtime"})
    tflags = sorted({max(o["names"], key=len) for nd in nodes.values() for o in nd["options"]
                     if o["bound"] and o["kind"] == "flag" and o["default"]})
    everywhere = [g for g in model["globals"] if g["where"] == "all"]
    root_only = [g for g in model["globals"] if g["where"] == "root"]
    title = f"# bash completion for {cmd}".ljust(64) + "-*- shell-script -*-"

    def long(o):
        return max(o["names"], key=len)
    paras = [
        f"aaru5 parses with System.CommandLine {model['scl']}. "
        + " and ".join(long(g) for g in everywhere) + " work before and after the command; "
        + " and ".join(long(g) for g in root_only) + " only before it (after it aaru5 parses it and "
        "does not act on it), so it is offered there only. A global option given at two levels "
        "makes System.CommandLine throw, so one that is already on the line is not offered again. "
        f"A flag that is on by default ({len(tflags)} of them) is turned off with `false`, which is "
        "offered after it.",
        "Not offered: the options aaru5 parses but does not pass to the command, so they do nothing ("
        + ", ".join(model["unbound"]) + "); the values of " + ", ".join(runtime) + " (aaru5 builds "
        "those lists at run time; see aaru5 formats, list-encodings and list-namespaces); the help "
        f"aliases {scl['unoffered_help']}, the directives {scl['directives']}, response files "
        "(@file), bundled short options (-cv) and the --option:value spelling."]
    head = [title, "# shellcheck shell=bash", "#",
            f"# GENERATED by scripts/completions/gen.py from {origin}.",
            "# Do not edit: change the generator, then run `scripts/completions/gen.py write`."]
    for para in paras:
        head += ["#"] + textwrap.wrap(para, 78, initial_indent="# ", subsequent_indent="# ",
                                      break_on_hyphens=False)

    def path_s(p):
        return " ".join(p)

    child_cases = []
    for parent, kids in children.items():
        for k in kids:
            pats = [f"{q(path_s(parent))}/{w}" if parent else f"/{w}" for w in [k[-1], *nodes[k]["aliases"]]]
            child_cases.append(f"        {'|'.join(pats)}) REPLY={q(path_s(k))} ;;")
    node_cases, value_cases = [], []
    file_pats, dir_pats, words_cases = [], [], []
    gnames = [n for g in everywhere for n in g["names"]]
    for p, nd in nodes.items():
        subs = [w for k in children.get(p, []) for w in [k[-1], *nodes[k]["aliases"]]]
        own = [n for o in nd["options"] if o["bound"] for n in o["names"]]
        opts = own + gnames + scl["help"]
        if p == ():
            opts += [n for g in root_only for n in g["names"]] + [scl["version"]]
        vopts = [n for o in nd["options"] if o["kind"] == "value" for n in o["names"]]
        tf = [n for o in nd["options"] if o["bound"] and o["kind"] == "flag" and o["default"] for n in o["names"]]
        lines = [f"    {q(path_s(p))})"]
        if subs:
            lines.append(f"        subs={q(wrap(subs, '              '))}")
        lines.append(f"        opts={q(wrap(opts, '              '))}")
        if vopts:
            lines.append(f"        vopts={q(wrap(vopts, '               '))}")
        if tf:
            lines.append(f"        tflags={q(wrap(tf, '                '))}")
        if nd["args"]:
            lines.append(f"        args='{' '.join(a['kind'] for a in nd['args'])}'")
        node_cases.append("\n".join(lines) + "\n        ;;")
        for o in nd["options"]:
            if o["kind"] != "value" or not o["bound"]:
                continue
            pats = [f"{path_s(p)}/{n}" for n in o["names"]]
            if o["value"] == "file":
                file_pats += pats
            elif o["value"] == "dir":
                dir_pats += pats
            elif o["value"] == "words":
                words_cases.append((pats, o["values"]))
    if file_pats:
        value_cases.append(f"        {'|'.join(q(x) for x in file_pats)})\n            _filedir\n            ;;")
    if dir_pats:
        value_cases.append(f"        {'|'.join(q(x) for x in dir_pats)})\n            _filedir -d\n            ;;")
    for pats, vals in words_cases:
        value_cases.append(f"        {'|'.join(q(x) for x in pats)})\n"
                           f"            mapfile -t COMPREPLY < <(compgen -W {q(' '.join(vals))} -- \"${{cur,,}}\")\n"
                           "            ;;")
    global_cases = [f"        {'|'.join(g['names'])}) REPLY={q(' '.join(g['names']))} ;;" for g in model["globals"]]
    devs = " ".join(f"/dev/{p}*" for p in model["devices"])

    out = "\n".join(head) + "\n\n"
    out += (f"# {fn}_child <node> <word>: the subcommand the word names, in REPLY\n"
            f"{fn}_child()\n{{\n    case $1/$2 in\n" + "\n".join(child_cases)
            + "\n        *) REPLY= ;;\n    esac\n}\n\n")
    out += (f"# {fn}_node <node>: what it takes (subcommands, the options offered, the\n"
            "# options that take a value, the flags that are on by default, the kinds of\n"
            "# its arguments)\n"
            f"{fn}_node()\n{{\n    subs='' opts='' vopts='' tflags='' args=''\n    case $1 in\n"
            + "\n".join(node_cases) + "\n    esac\n}\n\n")
    out += (f"# {fn}_value <node> <option>: complete the option's value; numbers, free\n"
            "# text and the lists aaru5 only knows at run time get nothing\n"
            f"{fn}_value()\n{{\n    case $1/$2 in\n" + "\n".join(value_cases)
            + "\n    esac\n}\n\n")
    out += (f"# {fn}_global <option>: all names of the global option, in REPLY\n"
            f"{fn}_global()\n{{\n    case $1 in\n" + "\n".join(global_cases)
            + "\n        *) return 1 ;;\n    esac\n}\n\n")
    out += (f"{fn}_devices()\n{{\n    local d\n    COMPREPLY=()\n"
            f"    for d in {devs}; do\n"
            "        [[ -e $d && $d == \"$cur\"* ]] && COMPREPLY+=(\"$d\")\n    done\n"
            "    ((${#COMPREPLY[@]})) || _filedir\n}\n\n")
    out += f"""{fn}()
{{
    local cur prev words cword split
    _init_completion -s -n : || return

    local node='' skip='' last='' used=' ' w lw c i j dirs=0 REPLY subs opts vopts tflags args
    local -a pos=() kinds=() offer=()
    for ((i = 1; i < cword; i++)); do
        w=${{words[i]}}
        if [[ $skip == value ]]; then
            skip=''
            continue
        fi
        lw=${{w,,}}
        if [[ $skip == flag ]]; then
            skip=''
            [[ $lw == true || $lw == false ]] && continue
        fi
        # directives ([parse] ...) come first
        if ((i == dirs + 1)) && [[ $w == \\[*\\] ]]; then
            dirs=$i
            continue
        fi
        case $w in
            --)
                # aaru5 ignores what follows
                return
                ;;
            @?*)
                # a response file: what it holds is unknown
                return
                ;;
            --*)
                {fn}_global "${{w%%[=:]*}}" && used+="$REPLY "
                [[ $w == *[=:]* ]] && continue
                {fn}_node "$node"
                last=$w
                if [[ " $vopts " == *[[:space:]]"$w"[[:space:]]* ]]; then skip=value; else skip=flag; fi
                ;;
            -?*)
                # short options, maybe bundled: the first that takes a value
                # takes the rest of the word, or the next word
                {fn}_node "$node"
                skip=flag
                for ((j = 1; j < ${{#w}}; j++)); do
                    c=-${{w:j:1}}
                    last=$c
                    {fn}_global "$c" && used+="$REPLY "
                    if [[ " $vopts " == *[[:space:]]"$c"[[:space:]]* ]]; then
                        if ((j == ${{#w}} - 1)); then skip=value; else skip=''; fi
                        break
                    fi
                done
                ;;
            *)
                {fn}_node "$node"
                if [[ $subs ]]; then
                    {fn}_child "$node" "$w"
                    [[ $REPLY ]] || return
                    node=$REPLY
                else
                    pos+=("$w")
                fi
                ;;
        esac
    done

    {fn}_node "$node"
    if [[ $skip == value ]]; then
        {fn}_value "$node" "$last"
        return
    fi
    if $split; then
        if [[ " $vopts " == *[[:space:]]"$prev"[[:space:]]* ]]; then
            {fn}_value "$node" "$prev"
        else
            mapfile -t COMPREPLY < <(compgen -W 'false true' -- "${{cur,,}}")
        fi
        return
    fi
    if [[ $skip == flag && " $tflags " == *[[:space:]]"$last"[[:space:]]* && $cur != -* ]] &&
        [[ false == "${{cur,,}}"* || true == "${{cur,,}}"* ]]; then
        mapfile -t COMPREPLY < <(compgen -W 'false true' -- "${{cur,,}}")
        return
    fi
    if [[ $cur == -* ]]; then
        read -rd '' -a kinds <<<"$opts"
        for w in "${{kinds[@]}}"; do
            [[ $used == *[[:space:]]"$w"[[:space:]]* ]] || offer+=("$w")
        done
        mapfile -t COMPREPLY < <(compgen -W "${{offer[*]}}" -- "$cur")
        return
    fi
    if [[ $subs ]]; then
        mapfile -t COMPREPLY < <(compgen -W "$subs" -- "$cur")
        return
    fi
    read -ra kinds <<<"$args"
    case ${{kinds[${{#pos[@]}}]-}} in
        file) _filedir ;;
        dir) _filedir -d ;;
        device) {fn}_devices ;;
        host) _known_hosts_real -- "$cur" ;;
    esac
}} &&
    complete -F {fn} {' '.join(names)}

# ex: filetype=sh
"""
    return out
