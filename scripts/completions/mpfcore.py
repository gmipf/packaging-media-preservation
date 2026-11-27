"""Shared part of the mpf-cli and mpf-check generators.

MPF parses by hand (MPF.<project>/Features/MainFeature.cs ProcessArgs): argv[1]
is the system, every later word is offered to an if/else-if chain of typed
inputs, and what no input takes becomes a plain input. A standalone command
(help, version, ls, ...) replaces the system when argv[1] names one of the
features Program.cs adds to its command set.

The values come from three sources at the revisions MPF pins:
  - MPF itself: the inputs, the commands, the program names (-u) and the log
    compression names (MPF.Frontend/EnumExtensions.cs);
  - SabreTools.RedumpLib: the systems and media types, at the version
    MPF.<project>.csproj references;
  - SabreTools.CommandLine: the flags of its built-in help and man features.
"""
import re

import clex


class ParseError(Exception):
    pass


FRONTEND_FEATURES = ["ListCodesFeature", "ListConfigFeature", "ListMediaTypesFeature",
                     "ListPathMacrosFeature", "ListProgramsFeature", "ListSystemsFeature",
                     "VersionFeature"]
LIBS = {"SabreTools.RedumpLib": ["SabreTools.RedumpLib/Data/PhysicalSystem.cs",
                                 "SabreTools.RedumpLib/Data/PhysicalMediaType.cs",
                                 "SabreTools.RedumpLib/Data/Extensions.cs"],
        "SabreTools.CommandLine": ["SabreTools.CommandLine/Features/Help.cs",
                                   "SabreTools.CommandLine/Features/Manpage.cs"]}

# What a plain string input names, by field. A new string input stops the run
# until it is added here: guessing "file" for a drive or a free text would offer
# the wrong thing without anyone noticing.
STRING_KINDS = {"DeviceInput": "device", "FileInput": "file", "MountedInput": "dir",
                "CustomInput": "text", "LoadSeedInput": "file", "PathInput": "dir"}
CONVERSIONS = {"ToInternalProgram": "program", "ToPhysicalMediaType": "media",
               "ToLogCompression": "logcomp"}


def die(project, msg):
    raise ParseError(f"{project}: {msg}")


def files(project):
    return [f"{project}/Program.cs", f"{project}/{project}.csproj",
            f"{project}/Features/MainFeature.cs", f"{project}/Features/BaseFeature.cs",
            f"{project}/Features/InteractiveFeature.cs", "MPF.Frontend/EnumExtensions.cs",
            *[f"MPF.Frontend/Features/{f}.cs" for f in FRONTEND_FEATURES]]


def lib_versions(src, project):
    csproj = src[f"{project}/{project}.csproj"]
    out = {}
    for lib in LIBS:
        v = re.findall(r'<PackageReference Include="' + re.escape(lib) + r'" Version="([^"]+)"', csproj)
        if len(v) != 1 or not re.fullmatch(r"[0-9][0-9.]*", v[0]):
            die(project, f"{project}.csproj: no single plain version of {lib}: {v}")
        out[lib] = v[0]
    return out


def deps(src, project):
    """(repo, ref, path) of the library files, at the versions the csproj pins."""
    return [(f"SabreTools/{lib}", ver, path)
            for lib, ver in lib_versions(src, project).items() for path in LIBS[lib]]


def lib(src, project, path):
    for lib_name in lib_versions(src, project):
        if path.startswith(lib_name + "/"):
            return src[f"SabreTools/{lib_name}/{path}"]
    die(project, f"no library file {path}")
    return None


def body(project, text, signature):
    """The text inside the braces of the method whose header contains signature."""
    bl = clex.blank(text)
    at = text.find(signature)
    if at < 0 or text.find(signature, at + 1) >= 0:
        die(project, f"not exactly one {signature!r}")
    rest = re.match(r"[^;{]*?\{", bl[at:])
    if not rest:
        die(project, f"no body after {signature!r}")
    open_at = at + rest.end() - 1
    return text[open_at + 1:clex.match(bl, open_at) - 1]


def no_comments(project, text):
    if "/*" in text:
        die(project, "block comment inside a parsed switch")
    return "\n".join(line for line in text.split("\n") if not line.strip().startswith("//"))


