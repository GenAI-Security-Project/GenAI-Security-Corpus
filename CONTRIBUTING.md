# Contributing

## Adding a corpus resource

See "Adding or updating a resource" in [README.md](./README.md). In short: drop the
file(s) in `corpus/<initiative>/`, add a `corpus/MANIFEST.yaml` entry, open a PR --
CI validates the manifest, and PDF text extraction runs automatically after merge.

## Changing the tooling

`scripts/validate_corpus.py` and `scripts/extract_pdf_text.py` are run by the
workflows in `.github/workflows/`. Changing `extract_pdf_text.py` re-runs extraction
on the next push to `main`.

## Skill instructions

`SKILL.md` lives in
[GenAI-Security-Advisor](https://github.com/GenAI-Security-Project/GenAI-Security-Advisor),
along with the skill's versioning and changelog. Open a PR there when a corpus
change should alter how the skill describes or uses the corpus.

## License

By contributing, you agree that:
- Contributions to `scripts/`, workflows, and other repo-native files are licensed
  under this repo's Apache-2.0 license.
- Contributions to `corpus/` are either your own original work under a compatible
  license, or vendored content from an OWASP GenAI Security Project source whose
  license is recorded accurately in the `MANIFEST.yaml` entry.
