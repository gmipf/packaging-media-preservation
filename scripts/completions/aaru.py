"""aaru (6.x, Spectre.Console.Cli): the command tree from Aaru/Main.cs, the
options and arguments from the settings classes under Aaru/Commands.

Spectre gives each option to the command whose settings class declares it.
The branches (image, media, ...) use the family classes, which only inherit
BaseSettings, so -v/-d/--logfile/--pause belong to the BRANCH: they work
between the branch and its subcommand (`aaru image -d convert`) and are
silently dropped after it. A top-level command (formats) has no branch and
owns them itself. Flags take an optional true/false; for the ones that
default to true only `--x false` turns them off, so that is offered.

What the source cannot say is a table here, and anything new stops the
generator: a string option or an argument nobody classified, an attribute
this file does not know, a Spectre.Console.Cli version whose built-in `cli`
branch nobody looked at. Values aaru only knows at run time (image formats,
encodings, filesystem namespaces, -O keys) are not offered; its own listing
commands print them.
"""
import re
import textwrap

import clex


class ParseError(Exception):
    pass


COMMANDS = ["Archive/ArchiveFamily.cs", "Archive/Extract.cs", "Archive/Info.cs", "Archive/List.cs",
            "BaseSettings.cs", "Configure.cs", "Database/DatabaseFamily.cs", "Database/Statistics.cs",
            "Database/Update.cs", "Device/DeviceFamily.cs", "Device/DeviceReport.cs", "Device/Info.cs",
            "Device/List.cs", "Filesystem/ExtractFiles.cs", "Filesystem/FilesystemFamily.cs",
            "Filesystem/Info.cs", "Filesystem/Ls.cs", "Filesystem/Options.cs", "Formats.cs",
            "Image/Analyze.cs", "Image/Checksum.cs", "Image/Compare.cs", "Image/Convert.cs",
            "Image/CreateSidecar.cs", "Image/Decode.cs", "Image/Entropy.cs", "Image/ImageFamily.cs",
            "Image/Info.cs", "Image/Merge.cs", "Image/Options.cs", "Image/Print.cs", "Image/Verify.cs",
            "Image/WriteMetadata.cs", "ListEncodings.cs", "ListNamespaces.cs", "Media/Dpm.cs",
            "Media/Dump.cs", "Media/Info.cs", "Media/MediaFamily.cs", "Media/Scan.cs",
            "MetadataSchema.cs", "Remote.cs"]
MAIN = "Aaru/Main.cs"
PACKAGES = "Directory.Packages.props"
UI_RESX = "Aaru.Localization/UI.resx"
LINUX_DEVICE = "Aaru.Devices/Linux/Device.cs"
FILES = [MAIN, PACKAGES, UI_RESX, LINUX_DEVICE] + [f"Aaru/Commands/{f}" for f in COMMANDS]

SMOKE = [
    ("{cmd} ", {"archive", "image", "media", "fmt", "cli", "gui"}, {"-v", "convert"}),
    ("{cmd} -", {"-h", "--help", "-v", "--version"}, {"--verbose"}),
    ("{cmd} image ", {"convert", "cvt", "verify", "write-metadata", "options"}, {"archive", "gui"}),
    ("{cmd} img -", {"-v", "--debug", "--logfile", "--pause"}, {"--format"}),
    ("{cmd} image convert -", {"--format", "-O", "--fix-subchannel-position"}, {"--debug", "--logfile"}),
    ("{cmd} i -d --logfile x.log cvt --", {"--format", "--geometry"}, {"--pause"}),
    # aaru also takes --opt:value; readline splits the word at the colon
    ("{cmd} i --logfile:x.log cvt --", {"--format", "--geometry"}, {"--pause"}),
    ("{cmd} media dump --subchannel ", {"any", "rw", "rw-or-pq", "pq", "none"}, set()),
    ("{cmd} m d --subchannel=r", {"rw", "rw-or-pq"}, {"any"}),
    ("{cmd} media dump --trim ", {"false", "true"}, set()),
    ("{cmd} media dump --force ", set(), {"false", "true"}),
    ("{cmd} image decode -l ", {"all"}, set()),
    ("{cmd} image convert -c ", set(), "*"),
    ("{cmd} image convert --format ", set(), "*"),
    ("{cmd} formats --", {"--verbose", "--logfile", "--pause"}, set()),
    ("{cmd} gui ", set(), "*"),
    ("{cmd} -d image ", set(), "*"),
    ("{cmd} cli ", {"version", "xmldoc", "explain", "opencli"}, set()),
    ("{cmd} cli explain ", {"image", "media", "cli"}, set()),
    ("{cmd} cli explain image ", {"convert", "verify"}, {"image"}),
]