def strings(s):
    return re.findall(r'"([^"]*)"', s)


def static_items(project, text, cls, array):
    """name -> (display name, code, available, marker) for every static instance
    listed in `array`, in that order."""
    items = {}
    bl = clex.blank(text)  # commented-out instances do not count
    for m in re.finditer(r"public static readonly " + cls + r" (\w+) = new\(", bl):
        close = clex.match(bl, m.end() - 1, "(", ")")
        end = text.index(";", close)
        args, tail = text[m.end():close - 1], text[close:end]
        name = strings(args)[0]
        code = re.search(r'\bcode:\s*"([^"]*)"', args)
        items[m.group(1)] = (name, code.group(1) if code else None,
                             not re.search(r"\bavailable:\s*false\b", args),
                             bool(re.search(r"IsMarker\s*=\s*true", tail)))
    m = re.search(r"public static readonly " + cls + r"\[\] " + array + r" =\s*\[(.*?)\];", bl, re.S)
    if not m or not items:
        die(project, f"no {cls}.{array}")
    order = re.findall(r"\b(\w+)\b", re.sub(r"^\s*#\s*(end)?region\b.*$", "", m.group(1), flags=re.M))
    for n in order:
        if n not in items:
            die(project, f"{array} lists {n}, which is not a {cls}")
    return [items[n] for n in order]


def check_lookup(project, ext, sig, fragments):
    b = body(project, ext, sig)
    for f in fragments:
        if f not in b:
            die(project, f"{sig} no longer contains {f!r}: the way names are matched changed")


def systems(src, project):
    items = static_items(project, lib(src, project, "SabreTools.RedumpLib/Data/PhysicalSystem.cs"),
                         "PhysicalSystem", "AllSystems")
    check_lookup(project, lib(src, project, "SabreTools.RedumpLib/Data/Extensions.cs"),
                 "PhysicalSystem? ToPhysicalSystem(this string? system)",
                 ["system = system.ToLowerInvariant();", "system == s.Code?.ToLowerInvariant()",
                  's.Name.Replace(" ", string.Empty)'])
    words, by_name = [], []
    for name, code, _avail, marker in items:
        if marker:
            continue
        w = code.lower() if code else name.replace(" ", "").lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._+/-]*", w):
            by_name.append(name)
            continue
        words.append(w)
        if not code:
            by_name.append(name)
    if len(words) < 100:
        die(project, f"only {len(words)} systems")
    return words, [n for n in by_name if n.replace(" ", "").lower() not in words]


def media_types(src, project):
    items = static_items(project, lib(src, project, "SabreTools.RedumpLib/Data/PhysicalMediaType.cs"),
                         "PhysicalMediaType", "AllMediaTypes")
    check_lookup(project, lib(src, project, "SabreTools.RedumpLib/Data/Extensions.cs"),
                 "PhysicalMediaType? ToPhysicalMediaType(this string? mediaType)",
                 ["mediaType = mediaType.ToLowerInvariant();", "mediaType == mt.Code?.ToLowerInvariant()"])
    words = [code.lower() for _n, code, avail, _m in items if avail and code]
    if len(words) < 5 or any(not re.fullmatch(r"[a-z0-9-]+", w) for w in words):
        die(project, f"odd media type codes {words}")
    return words


def switch_arms(project, b, enum):
    """[(aliases, member)] of a `"a" or "b" => Enum.Member` switch, NONE excluded."""
    arms = re.findall(r'((?:"[^"]*"\s*(?:or\s+)?)+)=>\s*' + enum + r"\.(\w+)", no_comments(project, b))
    return [(strings(a), mem) for a, mem in arms if mem != "NONE"]


def programs(src, project):
    ext = src["MPF.Frontend/EnumExtensions.cs"]
    arms = switch_arms(project, body(project, ext, "InternalProgram ToInternalProgram(this string? internalProgram)"),
                       "InternalProgram")
    short = dict((mem, s) for mem, s in re.findall(
        r'InternalProgram\.(\w+)\s*=>\s*"([^"]*)"',
        no_comments(project, body(project, ext, "string ShortName(this InternalProgram? prog)"))))
    out = {}
    for aliases, mem in arms:
        if short.get(mem) not in aliases:
            die(project, f"ShortName of {mem} ({short.get(mem)!r}) is not one of its names {aliases}")
        out[mem] = short[mem]
    if len(out) < 4:
        die(project, f"only {len(out)} programs")
    return out


