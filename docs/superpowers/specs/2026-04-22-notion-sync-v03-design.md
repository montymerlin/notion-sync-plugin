# notion-sync v0.3 — Design Spec

**Date:** 2026-04-22
**Status:** Approved — ready for implementation
**Version target:** v0.3.0
**Replaces:** ad-hoc workaround scripts in bridging-worlds `.scripts/`

---

## Context

The first serious real-world sync session (Bridging Worlds research commons, 47 markdown files, Notion "Knowledge & Research" database) surfaced three layers of problems in v0.2:

1. **Configuration drift** — frontmatter field names, stage emoji values, and Notion property names had diverged between local files, config, and the database schema. Fixable but fiddly.
2. **Script bugs** — `link_registry.py` iterated a dict as a list; `push_markdown.py` expected registry values in a format `link_registry.py` never wrote; unresolved links rendered as HTML comments in Notion.
3. **Fundamental architecture flaw** — pushing content via MCP passes document text through LLM token generation. For the EthicHub document (85K chars, ~300 blocks), this produced AI-regenerated prose instead of the source content. A direct Blocks API workaround script was written in the consumer repo as a patch.

This spec resolves all three layers in one coherent redesign. The "scripts handle mechanics, skills handle orchestration" design principle is preserved throughout.

---

## Goals

- Eliminate content fabrication on push — completely and by design, not by workaround
- Make property-only changes fast and low-risk (no content touched; properties use MCP, no token required)
- Fix both script bugs so the tools actually work
- Make the Notion integration token a first-class configuration requirement
- Store enough state in the manifest to power targeted push operations
- Absorb the bridging-worlds workaround script into the plugin

## Non-goals (this version)

- Multi-operator / shared `config.json` — single-operator only (see Roadmap)
- Image uploads — Notion API limitation at most plan tiers (documented constraint, callout placeholders stay)
- Script test suite — Roadmap item
- Webhook-based change detection — Roadmap item
- Per-file sync opt-out (`sync_enabled: false`) — Roadmap item

---

## Architecture Overview

### What stays the same

The core model: **scripts handle deterministic mechanics, skills guide the agent through judgment calls.** Scripts are stdlib-only Python, importable as libraries, JSON output. Skills are SKILL.md files that orchestrate the agent through the workflow — conflict resolution, user confirmation, folder selection remain agent-driven.

The MCP read path is retained: `notion-fetch` for pulling pages and exhaustive database discovery, `notion-search` as fallback. These are reliable and don't pass content through token generation.

`build_markdown.py` is untouched — the pull path has no fabrication problem.

### What changes

**The push path moves entirely off MCP.** `notion-update-page` with `replace_content` is never called for content in v0.3. All writes go through `push_markdown.py` subcommands that call the Notion Blocks API directly via an integration token.

**The manifest gains property snapshots.** Each page entry stores the last-synced value of every tracked property alongside the content hash. This enables the diff to say "only properties changed" and route to a fast, targeted push.

Three scripts change:
- `link_registry.py` — two bug fixes
- `push_markdown.py` — redesigned as a unified push pipeline; absorbs direct API logic
- `manifest.py` — v2 format with property snapshots and enriched diff output

Two skills change:
- `notion-setup` — gains token setup step
- `notion-sync` — step 2 simplified, step 6 entirely script-driven

---

## Manifest v2

### Schema

```json
{
  "version": 2,
  "data_source_id": "<database-uuid>",
  "last_full_sync": "2026-04-22T10:00:00.000Z",
  "pages": {
    "<32-char-hex-page-id>": {
      "local_file": "research/ethichub.md",
      "title": "EthicHub",
      "last_notion_edit": "2026-03-24T13:57:46.206Z",
      "last_synced": "2026-03-24T14:00:00.000Z",
      "content_hash": "sha256:a1b2c3d4e5f6g7h8",
      "properties": {
        "research_stage": "🪴 Grown",
        "topics": ["ReFi", "Web3"],
        "system_change": "Reimagination",
        "draft": false
      }
    }
  }
}
```

The `properties` object stores the last-synced value of each mapped property, keyed by the `yaml_key` from `config.json` (not the Notion property name). This is what the local file's frontmatter is compared against during diff.

### Migration from v1

On load, `manifest.py` detects a missing or `version: 1` manifest and auto-migrates:

1. Adds `"version": 2` at the top level
2. Adds `"properties": {}` to each page entry
3. Writes the migrated file back to disk

Non-destructive — all content hashes and timestamps are preserved. The first sync after migration treats all properties as unknown (empty dict), so they are re-captured from local frontmatter and stored as the new baseline. No false "changed" detections on first run.