# Spectre.Console.Cli adds a hidden `cli` branch of its own (no code in the aaru
# tree). Read from 0.55.0's source and the binary (`aaru cli explain --hidden`);
# a new version must be looked at before it is trusted.
SPECTRE = {
    "0.55.0": {
        ("cli",): dict(aliases=[], options=[], args=[]),
        ("cli", "version"): dict(aliases=[], options=[], args=[]),
        ("cli", "xmldoc"): dict(aliases=[], options=[], args=[]),
        ("cli", "explain"): dict(aliases=[], args=[("commands", "commands")], options=[
            dict(names=["-d", "--detailed"], kind="flag", default=False, value=None),
            dict(names=["--hidden"], kind="flag", default=False, value=None)]),
        ("cli", "opencli"): dict(aliases=[], options=[], args=[]),
    },
}
# What a string option's value is, by its long name: file, dir, text (free
# text or a number), words (the UI.resx strings the command compares it with),
# or runtime (a list aaru builds from its plugins; not offered).
STRING_OPTIONS = {
    "--logfile": "file", "--cicm-xml": "file", "--resume-file": "file", "--aaru-metadata": "file",
    "--ibg-log": "file", "--mhdd-log": "file", "--primary-resume": "file", "--secondary-resume": "file",
    "--sectors-file": "file", "--output-prefix": "file",
    "--comments": "text", "--creator": "text", "--drive-manufacturer": "text", "--drive-model": "text",
    "--drive-revision": "text", "--drive-serial": "text", "--media-barcode": "text",
    "--media-manufacturer": "text", "--media-model": "text", "--media-partnumber": "text",
    "--media-serial": "text", "--media-title": "text", "--options": "text", "--geometry": "text",
    "--format": "runtime", "--encoding": "runtime", "--namespace": "runtime",
    "--subchannel": "words", "--length": "words",
}
# Spectre argument names: what goes there (by property where a name means two things).
ARGUMENTS = {
    "image-path": "file", "image-path1": "file", "input-image": "file", "output-image": "file",
    "output-path": "file", "output-dir": "dir", "device-path": "device", "path": "file",
    "primary-image": "file", "secondary-image": "file", "host": "host", "aaru-remote-host": "host",
    "output": {"OutputDir": "dir", "Output": "file"},
}
NUMBER_TYPES = {"int", "uint", "long", "ulong", "short", "ushort", "byte", "sbyte", "double", "float"}
KNOWN_ATTRIBUTES = {"CommandOption", "CommandArgument", "LocalizedDescription", "Description", "DefaultValue",
                    "CanBeNull", "NotNull"}
# Main.cs configuration calls that do not change what the command line takes
INERT_CONFIG = {"PropagateExceptions", "SetInterceptor", "SetDescription", "WithDescription"}


