"""redumper: read the command line out of the source, render a bash completion.

redumper parses argv by hand (options.ixx): one positional command, options as
--key, --key=value or --key value. Everything offered comes from the parser
itself, so it includes what `redumper --help` leaves out. Every anchor is
asserted: an upstream refactor stops the generator instead of producing a short
list that looks complete.
"""
import re

FILES = ["options.ixx", "redumper.ixx", "drive.ixx"]

# What a value of these options IS. Everything else comes from the source: the
# parser says flag / string / int, the enum tables say the fixed value sets.
KINDS = {
    "--drive": "device",
    "--image-path": "dir",
    "--image-name": "dumpname",
    "--firmware": "file",
}

# (typed line, must be offered, must not be offered -- "*": nothing at all);
# {cmd} is the command name. Run by `gen.py smoke`.
SMOKE = [
    ("{cmd} ", {"disc", "dump", "refine", "drive::test", "debug::flip"}, set()),
    ("{cmd} dump ", set(), "*"),
    ("{cmd} --dri", {"--drive=", "--drive-type="}, {"--disc-type="}),
    ("{cmd} --deb", {"--debug"}, set()),
    ("{cmd} --disc-type=", {"CD", "DVD"}, set()),
    ("{cmd} --drive-read-method ", {"BE", "D8"}, set()),
    ("{cmd} --continue=drive::", {"detect"}, {"drive::detect"}),
    ("{cmd} --speed=", set(), "*"),
]


class ParseError(Exception):
    pass


def die(msg):
    raise ParseError(f"redumper: {msg}")


def string_table(text, name, fname):
    m = re.search(r"std::map<[^>]+,\s*std::string>\s+" + re.escape(name) + r"\s*=\s*\{(.*?)\n\};", text, re.S)
    if not m:
        die(f"string table {name} not found in {fname}")
    vals = re.findall(r'\{\s*[\w:]+\s*,\s*"([^"]+)"\s*\}', m.group(1))
    if len(vals) < 2:
        die(f"string table {name} has {len(vals)} values")
    return vals


def extract(src):
    opt_txt, red_txt, drv_txt = src["options.ixx"], src["redumper.ixx"], src["drive.ixx"]

    # --- commands: the COMMANDS map, plus "disc", which redumper() handles itself
    m = re.search(r"const std::map<std::string, Command> COMMANDS\{(.*?)\n\};", red_txt, re.S)
    if not m:
        die("COMMANDS map not found in redumper.ixx")
    commands = re.findall(r'\{\s*"([^"]+)",\s*\{\s*(?:true|false),', m.group(1))
    if len(commands) < 10 or not {"dump", "split", "refine"} <= set(commands):
        die(f"COMMANDS map parse looks wrong: {commands}")
    if not re.search(r'options\.command\s*==\s*"disc"', red_txt):
        die('"disc" aggregate command not found in redumper.ixx')
    commands.insert(0, "disc")

    # --continue takes one of the disc sub-commands
    fm = re.search(r"redumper_disc_get_commands\(Options &options\)\s*\{(.*?)\n\}", red_txt, re.S)
    if not fm:
        die("redumper_disc_get_commands not found")
    body = fm.group(1)
    lm = re.search(r"cd_commands\{([^}]*)\}", body)
    if not lm:
        die("cd_commands literal not found")
    cont = re.findall(r'"([^"]+)"', lm.group(1))
    cont += [x for x in re.findall(r'(?:insert\([^,]+,|push_back\()\s*"([^"]+)"\)', body) if x not in cont]
    if "dump" not in cont:
        die(f"--continue values look wrong: {cont}")

    # --- options: one branch per `if(key == "--a" || key == "-a")`; its statement
    # runs to the next branch and says what the value is
    pm = re.search(r"if\(s_value == nullptr && i_value == nullptr\)(.*?)// unknown option", opt_txt, re.S)
    if not pm:
        die("option dispatch block not found in options.ixx")
    block = pm.group(1)
    keys = list(re.finditer(r'if\((key == "-[^"]+"(?:\s*\|\|\s*key == "-[^"]+")*)\)', block))
    options = {}
    for i, km in enumerate(keys):
        end = keys[i + 1].start() if i + 1 < len(keys) else len(block)
        stmt = block[km.end():end]
        if "s_value" in stmt:
            arg = "string"
        elif "i_value" in stmt:
            arg = "int"
        elif "d_value" in stmt:
            arg = "number"
        elif re.search(r"\w+\s*=\s*true;", stmt):
            arg = "none"
        else:
            die(f"cannot classify option {km.group(1)}")
        for name in re.findall(r'key == "(-[^"]+)"', km.group(1)):
            if name in options:
                die(f"option {name} parsed twice")
            options[name] = arg
    if len(options) < 30 or not {"--drive", "--image-path", "--image-name", "--help"} <= set(options):
        die(f"option parse looks wrong: {sorted(options)}")
    if 'o.find("=")' not in opt_txt:
        die("'=' value split not found; the value syntax changed")

    # --- what --help lists (printUsage), to name what it does not ------------
    um = re.search(r"void printUsage\(\)\s*\{(.*?)\n    \}", opt_txt, re.S)
    if not um:
        die("printUsage not found")
    cpart, _, opart = um.group(1).partition('LOG("OPTIONS:");')
    if not opart:
        die("OPTIONS: section not found in printUsage")
    doc_cmds = set(re.findall(r'LOG\("\\t([a-z][\w:]*)\s*\\t', cpart))
    doc_opts = set(re.findall(r"(--[a-z0-9-]+)", opart))
    hk = re.search(r'helpKeys\(\)\s*\{\s*return "([^"]+)"', opt_txt)
    if hk and "helpKeys()" in opart:
        doc_opts |= set(hk.group(1).split(","))
    if "dump" not in doc_cmds or "--drive" not in doc_opts:
        die("printUsage parse looks wrong")

    # --- fixed value sets ------------------------------------------------------
    enums = {}
    for opt, table, txt, fname in (
            ("--disc-type", "DISC_TYPE_STRING", red_txt, "redumper.ixx"),
            ("--drive-type", "TYPE_STRING", drv_txt, "drive.ixx"),
            ("--drive-read-method", "READ_METHOD_STRING", drv_txt, "drive.ixx"),
            ("--drive-sector-order", "SECTOR_ORDER_STRING", drv_txt, "drive.ixx")):
        if opt not in options:
            die(f"{opt} vanished but its value table is still mapped here")
        enums[opt] = string_table(txt, table, fname)
    enums["--continue"] = cont

    for k in KINDS:
        if options.get(k) != "string":
            die(f"{k} is no longer a value option")
    return {
        "commands": commands,
        "options": options,
        "enums": enums,
        "hidden_commands": [c for c in commands if c not in doc_cmds],
        "hidden_options": [o for o in options if o not in doc_opts],
    }


