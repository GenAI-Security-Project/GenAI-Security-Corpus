# inbox/ -- submit new corpus resources here

Drop a new resource (PDF, markdown, JSON, or a folder of them) in this folder in
a pull request. The `process-inbox` workflow checks it and moves it into
`corpus/` with a `MANIFEST.yaml` entry, committed back to your PR branch. A
CODEOWNER then reviews and merges.

**This folder is always empty on `main`.** CI fails while anything other than
this README is here, so nothing unreviewed is ever published.

## How to submit

1. Add the file, e.g. `inbox/My-Guide-v1.0.pdf`.
2. Add a sidecar with the same name and a `.yaml` extension,
   e.g. `inbox/My-Guide-v1.0.yaml`:

   ```yaml
   title: "My Guide"                    # defaults to the PDF's metadata title
   initiative: mcp-security             # required: corpus/ subfolder (new ones OK)
   source_url: https://genai.owasp.org/resource/...   # or source_repo (+ source_path)
   version: "1.0"                       # defaults to the version in the file name
   published: "2026-10-01"              # optional
   folder: companions                   # optional subfolder under the initiative
   supersedes: some-existing-id         # optional: marks that entry superseded
   status: current                      # current (default) | draft | linked
   id: my-guide-1.0                     # optional: defaults to the file name
   notes: >
     What it is and when the Advisor should use it.
   ```

3. Open a PR. The workflow comments with what it did, or why a submission was
   held.

To work locally instead, run `python scripts/process_inbox.py` (add
`--dry-run` to preview) and commit the result.

## License rules

The processor only moves a file into `corpus/` when the document itself states
one of these licenses: CC BY-SA 4.0, CC BY 4.0, Apache-2.0 or MIT. A vague
"released under creative commons licenses" doesn't count.

- **No license statement found:** the file is held. Either confirm the license
  with the initiative lead and add a statement, or set `status: linked`.
- **`status: linked`:** catalogs the resource with `path: null` and
  `license: UNCONFIRMED`, and deletes the file. The Advisor links to
  `source_url` and doesn't quote from it. A sidecar on its own (no file) works
  for this too.
- **Any other license (e.g. NC/ND variants):** held for a maintainer decision.

Reviewers still confirm the license before merging. The detector helps
reviewers; it doesn't replace them.