def scan(text, keep_strings):
    """C# text with comments blanked, and the inside of string and character
    literals kept (to read attribute arguments) or blanked (to count braces).
    Knows @"..." (with ""), $"..." (with {holes} that hold strings again) and
    '\\uXXXX'. Offsets never move."""
    out, i, n = list(text), 0, len(text)

    def lit(i):
        """i at a literal's first character; the index just past it."""
        pre = re.match(r'[@$]*"', text[i:]).group(0)
        verbatim, interp = "@" in pre, "$" in pre
        j = i + len(pre)
        while j < n:
            if verbatim and text.startswith('""', j):
                j += 2
            elif not verbatim and text[j] == "\\":
                j += 2
            elif interp and text.startswith("{{", j):
                j += 2
            elif interp and text[j] == "{":
                depth, j = 1, j + 1
                while j < n and depth:
                    if text[j] == '"' or (text[j] in "@$" and re.match(r'[@$]{1,2}"', text[j:j + 3])):
                        j = lit(j)
                        continue
                    depth += {"{": 1, "}": -1}.get(text[j], 0)
                    j += 1
            elif text[j] == '"':
                return j + 1
            else:
                j += 1
        raise ParseError("unterminated string")

    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise ParseError("unterminated comment")
            out[i:j + 2] = [c if c == "\n" else " " for c in text[i:j + 2]]
            i = j + 2
        elif text[i] == '"' or (text[i] in "@$" and re.match(r'[@$]{1,2}"', text[i:i + 3])):
            j = lit(i)
            if not keep_strings:
                k = text.index('"', i)
                out[k + 1:j - 1] = [c if c == "\n" else " " for c in text[k + 1:j - 1]]
            i = j
        elif text[i] == "'" and not re.match(r"\w", text[i - 1:i] or " "):
            m = re.match(r"'(\\u[0-9A-Fa-f]{4}|\\x[0-9A-Fa-f]{1,4}|\\.|[^'\\])'", text[i:])
            if not m:
                raise ParseError(f"odd character literal at {text[i:i + 12]!r}")
            if not keep_strings:
                out[i + 1:i + len(m.group(0)) - 1] = " " * (len(m.group(0)) - 2)
            i += len(m.group(0))
        else:
            i += 1
    return "".join(out)


def no_comments(text):
    return scan(text, True)


def blank_strings(text):
    """Comment-free text with string contents blanked: braces can be counted."""
    return scan(text, False)


def close(bl, start, open_ch="{", close_ch="}"):
    """The index of the bracket that closes the one at bl[start]."""
    try:
        return clex.match(bl, start, open_ch, close_ch) - 1
    except clex.CError as e:
        raise ParseError(str(e)) from None


def body(text, open_pos):
    """(start, end) of the {...} block that opens at or after open_pos."""
    bl = blank_strings(text)
    start = bl.index("{", open_pos)
    return start, close(bl, start)


ATTR_RE = re.compile(r'\[\s*((?:[^\]"]|"(?:[^"\\]|\\.)*")*)\]')
MEMBER_RE = re.compile(r'((?:\[\s*(?:[^\]"]|"(?:[^"\\]|\\.)*")*\]\s*)+)'
                       r'public\s+([\w.<>?\[\], ]+?)\s+(\w+)\s*(?:\{|=>|;|=)')


def settings_classes(path, text):
    """{qualified class name: (base, [members])} for the settings classes of a file."""
    ns = re.search(r"^namespace\s+([\w.]+)\s*;", text, re.M)
    if not ns:
        raise ParseError(f"{path}: no file-scoped namespace")
    out = {}
    for m in re.finditer(r"\bclass\s+(\w+)\s*:\s*([\w.]+)\s*(\{\s*\}|\{)", text):
        name, base = m.group(1), m.group(2)
        if base.endswith("Command") or "<" in text[m.end(2):m.end(2) + 1]:
            continue
        outer = re.findall(r"\bclass\s+(\w+)\s*:\s*\w*Command<", text[:m.start()])
        qual = f"{ns.group(1)}.{outer[-1] + '.' if outer and name == 'Settings' else ''}{name}"
        if m.group(3).startswith("{") and m.group(3).strip() == "{}":
            out[qual] = (base, [])
            continue
        start, end = body(text, m.start(3))
        members = []
        for mm in MEMBER_RE.finditer(text[start + 1:end]):
            attrs = {}
            for a in ATTR_RE.finditer(mm.group(1)):
                for part in split_attrs(a.group(1)):
                    an = re.match(r"(\w+)", part).group(1)
                    if an not in KNOWN_ATTRIBUTES:
                        raise ParseError(f"{path}: {name}.{mm.group(3)} has attribute [{an}]")
                    attrs[an] = re.sub(r"^\w+\s*", "", part).strip()
            if "CommandOption" in attrs or "CommandArgument" in attrs:
                members.append((mm.group(3), mm.group(2).replace(" ", ""), attrs))
        out[qual] = (base, members)
    return out