def render(model, cmd, origin):
    fn = "_mediapres_" + re.sub(r"[^A-Za-z0-9]", "_", cmd)
    opts = model["options"]
    valopts = [o for o, a in opts.items() if a != "none"]
    words = [o + ("=" if a != "none" else "") for o, a in opts.items()]

    cases = []
    for name, kind in KINDS.items():
        body = {
            "device": f"{fn}_devices",
            "dir": "_filedir -d",
            "file": "_filedir",
            "dumpname": f"{fn}_dumpnames",
        }[kind]
        cases.append(f"        {name})\n            {body}\n            return\n            ;;")
    for name, values in model["enums"].items():
        trim = '\n            __ltrim_colon_completions "$cur"' if any(":" in v for v in values) else ""
        cases.append(f"        {name})\n            mapfile -t COMPREPLY < <(compgen -W '{' '.join(values)}' -- \"$cur\"){trim}\n            return\n            ;;")
    rest = [o for o in valopts if o not in KINDS and o not in model["enums"]]
    cases.append("        " + "|".join(rest) + ")\n            # a number or free text: nothing to offer\n            return\n            ;;")
    nl = "\n"

    return f"""# bash completion for {cmd}                                  -*- shell-script -*-
# shellcheck shell=bash
#
# GENERATED by scripts/completions/gen.py from {origin}.
# Do not edit: change the generator, then run `scripts/completions/gen.py write`.
#
# Every command and option the parser accepts (options.ixx, redumper.ixx), also
# the ones `{cmd} --help` does not list:
#   commands: {' '.join(model['hidden_commands']) or '-'}
#   options:  {' '.join(model['hidden_options']) or '-'}

{fn}_devices()
{{
    # optical drives: their block nodes and, as redumper lists them itself, their
    # SCSI generic nodes (sysfs type 5 = CD/DVD)
    local d t
    COMPREPLY=()
    for d in /dev/sr[0-9]*; do
        [[ -e $d && $d == "$cur"* ]] && COMPREPLY+=("$d")
    done
    for t in /sys/class/scsi_generic/sg[0-9]*/device/type; do
        [[ -r $t && $(<"$t") == 5 ]] || continue
        d=${{t%/device/type}}
        d=/dev/${{d##*/}}
        [[ -e $d && $d == "$cur"* ]] && COMPREPLY+=("$d")
    done
    ((${{#COMPREPLY[@]}})) || _filedir
}}

# --image-name of an existing dump: the stems of the dump files in --image-path
{fn}_dumpnames()
{{
    local i dir=. f
    for ((i = 1; i < cword; i++)); do
        case ${{words[i]}} in
            --image-path=*) dir=${{words[i]#--image-path=}} ;;
            --image-path) dir=${{words[i + 1]-.}} ;;
        esac
    done
    COMPREPLY=()
    for f in "$dir"/*.log "$dir"/*.scram "$dir"/*.iso; do
        [[ -e $f ]] || continue
        f=${{f##*/}}
        f=${{f%.*}}
        [[ $f == "$cur"* ]] && COMPREPLY+=("$f")
    done
    ((${{#COMPREPLY[@]}})) && mapfile -t COMPREPLY < <(printf '%s\\n' "${{COMPREPLY[@]}}" | sort -u)
}}

{fn}()
{{
    local cur prev words cword split
    _init_completion -s -n : || return

    case $prev in
{nl.join(cases)}
    esac
    $split && return

    if [[ $cur == -* ]]; then
        mapfile -t COMPREPLY < <(compgen -W '{' '.join(words)}' -- "$cur")
        [[ ${{COMPREPLY-}} == *= ]] && compopt -o nospace
        return
    fi

    # one command; a value option without '=' takes the next word
    local i
    for ((i = 1; i < cword; i++)); do
        case ${{words[i]}} in
            -*=*) ;;
            {'|'.join(valopts)}) ((i++)) ;;
            -*) ;;
            *) return ;;
        esac
    done
    mapfile -t COMPREPLY < <(compgen -W '{' '.join(model['commands'])}' -- "$cur")
    __ltrim_colon_completions "$cur"
}} &&
    complete -F {fn} {cmd}

# ex: filetype=sh
"""