def dumping_programs(src, project):
    """The programs MPF.CLI dumps with: the cases before the 'not a supported
    dumping program' default."""
    b = src[f"{project}/Features/BaseFeature.cs"]
    at = b.find("is not a supported dumping program")
    sw = b.rfind("switch (Options.InternalProgram)", 0, at)
    if at < 0 or sw < 0:
        die(project, "no switch that refuses programs it cannot dump with")
    cases = re.findall(r"case InternalProgram\.(\w+):", b[sw:at])
    if not cases:
        die(project, "the dumping switch has no cases")
    return cases


def log_compressions(src, project):
    arms = switch_arms(project, body(project, src["MPF.Frontend/EnumExtensions.cs"],
                                     "LogCompression ToLogCompression(this string? logCompression)"),
                       "LogCompression")
    if not arms:
        die(project, "no log compression names")
    return [a[0] for a, _m in arms]


def features(src, project):
    """Standalone commands: [(flags, display name, takes files)]."""
    prog = src[f"{project}/Program.cs"]
    main = body(project, prog, "static void Main(string[] args)")
    added = re.findall(r"commandSet\.Add\(new (\w+)\(", prog)
    known = {}
    texts = [lib(src, project, p) for p in LIBS["SabreTools.CommandLine"]]
    texts += [src[f"MPF.Frontend/Features/{f}.cs"] for f in FRONTEND_FEATURES]
    texts.append(src[f"{project}/Features/InteractiveFeature.cs"])
    for t in texts:
        cls = re.findall(r"\bclass (\w+)\b", t)
        fl = re.findall(r"string\[\] _(?:default)?[fF]lags = \[([^\]]*)\]", t)
        dn = re.findall(r'const string DisplayName = "([^"]*)"', t)
        if len(cls) != 1 or len(fl) != 1 or len(dn) != 1:
            die(project, f"a feature file no longer has one class, one flag list, one name: {cls}")
        known[cls[0]] = (strings(fl[0]), dn[0], t)
    out = []
    for cls in added:
        if cls not in known:
            die(project, f"Program.cs adds {cls}, a feature the generator does not read")
        if not re.search(r"\bcase " + cls + r"\b", main):
            die(project, f"Main does not dispatch {cls}")
        flags, dn, t = known[cls]
        takes_files = cls == "InteractiveFeature" and "VerifyInputs() => Inputs.Count > 0" in t
        out.append((flags, dn, takes_files))
    if len(out) < 8:
        die(project, f"only {len(out)} standalone commands")
    return out


def inputs(src, project):
    """Accepted options: [(flags, kind)] in parse order."""
    text = src[f"{project}/Features/MainFeature.cs"]
    decl = {}
    for m in re.finditer(r"internal readonly (\w+)\s+(\w+)\s*=\s*new\(\s*_\w+\s*,\s*(\[[^\]]*\]|\"[^\"]*\")", text):
        decl[m.group(2)] = (m.group(1), strings(m.group(3)))
    if len(re.findall(r"internal readonly \w+Input\b", text)) != len(decl):
        die(project, "an input declaration the generator cannot read")
    b = body(project, text, "bool ProcessArgs(string[] args, int index)")
    if "System = args[0].Trim('\"').ToPhysicalSystem();" not in b:
        die(project, "argv[1] is no longer the system")
    loops = b.split("for (index = 1; index < args.Length; index++)")
    if len(loops) != 2 or "Inputs.Add(args[index]);" not in loops[1]:
        die(project, "not one option loop from argv[2] on that keeps the rest as inputs")
    loop = loops[1]
    out = []
    hits = list(re.finditer(r"(\w+)\.ProcessInput\(args, ref index\)", loop))
    for k, m in enumerate(hits):
        field = m.group(1)
        if field not in decl:
            die(project, f"ProcessArgs reads {field}, which is not declared")
        typ, flags = decl[field]
        seg = loop[m.end():hits[k + 1].start() if k + 1 < len(hits) else len(loop)]
        conv = re.findall(r"\b" + field + r"\.Value\??\.(?:Trim\('\"'\)\.)?(To\w+)\(\)", seg)
        if typ == "FlagInput":
            kind = None
        elif typ == "Int32Input":
            kind = "int"
        elif typ == "StringInput" and conv:
            if conv[0] not in CONVERSIONS:
                die(project, f"{field} is converted by {conv[0]}, which the generator does not know")
            kind = CONVERSIONS[conv[0]]
        elif typ == "StringInput" and field in STRING_KINDS:
            kind = STRING_KINDS[field]
        else:
            die(project, f"{field} ({typ}): the generator does not know what its value names")
        out.append((flags, kind))
    if len(out) < 5 or len({f for fl, _k in out for f in fl}) != sum(len(fl) for fl, _k in out):
        die(project, "too few options, or one flag read by two inputs")
    return out