def split_attrs(s):
    """`A(x), B("y,z")` -> ['A(x)', 'B("y,z")']"""
    parts, depth, cur, q = [], 0, "", False
    for ch in s:
        if ch == '"':
            q = not q
        if not q:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                parts.append(cur.strip())
                cur = ""
                continue
        cur += ch
    return [p for p in (*parts, cur.strip()) if p]


def literal(s):
    m = re.fullmatch(r'"((?:[^"\\]|\\.)*)"', s.strip())
    if not m:
        raise ParseError(f"not a plain string literal: {s!r}")
    return m.group(1)


def attr_args(path, where, raw):
    """`("a", IsHidden = true)` -> (['"a"'], {'IsHidden': 'true'})"""
    m = re.fullmatch(r"\((.*)\)", raw.strip(), re.S)
    if not m:
        raise ParseError(f"{path}: {where}: odd attribute arguments {raw!r}")
    pos, named = [], {}
    for p in split_attrs(m.group(1)):
        nm = re.fullmatch(r"(\w+)\s*=\s*(.+)", p, re.S)
        if nm and not p.lstrip().startswith('"'):
            named[nm.group(1)] = nm.group(2).strip()
        else:
            pos.append(p)
    return pos, named


def resx(text):
    return {m.group(1): m.group(2) for m in
            re.finditer(r'<data name="(\w+)"[^>]*>\s*<value>([^<]*)</value>', text)}


def option(path, cls, prop, typ, attrs, cmdtext, ui):
    where = f"{cls}.{prop}"
    pos, named = attr_args(path, where, attrs["CommandOption"])
    if len(pos) != 1:
        raise ParseError(f"{path}: {where}: CommandOption({attrs['CommandOption']})")
    hidden = named.pop("IsHidden", "false") == "true"
    if named:
        raise ParseError(f"{path}: {where}: CommandOption takes {sorted(named)}")
    template = literal(pos[0]).split()
    names = template[0].split("|")
    if not all(re.fullmatch(r"-[A-Za-z?]|--[a-z0-9][a-z0-9-]*", n) for n in names) or len(template) > 2:
        raise ParseError(f"{path}: {where}: odd option template {literal(pos[0])!r}")
    longs = [n for n in names if n.startswith("--")]
    default = attrs.get("DefaultValue", "").strip("() ")
    base = typ.rstrip("?")
    if base == "bool":
        if len(template) > 1:
            raise ParseError(f"{path}: {where}: a bool option with a value template")
        return dict(names=names, kind="flag", default=default == "true", value=None, hidden=hidden)
    if base in NUMBER_TYPES:
        return dict(names=names, kind="value", value="text", values=[], hidden=hidden)
    if base != "string":
        raise ParseError(f"{path}: {where}: option of type {typ}")
    kind = STRING_OPTIONS.get(longs[0] if longs else names[0])
    if kind is None:
        raise ParseError(f"{path}: {where}: string option {names} is not in STRING_OPTIONS")
    values = []
    if kind == "words":
        keys = re.findall(rf"settings\.{prop}\b[^;=]*?==\s*UI\.(\w+)", cmdtext)
        if not keys:
            raise ParseError(f"{path}: {where}: no `settings.{prop} == UI.<key>` comparison found")
        for k in keys:
            if k not in ui:
                raise ParseError(f"{path}: UI.{k} is not in {UI_RESX}")
            values.append(ui[k])
    return dict(names=names, kind="value", value=kind, values=values, hidden=hidden)


def argument(path, cls, prop, attrs):
    pos, named = attr_args(path, f"{cls}.{prop}", attrs["CommandArgument"])
    if named or len(pos) != 2 or not pos[0].strip().isdigit():
        raise ParseError(f"{path}: {cls}.{prop}: CommandArgument({attrs['CommandArgument']})")
    m = re.fullmatch(r"([<\[])([\w-]+)([>\]])", literal(pos[1]))
    if not m:
        raise ParseError(f"{path}: {cls}.{prop}: odd argument {literal(pos[1])!r}")
    kind = ARGUMENTS.get(m.group(2))
    if isinstance(kind, dict):
        kind = kind.get(prop)
    if kind is None:
        raise ParseError(f"{path}: {cls}.{prop}: argument <{m.group(2)}> is not in ARGUMENTS")
    return int(pos[0]), (m.group(2), kind)


