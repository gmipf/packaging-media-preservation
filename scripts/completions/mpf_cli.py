"""mpf-cli: see mpfcore.py."""
import mpfcore
from mpfcore import ParseError  # noqa: F401  # gen.py catches mod.ParseError

PROJECT = "MPF.CLI"
FILES = mpfcore.files(PROJECT)
SMOKE = [
    ("{cmd} ", {"ps2", "version", "listsystems", "man", "lpm", "listpath"}, {"Help", "listpathmacros"}),
    ("{cmd} ps2 -u ", {"aaru", "dic", "dreamdump", "redumper"}, {"cleanrip", "xbc", "chef"}),
    ("{cmd} ps2 --use=", {"redumper"}, {"generic"}),
    ("{cmd} ps2 -t ", {"cdrom", "dvd", "bdrom"}, {"aperture", "cd"}),
    ("{cmd} ps2 --", {"--use", "--mediatype", "--retries", "--custom"}, set()),
    ("{cmd} ps2 -s ", set(), "*"),
    ("{cmd} ps2 -c ", set(), "*"),
    ("{cmd} version ", set(), "*"),
    ("{cmd} i ", set(), "*"),
]


def deps(src):
    return mpfcore.deps(src, PROJECT)


def extract(src):
    return mpfcore.extract(src, PROJECT, known_doc_only=[])


def render(model, cmd, origin, names):
    return mpfcore.render(model, cmd, origin, names, positional_files=False)
