# GenAI Security Corpus

The curated, versioned research corpus behind the OWASP GenAI Security Project's
advisor tooling. **This repo is the authoritative source of the corpus** -- the
single place where corpus content is added, updated, validated, and processed.

Consumers:

- [GenAI-Security-Advisor-MCP](https://github.com/GenAI-Security-Project/GenAI-Security-Advisor-MCP)
  -- remote MCP server; reads `corpus/MANIFEST.yaml` and files from this repo's
  `main` branch at query time (edge-cached for up to an hour).
- [GenAI-Security-Advisor](https://github.com/GenAI-Security-Project/GenAI-Security-Advisor)
  -- the Agent Skill (`SKILL.md`). It bundles a copy of `corpus/`, which a GitHub
  Action copies over from this repo when the corpus changes. **Never edit the
  skills repo's `corpus/` directly** -- changes there are overwritten by the next
  copy. Skill instructions live there; corpus content lives here.

## Layout

```text
corpus/
  MANIFEST.yaml          # catalog of every resource -- the single source of truth
  <initiative>/...       # vendored content, grouped by initiative
  _extracted/            # auto-generated PDF text (search index only, never edit)
inbox/                   # submission drop zone -- always empty on main
scripts/
  validate_corpus.py     # MANIFEST checks, run by CI on every PR
  process_inbox.py       # inbox/ -> corpus/ + MANIFEST entry, with license check
  extract_pdf_text.py    # regenerates corpus/_extracted/ from vendored PDFs
  requirements.txt
.github/workflows/
  validate-corpus.yaml   # PR check
  process-inbox.yaml     # PR: processes inbox/ submissions onto the PR branch
  extract-pdf-text.yaml  # runs on push to main, commits refreshed _extracted/
```

## Adding or updating a resource

**Easiest: use the inbox.** Put the file and a small `.yaml` sidecar in
`inbox/` and open a PR. The `process-inbox` workflow checks the document for an
explicit license statement, moves it into `corpus/`, writes the `MANIFEST.yaml`
entry (and marks anything it supersedes), and comments on the PR with what it
did. See [inbox/README.md](inbox/README.md). Don't have the file, or don't want
to open a PR? Use the **Propose a corpus resource** issue form instead.

The manual steps below are what the inbox automates, and still apply for
anything it can't handle (e.g. turning an existing `linked` entry into a
vendored one).

1. **Confirm the license.** Only vendor (copy in) a document whose license is
   explicitly stated in the source -- most OWASP GenAI Security Project output is
   CC BY-SA 4.0. If you can't confirm it, catalog it as a `linked` entry instead
   (step 3) and don't commit the file.
2. **Add the file(s)** under the appropriate `corpus/<initiative>/` folder. If it
   supersedes an existing resource, use a new version- or date-named folder
   rather than overwriting the old file. A new initiative folder is fine.
3. **Add an entry to `corpus/MANIFEST.yaml`.**

   ```yaml
   - id: my-resource-1.0            # unique, stable
     title: "Full Document Title"
     initiative: mcp-security       # matches the corpus/ subfolder
     version: "1.0"
     status: current                # current | draft | superseded | linked
     format: pdf                    # markdown | pdf | json | mixed
     path: corpus/mcp-security/My-Resource-v1.0.pdf   # file, or folder ending in /
     license: CC-BY-SA-4.0
     source_url: https://genai.owasp.org/resource/...  # and/or source_repo + source_path
     vendored_commit: <sha>         # when copied from a git repo
     vendored_date: "YYYY-MM-DD"
     published: "YYYY-MM-DD"        # or null if unknown
     notes: >
       What it is and when to use it.
   ```

   For a `linked` entry: `path: null`, `license: UNCONFIRMED` (or the actual
   license if known but not vendored), and a `source_url` or `source_repo`.
4. **If it replaces something,** set the old entry's `status: superseded`. Don't
   delete it -- historical questions still need it.
5. **Validate locally (optional):**

   ```bash
   pip install -r scripts/requirements.txt
   python scripts/validate_corpus.py
   ```

6. **Open a PR.** `validate-corpus.yaml` checks that `inbox/` is empty and that every entry has its required
   fields, ids are unique, `status` is valid, and `path` exists (or is `null` for
   `linked`). CODEOWNERS review is required for `corpus/`.
7. **After merge,** `extract-pdf-text.yaml` extracts text from every `current` or
   `draft` PDF (including PDFs inside a `mixed` folder) into `corpus/_extracted/`
   and commits it to `main`, so the MCP server's full-text search picks it up.
   It can also be run manually from the Actions tab (`workflow_dispatch`).

Don't hand-edit `corpus/_extracted/`; see its [README](corpus/_extracted/README.md).

### Updating from upstream

Everything under `corpus/` is a frozen point-in-time copy -- there's no sync
with the upstream initiative repos. Pulling in an upstream change is always
manual: re-fetch, review, update `vendored_commit` / `vendored_date`, PR.

### Letting the skill know

The MCP server picks up merged changes automatically, and the copy Action carries
them into the skills repo's `corpus/`. The skill's `SKILL.md`
describes corpus areas in prose, so a new initiative or a superseded headline
resource should also get a matching update (and version bump) in
[GenAI-Security-Advisor](https://github.com/GenAI-Security-Project/GenAI-Security-Advisor).

## Licensing

Repo-native files (scripts, workflows, docs, `MANIFEST.yaml`) are Apache-2.0 --
see [LICENSE](LICENSE). Content under `corpus/` is third-party and keeps its
original license, recorded per entry in `corpus/MANIFEST.yaml` (mostly
CC BY-SA 4.0). Extracted text inherits its source PDF's license.