def registrations(path, text):
    """[(path tuple, class name, aliases)] from app.Configure(...), in order,
    plus whether the root takes --version."""
    m = re.search(r"\.Configure\(\s*static\s+(\w+)\s*=>", text)
    if not m:
        raise ParseError(f"{path}: no app.Configure(static config => ...)")
    start, end = body(text, m.end())
    block = text[start + 1:end]
    out, root_version = [], False
    stmt_re = re.compile(r"(\w+)\.(\w+)(?:<([\w.]+)>)?\(")
    pos = 0
    bl = blank_strings(block)
    while True:
        s = stmt_re.search(bl, pos)
        if not s:
            break
        call = s.group(2)
        argend = close(bl, s.end() - 1, "(", ")")
        tail = re.match(r"(?:\s*\.\w+\([^;]*?\))*\s*;", bl[argend + 1:], re.S)
        if not tail:
            raise ParseError(f"{path}: config.{call}(...) is not a statement")
        chain = block[argend + 1:argend + 1 + tail.end()]
        if call == "UseAssemblyInformationalVersion" or call == "SetApplicationVersion":
            root_version = True
        elif call in ("AddBranch", "AddCommand"):
            args = block[s.end():argend]
            nm = re.match(r'\s*"([\w-]+)"', args)
            if not nm:
                raise ParseError(f"{path}: {call}<{s.group(3)}>: no literal name")
            aliases = re.findall(r'\.WithAlias\("([\w-]+)"\)', chain)
            other = set(re.findall(r"\.(\w+)\(", chain)) - {"WithAlias", "WithDescription"}
            if other:
                raise ParseError(f"{path}: {nm.group(1)}: unknown {sorted(other)}")
            out.append(((nm.group(1),), s.group(3), aliases, call))
            if call == "AddBranch":
                lam = re.search(r"static\s+(\w+)\s*=>", args)
                if not lam:
                    raise ParseError(f"{path}: branch {nm.group(1)}: no static lambda")
                bs, be = body(args, lam.end())
                for sub in re.finditer(rf"\b{lam.group(1)}\.(\w+)(?:<([\w.]+)>)?\(", args[bs:be]):
                    if sub.group(1) == "AddCommand":
                        a0 = bs + sub.end()
                        ae = close(blank_strings(args), a0 - 1, "(", ")")
                        snm = re.match(r'\s*"([\w-]+)"\s*$', args[a0:ae])
                        stail = re.match(r"(?:\s*\.\w+\([^;]*?\))*\s*;", args[ae + 1:], re.S)
                        if not snm or not stail:
                            raise ParseError(f"{path}: {nm.group(1)}: odd AddCommand")
                        schain = args[ae + 1:ae + 1 + stail.end()]
                        sother = set(re.findall(r"\.(\w+)\(", schain)) - {"WithAlias", "WithDescription"}
                        if sother:
                            raise ParseError(f"{path}: {nm.group(1)} {snm.group(1)}: unknown {sorted(sother)}")
                        out.append(((nm.group(1), snm.group(1)), sub.group(2),
                                    re.findall(r'\.WithAlias\("([\w-]+)"\)', schain), "AddCommand"))
                    elif sub.group(1) not in INERT_CONFIG and sub.group(1) not in ("WithAlias",):
                        raise ParseError(f"{path}: branch {nm.group(1)}: unknown call {sub.group(1)}")
        elif call not in INERT_CONFIG:
            raise ParseError(f"{path}: unknown configuration call config.{call}")
        pos = argend + 1 + tail.end()
    return out, root_version


def resolve(name, classes, aliases):
    """A class name as Main.cs writes it -> its qualified name."""
    name = aliases.get(name, name)
    hits = [q for q in classes if q == name or q.endswith("." + name)]
    if len(hits) != 1:
        raise ParseError(f"{MAIN}: class {name} matches {hits or 'nothing'}")
    return hits[0]


