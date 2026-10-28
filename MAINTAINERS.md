# Maintainer notes

Open setup tasks and decisions that need a maintainer. Remove an item once it's
done.

## 1. `CORPUS_BOT_TOKEN` secret

**Status:** not set.

**Why it's needed:** `process-inbox.yaml` commits the processed submission back
to the PR branch. Commits pushed with the default `GITHUB_TOKEN` don't trigger
other workflows, so without this secret every inbox PR shows:

- a failed **Validate corpus** check on the submission commit (expected:
  `inbox/` isn't empty yet), and
- an **action required** / missing check on the bot's processed commit,

until someone pushes again. With the secret set, the bot's push triggers
**Validate corpus** and the PR goes green on its own. The workflow already uses
`secrets.CORPUS_BOT_TOKEN` when it exists, falling back to `github.token`.

Fork PRs never receive repository secrets; they get a dry-run report only, so
they're unaffected either way.

### Option A: fine-grained personal access token (no code change)

1. GitHub avatar → **Settings** → **Developer settings** → **Personal access
   tokens** → **Fine-grained tokens** → **Generate new token**.
2. Settings:
   - **Resource owner:** `GenAI-Security-Project` (an org owner may need to
     approve it, depending on org policy).
   - **Expiration:** the longest the org allows. Set a renewal reminder.
   - **Repository access:** Only select repositories → `GenAI-Security-Corpus`.
   - **Permissions:** Repository → **Contents: Read and write** (Metadata:
     read-only is added automatically).
3. Copy the token (shown once) and add it as a secret (see below).

Trade-offs: tied to one person's account. Bot pushes show that person as the
pusher. If the token expires or the person leaves, inbox processing still
works but the follow-up check stalls again.

### Option B: GitHub App (better long-term)

1. Org **Settings** → **Developer settings** → **GitHub Apps** → **New GitHub
   App**. Permissions: Repository → **Contents: Read and write**. Webhook off.
2. Install it on `GenAI-Security-Corpus` only.
3. Store the App ID and a generated private key as two repository secrets
   (e.g. `CORPUS_BOT_APP_ID`, `CORPUS_BOT_PRIVATE_KEY`).
4. Change `process-inbox.yaml` to mint a short-lived token per run with
   `actions/create-github-app-token` and pass it to `actions/checkout`
   instead of `secrets.CORPUS_BOT_TOKEN`.

Trade-offs: not tied to a person, no expiry to track, commits attributed to
the app. Needs the small workflow change in step 4.

**Recommendation:** start with A; move to B if the project wants this
independent of any individual.

### Adding the secret (Option A)

Repo **Settings** → **Secrets and variables** → **Actions** → **New
repository secret** → name `CORPUS_BOT_TOKEN`, value = the token.

## 2. Pending corpus updates

- **Securing Agentic Applications v2.0** (`securing-agentic-applications-guide-2.0`)
  is in as `status: draft`, from the external-review copy. On publication: set
  it to `current`, mark `securing-agentic-applications-guide-1.0` as
  `superseded`, replace `source_url` with the v2.0 resource page, and replace
  the PDF if the published file differs.
- **LLM Exploit Generation Phase 2** (`llm-exploit-generation-phase2-1.0`) is
  listed as version `1.0` (from the cover), but its resource page URL is
  `.../llm-exploit-generation-guide-2-0/`. Confirm which version number to use.
- **LLM Exploit Generation Phase 1** (`llm-exploit-generation-1.0`) and the
  other `linked` entries stay link-only until their licenses are confirmed
  with the initiative leads.

## 3. MCP server usage monitoring (deferred)

Applies to
[GenAI-Security-Advisor-MCP](https://github.com/GenAI-Security-Project/GenAI-Security-Advisor-MCP),
recorded here so the decision isn't lost. Goal: see where traffic comes from
and how the server is used over time, to monitor and tune performance.

**What exists today:** `wrangler.jsonc` enables Cloudflare Workers
observability, so the Cloudflare dashboard (Workers & Pages →
`genai-security-advisor-mcp` → Metrics / Observability) shows request volume,
errors, and timing over time. The code itself logs nothing: no tool names
(every call is `POST /mcp`), no client app, no cache hit/miss or GitHub fetch
timing, and tool errors are returned inside 200 responses so they look like
successes. Logs are retained for only a few days.

**Options:**

1. **Structured log line per call** (easiest): tool, client app/version (from
   the MCP `initialize` handshake), country, Cloudflare colo, ASN, status,
   duration, GitHub fetch time, cache hit, errors. No IPs. Queried and charted
   in the Worker's Observability tab; access limited to Cloudflare account
   members. No bindings or secrets. Short retention.
2. **Add Workers Analytics Engine** for ~3 months of history. Same fields as
   data points; one binding in `wrangler.jsonc` (changes the server's current
   "no bindings" design). View with Grafana via a read-only Cloudflare API
   token, or ad-hoc SQL.
3. **Token-protected `/stats` endpoint + custom page.** Possible, but adds a
   query endpoint, a stored API token, and a shared secret for little gain
   over 1 + 2.

**Visibility:** maintainers only to start. A public view is possible later on
top of the same Analytics Engine data (aggregates only), but per-ASN/client
breakdowns can identify organizations and a public endpoint adds abuse and
cost surface, so decide what to publish once real data exists.

**Proposed:** options 1 + 2 in one PR (Analytics Engine writes optional, so
the server runs unchanged without the binding), maintainer-only, with sample
SQL queries. The MCP repo has no deploy workflow, so someone with Cloudflare
access runs `npm run deploy` afterwards.