### Diff output

`manifest.py diff` produces structured output per changed file:

```json
{
  "local_changed": [
    {
      "page_id": "abc123...",
      "local_file": "research/ethichub.md",
      "push_target": "properties_only",
      "property_diff": {
        "research_stage": {"was": "🌱 Seedling", "now": "🪴 Grown"}
      },
      "content_changed": false
    },
    {
      "page_id": "def456...",
      "local_file": "research/kwaxala.md",
      "push_target": "both",
      "property_diff": {},
      "content_changed": true
    }
  ],
  "notion_changed": [...],
  "conflicts": [...],
  "new_local": [...],
  "unchanged": [...]
}
```

`push_target` values: `"properties_only"`, `"content_only"`, `"both"`, `"none"`.

### Registry freshness check

Before running the diff, `manifest.py diff` verifies that `.notion-sync/link-registry.json` exists and has a file modification time newer than `.notion-sync/manifest.json`. If stale or missing, it runs `link_registry.py build` automatically. This enforces the two-pass pattern: registry always current → diff using registry. Validated by NotionRepoSync's design, which uses an explicit two-phase link resolution: phase 1 = reconcile all pages and build path-to-ID index; phase 2 = resolve cross-document links using that index.

---

## Script Changes

### `link_registry.py`

**Bug 1 — dict iteration (line ~101):**

```python
# v0.2 (broken): iterates dict keys as if they were list entries
entries = manifest.get("pages", [])
for entry in entries:
    local_file = entry.get("local_file")   # AttributeError: 'str' has no .get()
    page_id = entry.get("page_id")

# v0.3 (fixed): iterate dict items
entries = manifest.get("pages", {})
for page_id, entry in entries.items():
    local_file = entry.get("local_file")
    # page_id comes from the dict key
```

**Bug 2 — unresolved link rendering:**

```python
# v0.2 (broken): renders as visible HTML comment in Notion
return f"[{text}]({file_path}) <!-- unresolved: {file_path} -->"

# v0.3 (fixed): per sync-engine.md spec
return f"{text} *(local file)*"
```

No other changes — `LinkRegistry` is already a clean importable class.

### `push_markdown.py`

**Format mismatch fix:** remove the duplicate `load_link_registry` and `convert_links` functions. Import `LinkRegistry` from `link_registry.py` and call `registry.convert_links(body, "push")` directly. One source of truth for registry format and link conversion logic.

**Token loading:** on startup, auto-load `.notion-sync/.env` then `.env` (cwd root) then `NOTION_TOKEN` env var. Token is required only for `push-content`. If called without a token, exit with:
```
Error: NOTION_TOKEN not found.
Add it to .notion-sync/.env — run /notion-setup for instructions.
```

**New subcommands:**

```
prepare          existing — strip frontmatter, convert links, compute hash, write staging file
push-content     NEW — read staging file → markdown_to_blocks() → Notion Blocks API (token required)
push-properties  NEW — calls notion-update-page via MCP (no token required; structured data, no fabrication risk)
batch            existing — find changed files, prepare all to staging dir
```

**`push-content` implementation:**

Absorbed from `notion_push_content.py` (bridging-worlds workaround script, battle-tested on EthicHub 300-block push):

- `markdown_to_blocks(markdown)` — converts markdown to Notion block objects. Handles: h1/h2/h3, paragraphs (with 2000-char splitting), bullet lists, numbered lists, blockquotes, code blocks (with 2000-char truncation), tables (correct `cells` format: `[[rich_text_obj, ...], ...]`), images (HTTPS URLs → image block; local paths → callout placeholder), dividers.
- `clear_page_blocks(page_id, token)` — deletes existing blocks before push; skips already-archived blocks gracefully (catches 400 "archived" errors).
- `push_blocks(page_id, blocks, token)` — pushes in batches of 100 via `PATCH /v1/blocks/{page_id}/children`.
- `--dry-run` flag — parses and counts blocks without making any API calls.

**`push-properties` implementation:**

- Reads YAML frontmatter from local file
- Maps each `yaml_key` to its Notion property name via `config.json`'s property map
- Serialises multi-select values as JSON array strings: `"[\"Value1\", \"Value2\"]"` (existing gotcha, now enforced in one place)
- Calls `notion-update-page(page_id, command="update_properties", properties={...})` via MCP
- No token required — property values are structured data from YAML parsing, not LLM-generated text, so the MCP path is safe here

**Page lock option:**