def extract(src):
    texts = {f: no_comments(src[f]) for f in FILES if f.endswith(".cs")}
    ui = resx(src[UI_RESX])
    if not ui:
        raise ParseError(f"{UI_RESX}: no strings")
    sp = re.search(r'<PackageVersion\s+Include="Spectre\.Console\.Cli"\s+Version="([^"]+)"', src[PACKAGES])
    if not sp:
        raise ParseError(f"{PACKAGES}: no Spectre.Console.Cli version")
    if sp.group(1) not in SPECTRE:
        raise ParseError(f"Spectre.Console.Cli {sp.group(1)}: look at its built-in `cli` branch, its help and "
                         f"version options and its value syntax, then add it to SPECTRE")
    prefixes = sorted(set(re.findall(r'devicePath\.StartsWith\("/dev/(\w+)"', texts[LINUX_DEVICE])))
    if not prefixes:
        raise ParseError(f"{LINUX_DEVICE}: no /dev/ prefixes")

    # every command class and settings class of the tree
    commands, settings = {}, {}
    for f in FILES:
        if not f.startswith("Aaru/Commands/"):
            continue
        t = texts[f]
        ns = re.search(r"^namespace\s+([\w.]+)\s*;", t, re.M).group(1)
        for m in re.finditer(r"\bclass\s+(\w+)\s*:\s*(\w*Command)<([\w.]+)>", t):
            if m.group(2) not in ("Command", "AsyncCommand"):
                raise ParseError(f"{f}: {m.group(1)} derives from {m.group(2)}")
            commands[f"{ns}.{m.group(1)}"] = (f, f"{ns}.{m.group(3)}")
        settings.update({k: (f, *v) for k, v in settings_classes(f, t).items()})
    using_alias = dict(re.findall(r"^using\s+(\w+)\s*=\s*([\w.]+)\s*;", texts[MAIN], re.M))

    def chain(qual):
        """[(file, class, members)] from the class up to CommandSettings."""
        out = []
        while qual:
            if qual not in settings:
                raise ParseError(f"settings class {qual} not found")
            f, base, members = settings[qual]
            out.append((f, qual, members))
            if base == "CommandSettings":
                return out
            # C# looks in the enclosing class and namespaces, innermost first
            scope = qual.split(".")[:-1]
            while ".".join([*scope, base]) not in settings:
                if not scope:
                    raise ParseError(f"{f}: base class {base} of {qual} not found")
                scope.pop()
            qual = ".".join([*scope, base])
        return out

    regs, root_version = registrations(MAIN, texts[MAIN])
    nodes = {(): dict(aliases=[], options=[], args=[], hidden=False)}
    family = {}
    for path, cls, aliases, call in regs:
        if path in nodes:
            raise ParseError(f"{MAIN}: {' '.join(path)} registered twice")
        if len(path) == 2 and path[:1] not in family:
            raise ParseError(f"{MAIN}: {path[1]} under unknown branch {path[0]}")
        if call == "AddBranch":
            qual = resolve(cls, settings, using_alias)
            family[path] = {id(m) for _f, _q, ms in chain(qual) for m in ms}
            members = [(f, q, m) for f, q, ms in chain(qual) for m in ms]
        else:
            f, sq = commands[resolve(cls, commands, using_alias)]
            inherited = family.get(path[:1], set())
            members = [(ff, q, m) for ff, q, ms in chain(sq) for m in ms if id(m) not in inherited]
        opts, args = [], {}
        for ff, q, (prop, typ, attrs) in members:
            if "CommandOption" in attrs:
                opts.append(option(ff, q, prop, typ, attrs, texts[ff], ui))
            else:
                n, a = argument(ff, q, prop, attrs)
                if n in args:
                    raise ParseError(f"{ff}: two arguments at position {n}")
                args[n] = a
        if sorted(args) != list(range(len(args))):
            raise ParseError(f"{MAIN}: {' '.join(path)}: argument positions {sorted(args)}")
        seen = [n for o in opts for n in o["names"]]
        if len(seen) != len(set(seen)):
            raise ParseError(f"{MAIN}: {' '.join(path)}: an option name twice")
        nodes[path] = dict(aliases=aliases, options=opts, args=[args[n] for n in sorted(args)],
                           hidden=False, branch=call == "AddBranch")
    for path, n in SPECTRE[sp.group(1)].items():
        nodes[path] = dict(n, hidden=True, branch=len(path) == 1)

    # `aaru gui` is read by Main before Spectre, and only as the sole argument
    gui = re.search(r'args\.Length\s*==\s*1\s*&&\s*args\[0\]\.Equals\("gui"', texts[MAIN]) is not None
    if not gui and '"gui"' in texts[MAIN]:
        raise ParseError(f"{MAIN}: \"gui\" is handled in a way this generator does not know")
    return dict(spectre=sp.group(1), root_version=root_version, nodes=nodes, gui=gui, devices=prefixes)


