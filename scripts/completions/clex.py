"""Small helpers to read C/C++ source as text: blank out comments and string
literals, match braces, find a function body, and take the Linux branch of
#ifdef _WIN32 blocks. Shared by the DiscImageCreator family generators.
"""
import re


class CError(Exception):
    pass


def blank(text):
    """The same text with comments and the inside of string and character
    literals replaced by spaces, so braces and parentheses can be counted."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise CError("unterminated comment")
            j += 2
            out[i:j] = [c if c == "\n" else " " for c in text[i:j]]
            i = j
        elif text[i] in "\"'":
            q, j = text[i], i + 1
            while j < n and text[j] != q:
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                raise CError("unterminated literal")
            out[i + 1:j] = " " * (j - i - 1)
            i = j + 1
        else:
            i += 1
    return _first_branches("".join(out))


def _first_branches(bl):
    """Blank every #elif / #else branch, so a line that opens a block once per
    platform (`#if A` `if (x) {` `#elif B` `if (y) {` `#endif`) counts once."""
    lines, stack = bl.split("\n"), []
    for k, line in enumerate(lines):
        d = re.match(r"\s*#\s*(\w+)", line)
        word = d.group(1) if d else None
        if word in ("if", "ifdef", "ifndef"):
            stack.append(False)
        elif word in ("elif", "else") and stack:
            stack[-1] = True
        elif word == "endif" and stack:
            stack.pop()
        elif any(stack):
            lines[k] = " " * len(line)
    return "\n".join(lines)


def match(bl, start, open_ch="{", close_ch="}"):
    """bl[start] == open_ch (in blanked text); the index just past its partner."""
    if bl[start] != open_ch:
        raise CError(f"expected {open_ch!r} at {start}")
    depth = 0
    for i in range(start, len(bl)):
        if bl[i] == open_ch:
            depth += 1
        elif bl[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
    raise CError(f"unbalanced {open_ch}{close_ch}")


def function_body(text, name):
    """The text between the braces of the definition of function `name`."""
    bl = blank(text)
    for m in re.finditer(r"^[A-Za-z_][\w \t*]*?\b" + re.escape(name) + r"\s*\(", bl, re.M):
        close = match(bl, m.end() - 1, "(", ")")
        rest = re.match(r"\s*\{", bl[close:])
        if rest:  # a definition, not a prototype
            open_at = close + rest.end() - 1
            return text[open_at + 1:match(bl, open_at) - 1]
    raise CError(f"no definition of {name}()")


def depth_at(bl, pos):
    """Brace depth at pos in blanked text."""
    return bl.count("{", 0, pos) - bl.count("}", 0, pos)


def linux_view(text):
    """Keep what a Linux build compiles of #ifdef/#ifndef _WIN32 ... #else ...
    #endif blocks. Any other conditional is refused: the caller has to learn it."""
    out, stack = [], []
    for line in text.split("\n"):
        d = re.match(r"\s*#\s*(\w+)\s*(.*)$", line)
        if not d:
            if all(stack):
                out.append(line)
            continue
        word, arg = d.group(1), d.group(2).strip()
        if word in ("ifdef", "if") and re.fullmatch(r"(defined\s*\(\s*)?_WIN32(\s*\))?", arg):
            stack.append(False)
        elif word == "ifndef" and arg == "_WIN32":
            stack.append(True)
        elif word == "else" and stack:
            stack[-1] = not stack[-1]
        elif word == "endif" and stack:
            stack.pop()
        else:
            raise CError(f"preprocessor line the generator does not know: {line.strip()!r}")
    if stack:
        raise CError("unbalanced #if")
    return "\n".join(out)


def c_strings(text):
    """The concatenated contents of every string literal in text, unescaped."""
    parts = re.findall(r'"((?:[^"\\\n]|\\.)*)"', text)
    s = "".join(parts)
    return re.sub(r"\\(.)", lambda m: {"t": "\t", "n": "\n"}.get(m.group(1), m.group(1)), s)