def help_text(src, project):
    """(standalone commands, options) the hand-written help lists."""
    b = body(project, src[f"{project}/Features/BaseFeature.cs"], "static void DisplayHelp()")
    lines = [re.sub(r"\\(.)", r"\1", s) for s in
             re.findall(r'Console\.WriteLine\("((?:[^"\\]|\\.)*)"\)', b)]
    verbs, opts, section = set(), set(), None
    for line in lines:
        if line.endswith("Options:"):
            section = "verbs" if line == "Standalone Options:" else "opts"
            continue
        if not line.strip():
            section = None
            continue
        col = re.split(r"\s{2,}", line.strip())[0]
        if section == "verbs":
            verbs.update(w.strip() for w in col.split(","))
        elif section == "opts":
            opts.update(w for w in re.split(r"[ ,]+", col) if re.fullmatch(r"--?[\w-]+", w))
    if not verbs or not opts:
        die(project, "the help text has no command or option section")
    return verbs, opts


def extract(src, project, known_doc_only):
    feats = features(src, project)
    opts = inputs(src, project)
    doc_verbs, doc_opts = help_text(src, project)
    verbs = [f for fl, _d, _t in feats for f in fl]
    flags = [f for fl, _k in opts for f in fl]
    if doc_verbs - set(verbs):
        die(project, f"the help lists commands the parser does not have: {sorted(doc_verbs - set(verbs))}")
    doc_only = sorted(doc_opts - set(flags))
    # Only a new one stops the run: it may be an option the parser takes in a
    # shape the generator has not learned. A known one leaving the help (MPF
    # deleting a dead line, 5289666d) is harmless and passes.
    new = sorted(set(doc_only) - set(known_doc_only))
    if new:
        die(project, f"the help lists options the parser rejects, new since the generator was written: {new} "
                     f"(known: {sorted(known_doc_only)})")
    progs = programs(src, project)
    kinds = {k for _f, k in opts}
    model = dict(project=project, libs=lib_versions(src, project), features=feats, options=opts,
                 hidden_verbs=[v for v in verbs if v not in doc_verbs],
                 hidden_opts=[f for f in flags if f not in doc_opts], doc_only=doc_only,
                 internal_names=[d for fl, d, _t in feats if d not in fl])
    model["systems"], model["by_name_only"] = systems(src, project)
    if "media" in kinds:
        model["media"] = media_types(src, project)
    if "program" in kinds:
        allowed = dumping_programs(src, project) if project == "MPF.CLI" else list(progs)
        for p in allowed:
            if p not in progs:
                die(project, f"{p} is dumped with but has no name")
        model["programs"] = [progs[p] for p in allowed]
    if "logcomp" in kinds:
        model["logcomp"] = log_compressions(src, project)
    return model


def wrap(words, indent, width=80):
    lines, cur = [], ""
    for w in words:
        if cur and len(indent) + len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    lines.append(cur)
    return ("\n" + indent).join(lines)