def wrap(words, indent, width=100):
    lines, cur = [], ""
    for w in words:
        if cur and len(indent) + len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    lines.append(cur)
    return ("\n" + indent).join(lines)


def q(s):
    return "''" if s == "" else s if re.fullmatch(r"[\w/-]+", s) else "'" + s.replace("'", "'\\''") + "'"


def render(model, cmd, origin, names):
    fn = "_mediapres_" + re.sub(r"\W", "_", cmd)
    nodes = model["nodes"]
    children = {}
    for p in nodes:
        if p:
            children.setdefault(p[:-1], []).append(p)
    hidden_opts = [n for p, nd in nodes.items() for o in nd["options"] if o.get("hidden") for n in o["names"]]
    runtime = sorted({f"{o['names'][-1]}" for nd in nodes.values() for o in nd["options"]
                      if o["kind"] == "value" and o["value"] == "runtime"})
    tflags = sorted({o["names"][-1] for nd in nodes.values() for o in nd["options"]
                     if o["kind"] == "flag" and o["default"]})
    title = f"# bash completion for {cmd}".ljust(64) + "-*- shell-script -*-"
    hidden = [" ".join(p) for p, nd in nodes.items() if nd["hidden"] and len(p) > 1]
    paras = [
        f"aaru parses with Spectre.Console.Cli {model['spectre']}. Offered although the help "
        "text does not show them: `gui` (only as the sole argument) and the `cli` branch ("
        + ", ".join(p.split()[-1] for p in hidden) + ")"
        + (f", and the options {' '.join(hidden_opts)}." if hidden_opts else "."),
        ("-v, -d, --logfile and --pause of a branch go between the branch and its subcommand "
         "(`aaru image -d convert ...`); after the subcommand aaru drops them. A flag that is on "
         f"by default ({len(tflags)} of them) is turned off with `false`, which is offered after it."),
        "Not offered: the values of " + ", ".join(runtime) + " (aaru builds those lists at run "
        "time; see aaru formats, list-encodings and list-namespaces), the help alias -?, the "
        "root's -V and --VERSION, and the --option:value spelling."]
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
            if True:
                pats = [f"{q(path_s(parent))}/{w}" if parent else f"/{w}" for w in [k[-1], *nodes[k]["aliases"]]]
                child_cases.append(f"        {'|'.join(pats)}) REPLY={q(path_s(k))} ;;")
    node_cases, value_cases = [], []
    file_pats, dir_pats, words_cases = [], [], []
    for p, nd in nodes.items():
        subs = [w for k in children.get(p, []) for w in [k[-1], *nodes[k]["aliases"]]]
        if p == ():
            opts = ["-h", "--help"] + (["-v", "--version"] if model["root_version"] else [])
        else:
            opts = [n for o in nd["options"] for n in o["names"]] + ["-h", "--help"]
        vopts = [n for o in nd["options"] if o["kind"] == "value" for n in o["names"]]
        tf = [n for o in nd["options"] if o["kind"] == "flag" and o["default"] for n in o["names"]]
        lines = [f"    {q(path_s(p))})"]
        if subs:
            lines.append(f"        subs={q(wrap(subs, '              '))}")
        lines.append(f"        opts={q(wrap(opts, '              '))}")
        if vopts:
            lines.append(f"        vopts={q(wrap(vopts, '               '))}")
        if tf:
            lines.append(f"        tflags={q(wrap(tf, '                '))}")
        if nd["args"]:
            lines.append(f"        args='{' '.join(k for _n, k in nd['args'])}'")
        node_cases.append("\n".join(lines) + "\n        ;;")
        for o in nd["options"]:
            if o["kind"] != "value":
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
                           f"            mapfile -t COMPREPLY < <(compgen -W {q(' '.join(vals))} -- \"$cur\")\n"
                           "            ;;")
    devs = " ".join(f"/dev/{p}*" for p in model["devices"])

    out = "\n".join(head) + "\n\n"
    out += (f"# {fn}_child <node> <word>: the subcommand the word names, in REPLY\n"
            f"{fn}_child()\n{{\n    case $1/$2 in\n" + "\n".join(child_cases)
            + "\n        *) REPLY= ;;\n    esac\n}\n\n")
    out += (f"# {fn}_node <node>: what it takes (subcommands, options, the options with a\n"
            "# value, the flags that are on by default, the kinds of its arguments)\n"
            f"{fn}_node()\n{{\n    subs='' opts='' vopts='' tflags='' args=''\n    case $1 in\n"
            + "\n".join(node_cases) + "\n    esac\n}\n\n")
    out += (f"# {fn}_value <node> <option>: complete the option's value; numbers, free\n"
            "# text and the lists aaru only knows at run time get nothing\n"
            f"{fn}_value()\n{{\n    case $1/$2 in\n" + "\n".join(value_cases)
            + "\n    esac\n}\n\n")
    out += (f"{fn}_devices()\n{{\n    local d\n    COMPREPLY=()\n"
            f"    for d in {devs}; do\n"
            "        [[ -e $d && $d == \"$cur\"* ]] && COMPREPLY+=(\"$d\")\n    done\n"
            "    ((${#COMPREPLY[@]})) || _filedir\n}\n\n")
    out += f"""{fn}()
{{
    local cur prev words cword split
    _init_completion -s -n : || return

    local node='' skip='' w lw i REPLY subs opts vopts tflags args
    local -a pos=() kinds=()
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
        case $w in
            --)
                return
                ;;
            -*)
                # before the first command: help, version or an error
                [[ -z $node ]] && return
                [[ $w == *=* ]] && continue
                {fn}_node "$node"
                if [[ " $vopts " == *[[:space:]]"$w"[[:space:]]* ]]; then skip=value; else skip=flag; fi
                ;;
            *)
                {"[[ -z $node && $lw == gui ]] && return" if model["gui"] else ":"}
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
    if [[ $skip == value ]] || {{ $split && [[ " $vopts " == *[[:space:]]"$prev"[[:space:]]* ]]; }}; then
        {fn}_value "$node" "$prev"
        return
    fi
    if $split || {{ [[ $skip == flag && " $tflags " == *[[:space:]]"$prev"[[:space:]]* && $cur != -* ]] &&
        [[ false == "${{cur,,}}"* || true == "${{cur,,}}"* ]]; }}; then
        mapfile -t COMPREPLY < <(compgen -W 'false true' -- "${{cur,,}}")
        return
    fi
    if [[ $cur == -* ]]; then
        mapfile -t COMPREPLY < <(compgen -W "$opts" -- "$cur")
        return
    fi
    if [[ $subs ]]; then
        {'[[ -z $node ]] && ((cword == 1)) && subs+=" gui"' if model["gui"] else ":"}
        mapfile -t COMPREPLY < <(compgen -W "$subs" -- "$cur")
        return
    fi
    read -ra kinds <<<"$args"
    w=${{kinds[${{#pos[@]}}]-}}
    ((${{#kinds[@]}})) && [[ -z $w && ${{kinds[-1]}} == commands ]] && w=commands
    case $w in
        file) _filedir ;;
        dir) _filedir -d ;;
        device) {fn}_devices ;;
        host) _known_hosts_real -- "$cur" ;;
        commands)
            # a command path: aaru cli explain image convert
            node=''
            for w in "${{pos[@]}}"; do
                {fn}_child "$node" "$w"
                [[ $REPLY ]] || return
                node=$REPLY
            done
            {fn}_node "$node"
            mapfile -t COMPREPLY < <(compgen -W "$subs" -- "$cur")
            ;;
    esac
}} &&
    complete -F {fn} {' '.join(names)}

# ex: filetype=sh
"""
    return out
