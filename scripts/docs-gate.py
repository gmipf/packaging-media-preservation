#!/usr/bin/env python3
"""A recipe change says what it means for the texts a reader sees.

A commit that changes a recipe (fedora/, opensuse/, ubuntu/, Formula/),
.packit.yaml or a workflow must also change a text -- README.md, CHANGELOG.md,
anything under docs/ (the live descriptions included, docs/descriptions/), the
lane READMEs -- or say in its message why none needs it, as a trailer in the
last paragraph:

    Docs-unchanged: <why, in a few words>

  docs-gate.py --msg FILE     .githooks/commit-msg: the staged change and this message
  docs-gate.py --range A..B   check-repo.yml: every non-merge commit pushed

Why: the texts fell behind the recipes again and again, and every time the step
was simply forgotten. A trailer costs one line and makes "nothing changed for a
reader" a decision instead of an omission. The gate cannot judge the decision;
it names the texts that mention each package the commit touches, so it is made
with them in view. Whether the texts still match the tree and the live
services is scripts/texts-check.py.

The hook sees the staged change, so after `git commit --amend` it sees only what
the amend adds; CI reads the whole commit. Commits pushed by the watchers start
no workflow (GITHUB_TOKEN), so CI only ever reads commits a person pushed.

Exit 0 ok, 1 finding, 2 not measurable (git failed, a range it cannot read).
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RECIPE = re.compile(r"(?:fedora|opensuse|ubuntu|Formula)/|\.packit\.yaml$|\.github/workflows/")
TEXT = re.compile(r"(?:README\.md|CHANGELOG\.md|docs/.+|(?:opensuse|ubuntu)/[^/]+\.md)$")
TRAILER = "Docs-unchanged"
MIN_WORDS = 3
SCISSORS = "# ------------------------ >8 ------------------------"


class Unmeasured(Exception):
    pass


def git(*args, root=ROOT, stdin=None):
    r = subprocess.run(["git", "-C", str(root), *args], input=stdin, capture_output=True, text=True)
    if r.returncode:
        raise Unmeasured(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def classify(paths):
    text = [p for p in paths if TEXT.fullmatch(p)]
    recipe = [p for p in paths if RECIPE.match(p) and not TEXT.fullmatch(p)]
    return recipe, text


def cleaned(msg):
    """The message as git stores it: no comment lines, nothing below the scissors."""
    msg = msg.split(SCISSORS, 1)[0]
    return "\n".join(line for line in msg.split("\n") if not line.startswith("#"))


def reason(msg, root=ROOT):
    """The Docs-unchanged trailer's text, or None. Only a real trailer counts (last paragraph)."""
    for line in git("interpret-trailers", "--parse", root=root, stdin=msg).splitlines():
        key, _, value = line.partition(":")
        if key.strip().lower() == TRAILER.lower():
            return value.strip()
    return None


def judge(paths, msg, root=ROOT):
    """(ok, recipe paths, why)."""
    recipe, text = classify(paths)
    if not recipe:
        return True, recipe, "no recipe, .packit.yaml or workflow change"
    if text:
        return True, recipe, f"texts change with it: {', '.join(text[:3])}{' ...' if len(text) > 3 else ''}"
    r = reason(msg, root)
    if r is None:
        return False, recipe, "no text changed and no `Docs-unchanged:` trailer"
    if len(r.split()) < MIN_WORDS:
        return False, recipe, f"`Docs-unchanged: {r}` gives no reason (at least {MIN_WORDS} words)"
    return True, recipe, f"Docs-unchanged: {r}"


def names(text, name):
    return re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", text, re.I) is not None


def hints(recipe, root=ROOT):
    """Lines naming the texts that mention what the commit touched."""
    pkgs = set()
    for p in recipe:
        parts = p.split("/")
        if parts[0] in ("fedora", "opensuse", "ubuntu") and len(parts) >= 3:
            pkgs.add(parts[1])
        elif parts[0] == "Formula" and p.endswith(".rb"):
            pkgs.add(parts[1][:-3])
    texts = {}
    for t in git("ls-files", "-z", root=root).split("\0"):
        if t and TEXT.fullmatch(t):
            try:
                texts[t] = (root / t).read_text(encoding="utf-8")
            except OSError:
                pass
    out = []
    for pkg in sorted(pkgs):
        hit = [t for t in sorted(texts) if names(texts[t], pkg)]
        out.append(f"  `{pkg}` is named in: {', '.join(hit) if hit else 'no text at all -- a new package?'}")
    if any(p.startswith(".github/workflows/") for p in recipe):
        out.append("  a workflow changed: docs/how-it-works.md lists what each one does")
    if ".packit.yaml" in recipe:
        out.append("  .packit.yaml changed: a new distribution or architecture belongs in CHANGELOG.md")
    return out


ADVICE = f"""  Update what changed for a reader (README.md, docs/, CHANGELOG.md, the lane
  READMEs; a changed docs/descriptions/ text is then published, see its README),
  or say why nothing did, as a trailer in the message's last paragraph:
      {TRAILER}: <why, in a few words>"""


def report(head, recipe, why, root=ROOT):
    more = f" and {len(recipe) - 1} more" if len(recipe) > 1 else ""
    print(f"docs-gate: {head} changes {recipe[0]}{more}: {why}.")
    for line in hints(recipe, root):
        print(line)
    print(ADVICE)


def staged(msgfile, root=ROOT):
    gitdir = pathlib.Path(git("rev-parse", "--absolute-git-dir", root=root).strip())
    if (gitdir / "MERGE_HEAD").exists():
        print("docs-gate: a merge commit -- not checked here; CI reads the commits it brings")
        return 0
    try:
        msg = cleaned(pathlib.Path(msgfile).read_text(encoding="utf-8"))
    except OSError as e:
        raise Unmeasured(f"{msgfile}: {e.strerror or e}") from e
    paths = [p for p in git("diff", "--cached", "--name-only", "-z", root=root).split("\0") if p]
    ok, recipe, why = judge(paths, msg, root)
    if ok:
        print(f"docs-gate: ok -- {why}")
        return 0
    report("this commit", recipe, why, root)
    return 1


def pushed(rng, root=ROOT):
    base, sep, head = rng.partition("..")
    if not sep or not head:
        raise Unmeasured(f"not a range: {rng!r}")
    if re.fullmatch(r"0{40}", base):            # a new branch: its tip alone
        revs = git("rev-list", "--no-merges", "-n", "1", head, root=root).split()
    else:
        for rev in (base, head):
            git("cat-file", "-e", f"{rev}^{{commit}}", root=root)
        revs = git("rev-list", "--no-merges", "--reverse", f"{base}..{head}", root=root).split()
    bad = 0
    for c in revs:
        paths = [p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", c,
                                root=root).split("\0") if p]
        msg = git("log", "-1", "--format=%B", c, root=root)
        ok, recipe, why = judge(paths, msg, root)
        subject = msg.split("\n", 1)[0]
        if ok:
            print(f"docs-gate: ok   {c[:8]} {subject} -- {why}")
        else:
            bad += 1
            report(f"{c[:8]} ({subject})", recipe, why, root)
    print(f"docs-gate: {len(revs)} commit(s) read, {bad} without a text change or a reason")
    return 1 if bad else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        if len(argv) == 2 and argv[0] == "--msg":
            return staged(argv[1])
        if len(argv) == 2 and argv[0] == "--range":
            return pushed(argv[1])
    except Unmeasured as e:
        print(f"docs-gate: NOT MEASURED -- {e}", file=sys.stderr)
        return 2
    print("usage: docs-gate.py --msg FILE | --range A..B", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
