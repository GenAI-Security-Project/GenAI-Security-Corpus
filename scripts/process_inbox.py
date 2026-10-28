#!/usr/bin/env python3
"""Process submissions in inbox/ into corpus/ + corpus/MANIFEST.yaml.

Each submission is a file (or folder) at the top of inbox/, plus an optional
sidecar `<name>.yaml` describing it (see inbox/README.md). For each one:

  1. Look for an explicit license statement in the text (e.g. "CC BY-SA 4.0").
     A vague mention like "released under creative commons licenses" does NOT
     count -- see the governance checklist / exploit generation entries in the
     manifest for why.
  2. If a known redistributable license is found (or the sidecar sets
     `license:` and the detector doesn't contradict it), move the file into
     corpus/<initiative>/[<folder>/] and append a MANIFEST entry.
  3. If the sidecar says `status: linked`, append a linked entry (path: null)
     and delete the file -- it must never be vendored.
  4. Otherwise leave the file in inbox/ and report why. validate_corpus.py
     fails while inbox/ is non-empty, so the PR can't merge until resolved.
  5. If the sidecar names `supersedes: <id>`, flip that entry to superseded.

Writes a markdown report (--report) for the PR comment / job summary. Exits 1
if anything was left unprocessed. Run from the repo root:

    python scripts/process_inbox.py            # process
    python scripts/process_inbox.py --dry-run  # report only, change nothing
"""
import argparse
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone

import yaml
from pypdf import PdfReader

INBOX = "inbox"
INBOX_KEEP = {"README.md", ".gitkeep"}
MANIFEST = os.path.join("corpus", "MANIFEST.yaml")

# Licenses that may be vendored without further review. Anything else that's
# detected is reported, and the submission is held for a maintainer.
VENDORABLE = {"CC-BY-SA-4.0", "CC-BY-4.0", "Apache-2.0", "MIT"}

LICENSE_PATTERNS = [
    # Order matters: most specific first.
    ("CC-BY-NC-SA-4.0", r"cc[\s-]*by[\s-]*nc[\s-]*sa[\s-]*4|attribution[\s-]+noncommercial[\s-]+sharealike\s+4"),
    ("CC-BY-NC-4.0", r"cc[\s-]*by[\s-]*nc[\s-]*4|attribution[\s-]+noncommercial\s+4"),
    ("CC-BY-ND-4.0", r"cc[\s-]*by[\s-]*nd[\s-]*4|attribution[\s-]+noderivatives\s+4"),
    ("CC-BY-SA-4.0", r"cc[\s-]*by[\s-]*sa[\s-]*4|attribution[\s-]+sharealike\s+4"),
    ("CC-BY-4.0", r"cc[\s-]*by[\s-]*4\.0|creative\s+commons\s+attribution\s+4"),
    ("Apache-2.0", r"apache\s+license,?\s+version\s+2|apache[\s-]+2\.0\s+licen[sc]e"),
    ("MIT", r"\bmit\s+licen[sc]e\b"),
]

FORMAT_BY_EXT = {".pdf": "pdf", ".md": "markdown", ".json": "json"}
TEXT_EXTS = {".md", ".txt", ".json", ".yaml", ".yml"}

logging.getLogger("pypdf").setLevel(logging.ERROR)


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", s.lower()).strip("-")