If `config.json` has `"lock_after_push": true`, after a successful `push-content` call, `push_markdown.py` fires `PATCH /v1/pages/{page_id}` with `{"locked": true}`. Signals "Git is source of truth, do not edit in Notion." Off by default. Sourced from Mk Notes' `lockPage` pattern.

### `manifest.py`

- `load()` — detect `version` field; auto-migrate v1→v2 if needed
- `save()` — always writes `"version": 2`
- `diff` command — two-step check per file:
  1. Parse local YAML frontmatter → compare each property to `manifest["pages"][page_id]["properties"]`
  2. Strip frontmatter → compute content hash → compare to `manifest["pages"][page_id]["content_hash"]`
  - Output: enriched JSON with `push_target`, `property_diff`, `content_changed` per entry
  - Registry freshness check before running
- `bootstrap` / `discover` — after writing new entries, initialise `"properties": {}` so migration is clean

---

## Auth & Token Management

**Single-operator. No shared secrets.**

The Notion integration token is required for `push-content` (direct Blocks API). Property-only pushes use MCP `update_properties` and do not require a token — so a repo without a token can still sync property changes. Token is stored in `.notion-sync/.env` (gitignored with the rest of `.notion-sync/`). The `.env` file format:

```
NOTION_TOKEN=ntn_your_token_here
```

**Setup flow** (notion-setup skill, new step):
1. Go to `notion.so/my-integrations` → New integration → Internal → copy the token
2. Open the target Notion database → `...` menu → Connections → connect your integration
3. Create `.notion-sync/.env` with `NOTION_TOKEN=ntn_...`
4. Verify token is readable: `python scripts/push_markdown.py push-content --dry-run` (no page ID needed in dry-run; confirms token loads correctly from `.env`)

**Multi-operator** is a future roadmap item. The constraint is Notion's paid-seat requirement for integration access, not a technical limitation. When that changes, the path is: track `config.json`, add `config.local.json` (gitignored) for per-operator token overrides.

---

## SKILL.md Workflow Changes

### notion-setup additions

New step after config creation: token setup (see Auth section above). Token verification via dry-run before the skill completes.

### notion-sync step changes

**Step 2 (Build inventories) — simplified:**

The manual "also check YAML property fields" note is removed — the property diff is now automatic inside `manifest.py diff`. Step 2 runs one command and gets a complete picture:

```bash
python scripts/manifest.py diff --manifest-path .notion-sync/manifest.json
```

**Step 3 (Classify and plan) — more granular:**

The sync plan now shows push type breakdown:

```
Notion Sync Plan:
  Properties-only push:    3 pages  (frontmatter changed, body unchanged)
  Full push (both):        2 pages  (content + properties)
  Content-only push:       1 page
  Pull from Notion:        2 pages
  Conflicts:               1 page (need resolution)
  Unchanged:              38 pages (skipping)
```

**Step 5 (Execute pulls) — manifest update:**

After writing a pulled file, the manifest entry update includes the `properties` snapshot captured from the `<properties>` section of the `notion-fetch` response, mapped through `config.json`.

**Step 6 (Execute pushes) — entirely script-driven:**

`notion-update-page` with `replace_content` is **never called**. For each file, based on `push_target` from the diff output:

*Properties only:*
```bash
python scripts/push_markdown.py push-properties \
  --page-id <notion_id> --file <local_path>
```

*Content only:*
```bash
python scripts/push_markdown.py prepare \
  --file <local_path> --output .notion-sync/push-staging/<slug>.md

python scripts/push_markdown.py push-content \
  --page-id <notion_id> --file .notion-sync/push-staging/<slug>.md
```

*Both (content + properties):*
```bash
# 1. Prepare staging file
python scripts/push_markdown.py prepare \
  --file <local_path> --output .notion-sync/push-staging/<slug>.md

# 2. Push content via direct API
python scripts/push_markdown.py push-content \
  --page-id <notion_id> --file .notion-sync/push-staging/<slug>.md

# 3. Push properties via MCP
python scripts/push_markdown.py push-properties \
  --page-id <notion_id> --file <local_path>
```

**Updated important notes:**

Added:
- "Always use `push_markdown.py` for all writes — never `notion-update-page` for content. The MCP content path passes text through LLM token generation and is unreliable for documents over a few thousand words."
- "Token is auto-loaded from `.notion-sync/.env` or `.env`. Run `/notion-setup` if missing."

Retained:
- "Never use subagents to push content" — still relevant; the fabrication risk exists in any workflow that passes content through an agent context.

---

## Reasoning Artifacts