def render(model, cmd, origin, names, positional_files):
    fn = "_mediapres_" + re.sub(r"\W", "_", cmd)
    title = f"# bash completion for {cmd}".ljust(64) + "-*- shell-script -*-"
    redumplib = model["libs"]["SabreTools.RedumpLib"]
    head = [title, "# shellcheck shell=bash", "#",
            f"# GENERATED by scripts/completions/gen.py from {origin}.",
            "# Do not edit: change the generator, then run `scripts/completions/gen.py write`.", "#",
            f"# {model['project']} takes a system, then options"
            + (", then the files to check;" if positional_files else ";")
            + " or one standalone command.",
            f"# Systems and media types come from SabreTools.RedumpLib {redumplib}.",
            "# Accepted although the help text does not list them:",
            f"#   commands: {' '.join(model['hidden_verbs']) or '(none)'}"]
    head += ["#   options:  " + line for line in
             wrap(model["hidden_opts"] or ["(none)"], "#   options:  ").split("\n#   options:  ")]
    if model["doc_only"]:
        head.append(f"# Listed by the help text, rejected by the parser: {' '.join(model['doc_only'])}")
    head.append("# Also accepted, not offered: `?` (h and help are), the internal command names"
                if any("?" in fl for fl, _d, _t in model["features"]) else
                "# Also accepted, not offered: the internal command names")
    head.append(f"# {' '.join(model['internal_names'])}, a system by its full name, and the other")
    head.append("# spellings of program and media type names.")
    if model["by_name_only"]:
        head.append("# Systems without a short code are offered by their name without spaces.")

    sysw = wrap(model["systems"], "        ")
    verbs = [f for fl, _d, _t in model["features"] for f in fl if f != "?"]
    file_verbs = [f for fl, _d, t in model["features"] if t for f in fl]
    plain_verbs = [f for f in verbs if f not in file_verbs]
    flags = [f for fl, _k in model["options"] for f in fl]
    cases = []
    quiet = [f for fl, kind in model["options"] if kind in ("int", "text") for f in fl]
    if quiet:  # a number or free text: nothing to offer
        cases.append(f"        {'|'.join(quiet)})\n            return\n            ;;")
    for fl, kind in model["options"]:
        if kind in (None, "int", "text"):
            continue
        pat = "|".join(fl)
        if kind == "device":
            act = f"{fn}_drives"
        elif kind == "file":
            act = "_filedir"
        elif kind == "dir":
            act = "_filedir -d"
        else:
            vals = {"program": model.get("programs"), "media": model.get("media"),
                    "logcomp": model.get("logcomp")}[kind]
            act = f"mapfile -t COMPREPLY < <(compgen -W '{' '.join(vals)}' -- \"$cur\")"
        cases.append(f"        {pat})\n            {act}\n            return\n            ;;")
    out = "\n".join(head) + "\n\n"
    if any(k == "device" for _f, k in model["options"]):
        out += (f"{fn}_drives()\n{{\n"
                "    local d\n    COMPREPLY=()\n"
                "    for d in /dev/sr[0-9]*; do\n"
                "        [[ -e $d && $d == \"$cur\"* ]] && COMPREPLY+=(\"$d\")\n    done\n"
                "    ((${#COMPREPLY[@]})) || _filedir\n}\n\n")
    out += f"{fn}()\n{{\n    local cur prev words cword split\n    _init_completion -s || return\n\n"
    out += ("    if ((cword == 1)); then\n"
            f"        local systems='{sysw}'\n"
            f"        mapfile -t COMPREPLY < <(compgen -W \"{' '.join(verbs)} $systems\" -- \"$cur\")\n"
            "        return\n    fi\n\n")
    out += "    case ${words[1]} in\n"
    if file_verbs:
        out += f"        {'|'.join(file_verbs)})\n            _filedir\n            return\n            ;;\n"
    qm = "\\?|" if any("?" in fl for fl, _d, _t in model["features"]) else ""
    out += f"        {qm}{'|'.join(plain_verbs)})\n            return\n            ;;\n    esac\n\n"
    out += "    case $prev in\n" + "\n".join(cases) + "\n    esac\n    $split && return\n\n"
    optw = wrap(flags, "        ")
    if positional_files:
        out += ("    if [[ $cur == -* ]]; then\n"
                f"        mapfile -t COMPREPLY < <(compgen -W '{optw}' -- \"$cur\")\n"
                "    else\n        _filedir\n    fi\n")
    else:
        out += f"    mapfile -t COMPREPLY < <(compgen -W '{optw}' -- \"$cur\")\n"
    out += f"}} &&\n    complete -F {fn} {' '.join(names)}\n\n# ex: filetype=sh\n"
    return out