def text_pages(path: str):
    """Yield (location, text) for a file, page by page for PDFs."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        for i, page in enumerate(PdfReader(path).pages, start=1):
            yield f"page {i}", page.extract_text() or ""
    elif ext in TEXT_EXTS:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            yield "text", f.read()


def files_of(path: str):
    if os.path.isdir(path):
        for root, _, names in os.walk(path):
            for n in sorted(names):
                yield os.path.join(root, n)
    else:
        yield path


def detect_licenses(path: str):
    """Return {license_id: first 'file @ location'} for explicit statements."""
    found = {}
    for f in files_of(path):
        for loc, text in text_pages(f):
            flat = re.sub(r"\s+", " ", text)
            for lic, pat in LICENSE_PATTERNS:
                if lic not in found and re.search(pat, flat, re.I):
                    found[lic] = f"{os.path.basename(f)} @ {loc}"
    # "CC BY-SA 4" also matches the CC-BY-4.0 attribution pattern in some
    # wordings; a ShareAlike/NC/ND variant always wins over plain CC BY.
    if "CC-BY-4.0" in found and any(k.startswith("CC-BY-") and k != "CC-BY-4.0" for k in found):
        del found["CC-BY-4.0"]
    return found


def pdf_title(path: str):
    if not path.lower().endswith(".pdf"):
        return None
    meta = PdfReader(path).metadata
    title = (meta.title if meta else None) or ""
    return title.strip() or None


def guess_version(name: str):
    m = re.search(r"v?(\d+(?:\.\d+)+)", name)
    return m.group(1) if m else None


def guess_format(path: str) -> str:
    if os.path.isdir(path):
        fmts = {FORMAT_BY_EXT.get(os.path.splitext(f)[1].lower(), "other") for f in files_of(path)}
        return fmts.pop() if len(fmts) == 1 and "other" not in fmts else "mixed"
    return FORMAT_BY_EXT.get(os.path.splitext(path)[1].lower(), "mixed")


def yaml_scalar(v) -> str:
    if v is None:
        return "null"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_entry(e: dict) -> str:
    """Render a manifest entry in the hand-written style of MANIFEST.yaml."""
    lines = [f"  - id: {e['id']}"]
    order = ["title", "initiative", "version", "status", "format", "path", "license",
             "source_repo", "source_path", "source_url", "vendored_commit",
             "vendored_date", "published"]
    plain = {"initiative", "status", "format", "license", "source_repo",
             "source_path", "source_url", "vendored_commit"}
    for k in order:
        if k not in e:
            continue
        v = e[k]
        if k == "path":
            lines.append(f"    path: {v if v else 'null'}")
        elif k in plain and v is not None:
            lines.append(f"    {k}: {v}")
        else:
            lines.append(f"    {k}: {yaml_scalar(v)}")
    notes = (e.get("notes") or "").strip()
    if notes:
        lines.append("    notes: >")
        words, line = notes.split(), "     "
        for w in words:
            if len(line) + 1 + len(w) > 78:
                lines.append(line)
                line = "     "
            line += " " + w
        lines.append(line)
    return "\n".join(lines) + "\n"


def supersede(manifest_text: str, rid: str):
    """Flip `status:` to superseded inside entry `rid`; text-level to keep comments."""
    m = re.search(rf"^  - id: {re.escape(rid)}\s*\n(.*?)(?=^  - id: |\Z)", manifest_text, re.M | re.S)
    if not m:
        return manifest_text, False
    block = m.group(0)
    new_block, n = re.subn(r"^(    status: )\S+", r"\1superseded", block, count=1, flags=re.M)
    return manifest_text[:m.start()] + new_block + manifest_text[m.end():], n == 1


def submissions(repo_root: str):
    inbox = os.path.join(repo_root, INBOX)
    if not os.path.isdir(inbox):
        return []
    names = sorted(os.listdir(inbox))
    out = []
    for n in names:
        if n in INBOX_KEEP or n.startswith("."):
            continue
        if n.endswith((".yaml", ".yml")):
            stem = n.rsplit(".", 1)[0]
            if any(o != n and (o == stem or o.rsplit(".", 1)[0] == stem) for o in names):
                continue  # sidecar of another submission
            # A sidecar on its own describes a linked-only resource (no file).
        out.append(n)
    return out


def load_sidecar(inbox: str, name: str):
    stem = name if os.path.isdir(os.path.join(inbox, name)) else name.rsplit(".", 1)[0]
    for cand in (f"{name}.yaml", f"{stem}.yaml", f"{stem}.yml"):
        p = os.path.join(inbox, cand)
        if os.path.isfile(p) and cand != name:
            with open(p, "r", encoding="utf-8") as f:
                return p, yaml.safe_load(f) or {}
    return None, {}


def process(repo_root: str, dry_run: bool):
    inbox = os.path.join(repo_root, INBOX)
    manifest_path = os.path.join(repo_root, MANIFEST)
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_text = f.read()
    existing = {r["id"]: r for r in (yaml.safe_load(manifest_text) or {}).get("resources", [])}

    report, held, done = [], 0, 0
    for name in submissions(repo_root):
        src = os.path.join(inbox, name)
        is_sidecar_only = name.endswith((".yaml", ".yml"))
        if is_sidecar_only:
            sidecar_path, meta = src, yaml.safe_load(open(src, encoding="utf-8")) or {}
        else:
            sidecar_path, meta = load_sidecar(inbox, name)

        problems = []
        status = meta.get("status", "linked" if is_sidecar_only else "current")
        initiative = meta.get("initiative")
        title = meta.get("title") or (None if is_sidecar_only else pdf_title(src))
        version = str(meta.get("version") or guess_version(name) or "")
        rid = meta.get("id") or slug(os.path.splitext(name)[0])
        source_url, source_repo = meta.get("source_url"), meta.get("source_repo")

        if not initiative:
            problems.append("sidecar needs `initiative:` (the corpus/ subfolder, e.g. `mcp-security`)")
        elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(initiative)):
            problems.append(f"`initiative: {initiative}` must be a lowercase folder name")
        if not title:
            problems.append("sidecar needs `title:` (no title in PDF metadata)")
        if not version:
            problems.append("sidecar needs `version:` (none found in the file name)")
        if not source_url and not source_repo:
            problems.append("sidecar needs `source_url:` or `source_repo:`")
        if rid in existing:
            problems.append(f"id `{rid}` already exists in MANIFEST.yaml -- set a different `id:`")
        sup = meta.get("supersedes")
        if sup and sup not in existing:
            problems.append(f"`supersedes: {sup}` is not an id in MANIFEST.yaml")
        if status not in ("current", "draft", "linked"):
            problems.append(f"`status: {status}` must be current, draft or linked")

        detected = {} if is_sidecar_only else detect_licenses(src)
        claimed = meta.get("license")
        license_ = None
        lic_note = ", ".join(f"{k} ({v})" for k, v in detected.items()) or "none found"
        if status == "linked":
            license_ = claimed or "UNCONFIRMED"
        elif claimed and detected and claimed not in detected:
            problems.append(f"sidecar says `license: {claimed}` but the document states {lic_note}")
        elif len(detected) > 1 and not claimed:
            problems.append(f"multiple licenses stated ({lic_note}) -- set `license:` in the sidecar")
        else:
            license_ = claimed or (next(iter(detected)) if detected else None)
            if not license_:
                problems.append("no explicit license statement found -- confirm it with the "
                                "initiative lead, or set `status: linked` to catalog it without vendoring")
            elif license_ not in VENDORABLE:
                problems.append(f"`{license_}` isn't on the auto-vendor list ({', '.join(sorted(VENDORABLE))}) "
                                "-- needs a maintainer decision, or set `status: linked`")
            elif not detected:
                problems.append(f"`license: {license_}` is claimed but no license statement was found in "
                                "the document -- vendoring needs an explicit statement; use `status: linked`")

        folder = meta.get("folder")
        dest_rel = None
        if status != "linked" and initiative:
            dest_rel = "/".join(p for p in ("corpus", initiative, folder, name) if p)
            if os.path.isdir(src):
                dest_rel += "/"
            if os.path.exists(os.path.join(repo_root, dest_rel)):
                problems.append(f"`{dest_rel}` already exists")

        entry = {
            "id": rid, "title": title, "initiative": initiative, "version": version,
            "status": status, "format": "pdf" if is_sidecar_only and status == "linked" else
            (meta.get("format") or (None if is_sidecar_only else guess_format(src))),
            "path": dest_rel, "license": license_,
        }
        for k in ("source_repo", "source_path", "source_url", "vendored_commit"):
            if meta.get(k):
                entry[k] = meta[k]
        if status != "linked":
            entry["vendored_date"] = today()
        entry["published"] = str(meta["published"]) if meta.get("published") else None
        notes = (meta.get("notes") or "").strip()
        if status == "linked" and license_ == "UNCONFIRMED":
            notes = (notes + " " if notes else "") + ("License not confirmed from the document text. "
                                                       "Do NOT vendor until confirmed with the initiative lead.")
        if sup:
            notes = (notes + " " if notes else "") + f"Supersedes {sup}."
        entry["notes"] = notes

        report.append(f"### `{name}`\n")
        report.append(f"- License detected: {lic_note}")
        if problems:
            held += 1
            report.append("- **Held in inbox/** -- fix and push again:")
            report += [f"  - {p}" for p in problems]
            report.append("")
            continue

        report.append(f"- Action: {'catalog as linked (file removed)' if status == 'linked' else 'move to `' + dest_rel + '`'}")
        if sup:
            report.append(f"- Marks `{sup}` as superseded")
        report.append("\n```yaml\n" + render_entry(entry) + "```\n")
        done += 1
        if dry_run:
            continue

        if status != "linked":
            dest_abs = os.path.join(repo_root, dest_rel)
            os.makedirs(os.path.dirname(dest_abs.rstrip("/")), exist_ok=True)
            shutil.move(src, dest_abs.rstrip("/"))
        elif not is_sidecar_only:
            (shutil.rmtree if os.path.isdir(src) else os.remove)(src)
        if sidecar_path and os.path.exists(sidecar_path):
            os.remove(sidecar_path)
        if sup:
            manifest_text, _ = supersede(manifest_text, sup)
        manifest_text = manifest_text.rstrip("\n") + "\n\n" + render_entry(entry)
        existing[rid] = entry

    if not dry_run and done:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(manifest_text)

    head = f"## Inbox processing{' (dry run)' if dry_run else ''}\n\n{done} processed, {held} held.\n\n"
    if not report:
        head = "## Inbox processing\n\nNothing in inbox/.\n"
    return head + "\n".join(report), held


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", help="also write the markdown report to this file")
    args = ap.parse_args()

    report, held = process(os.path.abspath(args.repo_root), args.dry_run)
    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
    sys.exit(1 if held else 0)


if __name__ == "__main__":
    main()
