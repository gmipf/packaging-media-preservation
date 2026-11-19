"""mpf-check: see mpfcore.py."""
import mpfcore
from mpfcore import ParseError  # noqa: F401  # gen.py catches mod.ParseError

PROJECT = "MPF.Check"
FILES = mpfcore.files(PROJECT)
# Options the help text names but the parser does not take. Empty since MPF
# 1217ed66 (until then --disable-archives, --enable-debug, --include-artifacts).
# A new name here stops the run: it may be a parser change the generator has
# not learned.
KNOWN_DOC_ONLY = []
# The help text's old names, which the parser never took: never offered.
OLD_HELP_NAMES = {"--disable-archives", "--enable-debug", "--include-artifacts"}
SMOKE = [
    ("{cmd} ", {"ps2", "i", "interactive", "man", "lpm"}, {"Help", "Manpage"}),
    ("{cmd} ps2 -u ", {"aaru", "dic", "redumper", "cleanrip", "xbc", "generic"}, {"chef", "rd"}),
    ("{cmd} ps2 --log-compression ", {"store", "deflate", "deflatemaximum"}, {"zip", "max"}),
    ("{cmd} ps2 --", {"--no-zip", "--archives", "--attempt-count", "--load-seed"}, OLD_HELP_NAMES),
    ("{cmd} ps2 --attempt-count ", set(), "*"),
    ("{cmd} ps2 -t", set(), {"-t"}),
    ("{cmd} version ", set(), "*"),
]


def deps(src):
    return mpfcore.deps(src, PROJECT)


def extract(src):
    return mpfcore.extract(src, PROJECT, known_doc_only=KNOWN_DOC_ONLY)


def render(model, cmd, origin, names):
    return mpfcore.render(model, cmd, origin, names, positional_files=True)