### DECISIONS.md — two new entries to write before implementing

**Decision 007:** Direct API push + token as first-class config.
- Context: MCP content push causes silent fabrication on large documents (EthicHub incident).
- Decision: Token required for all writes; `push_markdown.py` calls Blocks API directly; MCP read-only.
- Alternatives considered: MCP-only with size limits (rejected — data integrity failure); token optional with fallback (rejected — complexity without benefit for single-operator).
- Ecosystem note: only `go-notion-md-sync` among reviewed tools achieves bidirectional sync, confirming the custom plugin is necessary.

**Decision 008:** Manifest v2 with property snapshots.
- Context: Binary diff (changed/unchanged) couldn't distinguish property changes from content changes; every changed file triggered a full content push.
- Decision: `properties` snapshot per manifest entry; `push_target` field enables targeted operations.
- Alternatives considered: separate property-hash (rejected — snapshot enables per-field diffs); manual property inspection in SKILL.md (rejected — too slow, too skippable).

### ROADMAP.md — four new items

Near-term ideas:
- **Per-file sync opt-out** — `sync_enabled: false` frontmatter flag. From go-notion-md-sync. `status: idea`
- **CDN image hosting** — auto-upload local images to configured public CDN on push. `status: idea`

Future / parked:
- **Multi-operator support** — tracked `config.json`, gitignored `config.local.json`. Blocked on Notion paid-seat requirement. `status: parked`

Existing items unchanged: Script test suite, Block-level sync, Webhook-based change detection, Conflict merge UI.

### CHANGELOG.md

Written after implementation. Narrative will cover: what the EthicHub session revealed, how v0.3 redesigns the push path, and what it means for reliability at scale.

---

## Alternatives Considered

Researched four tools as part of this design process:

**Mk Notes** (mk-notes.io) — TypeScript CLI, unidirectional (markdown → Notion only). No frontmatter-to-properties mapping, no link conversion. Has a `lockPage` option we adopted.

**NotionRepoSync** (github.com/sourcegraph/notionreposync) — Go tool by Sourcegraph, unidirectional. Explicit two-pass link resolution (build index → resolve links) validated and reinforced our link registry + registry-freshness-check approach.

**Notion GitHub Integration** (notion.com/integrations/github) — not a markdown sync tool. Surfaces GitHub activity (issues, PRs) inside Notion. Irrelevant to local file sync.

**go-notion-md-sync** (github.com/byvfx/go-notion-md-sync) — Go CLI, **bidirectional**. Only tool in the ecosystem with true two-way sync. Uses `notion_id` in frontmatter as the durable sync anchor (same as our approach). Has `sync_enabled: false` per-file opt-out flag (added to our roadmap). Confirms the custom plugin approach is sound.

**Conclusion:** No existing tool combines bidirectional sync, frontmatter-as-database-properties mapping, cross-reference link conversion, and agentic workflow integration. The custom plugin remains the right approach.

---

## Open Questions (resolved during brainstorming)

| Question | Decision |
|---|---|
| Token required or optional? | Required for content writes (`push-content`); property writes use MCP (no token); MCP retained for reads |
| Hybrid push (MCP for small, API for large)? | No — always API; size threshold adds complexity and failure modes |
| gitignore strategy for shared repos? | Single-operator now; multi-operator on roadmap |
| Evaluate alternatives before speccing? | Research done inline; confirmed custom approach is correct |
| Image uploads via MCP? | No MCP upload tool exists; Notion API file upload requires Business/Enterprise plan; callout placeholders stay |

---

## Implementation Scope

Files to change in `notion-sync-plugin/`:

| File | Change type |
|---|---|
| `scripts/link_registry.py` | Bug fix (2 fixes) |
| `scripts/push_markdown.py` | Redesign — absorb link_registry, add push-content + push-properties subcommands |
| `scripts/manifest.py` | Upgrade — v2 format, enriched diff output, registry freshness check |
| `skills/notion-setup/SKILL.md` | Add token setup step |
| `skills/notion-sync/SKILL.md` | Simplify step 2, replace step 6 push workflow |
| `skills/notion-sync/references/gotchas.md` | Document content fabrication problem for main-context MCP pushes (not just subagents) |
| `skills/notion-sync/references/sync-engine.md` | Update push procedure to reference new script subcommands |
| `DECISIONS.md` | Add Decision 007 and Decision 008 |
| `ROADMAP.md` | Add four new items |

Files to retire in bridging-worlds after v0.3 ships:
- `.scripts/notion_push_content.py` — functionality absorbed into `push_markdown.py`
