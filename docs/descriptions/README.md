# The live descriptions

Back to [how-it-works.md](../how-it-works.md).

Three services show a description of this project that does not live in a file
they read from here. These are their texts, word for word:

| file | where it is shown | format |
|---|---|---|
| `github-about.txt` | the repository's *About* on GitHub | one line |
| `copr-description.md` | COPR project page, *Description* | Markdown |
| `copr-instructions.md` | COPR project page, *Installation Instructions* | Markdown |
| `obs-title.txt` | OBS project, title | one line |
| `obs-description.txt` | OBS project, description | plain text (OBS renders no Markdown) |

`scripts/texts-check.py live` compares each with the live text, on every push to
`main` (check-repo.yml) and in `scripts/status.sh`. A difference is red either
way round:

- **changed here** → publish it, then the check turns green again:
  - GitHub: `gh repo edit --description "$(cat docs/descriptions/github-about.txt)"`
  - COPR: `copr-cli modify media-preservation --description "$(cat docs/descriptions/copr-description.md)" --instructions "$(cat docs/descriptions/copr-instructions.md)"`
  - OBS: `osc meta prj -e home:gmipf:media-preservation` and replace `<title>`
    and `<description>` (XML-escape `&`, `<` and `"`)
- **changed on the service** (an edit in a web form) → take it into git, or put
  the git text back.

`scripts/texts-check.py offline` (part of `scripts/lint.sh`) also makes sure the
COPR texts name every Fedora/EPEL package and the OBS text every package OBS
builds, and the live check that they name every release COPR and OBS build for.
