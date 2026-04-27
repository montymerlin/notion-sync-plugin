---
name: sync
description: >
  Bidirectional sync between a Notion database and local markdown files. Use when the
  user says "sync", "notion sync", "pull from notion", "push to notion", "check notion
  for updates", or wants to synchronise their local markdown files with a Notion database.
  Requires the Notion MCP and a configured .notion-sync/ directory (run /notion-setup first).
---

# Bidirectional Notion Sync

Sync local markdown files with a Notion database. Detects changes in both directions, shows a unified plan, resolves conflicts with user input, and executes pulls and pushes.

**Before using this skill**, read `references/sync-engine.md` for the detailed sync mechanics and `references/gotchas.md` for known issues and workarounds. These references contain critical operational knowledge that prevents data loss.

## Step 0: Check configuration

Look for `.notion-sync/config.json` in the current working directory.

- If it exists: load it and proceed. Read `config.json` for the data source ID, sync folder, and property mappings.
- If it doesn't exist: tell the user to run `/notion-setup` first to configure the sync, then stop.

Load the manifest from `.notion-sync/manifest.json`.

## Step 1: Git safety check

Run `git status` to check for uncommitted changes in the sync folder or `.notion-sync/`.

If dirty: ask the user to commit first. Use the `/commit` skill (git-cowork plugin). Only proceed when the working tree is clean — this ensures you can cleanly diff changes after sync.

## Step 2: Build inventories

**Local inventory:** Run the diff script to generate a complete change picture — it checks both property changes (frontmatter fields vs. manifest snapshot) and content changes (hash comparison), and ensures the link registry is fresh before running:

```bash
python scripts/manifest.py diff --manifest-path .notion-sync/manifest.json
```

Output includes `push_target` per changed file (`properties_only`, `content_only`, `both`, `none`), `property_diff` showing which fields changed, and `content_changed` flag. No separate property check is needed — the diff command handles it.

**Notion inventory:** For exhaustive page discovery, fetch the data source schema which returns all pages:

```
notion-fetch(id="collection://<data_source_id>")
```

This returns every page in the database — no search needed. Use this for full syncs and initial setup. For quick syncs where you only need to check specific pages, targeted `notion-fetch` calls by page ID are more efficient.

**Fallback (if database query is slow or unavailable):** Run 3-4 diverse semantic search queries via `notion-search`. Expect ~70-90% coverage per round. Pages in the manifest but not found in search are NOT considered deleted.

For each Notion page: compare its `last_edited_time` to the manifest's `last_synced` timestamp. Add a 60-second buffer (Notion rounds to nearest minute). If Notion is newer, the page has remote changes.

## Step 3: Classify and plan

Classify every page:

| Local changed? | Notion changed? | Action |
|---|---|---|
| No | No | Skip (unchanged) |
| No | Yes | Pull from Notion |
| Yes | No | Push to Notion |
| Yes | Yes | Conflict — ask user |
| — | New in Notion | Create local file |
| — | Deleted in Notion | Ask user |

Present the unified sync plan:

```
Notion Sync Plan:
  Properties-only push:    N pages  (frontmatter changed, body unchanged — fast)
  Full push (both):        N pages  (content + properties)
  Content-only push:       N pages
  Pull from Notion:        N pages
  Conflicts:               N pages (need resolution)
  New in Notion:           N pages
  Unchanged:               N pages (skipping)
```

List specific files in each category. **Wait for user confirmation before executing.**

## Step 4: Resolve conflicts

For each conflicted page:

1. Fetch the Notion version via `notion-fetch(id=page_id)`
2. Read the local file
3. Show the user a summary of both versions — what changed on each side
4. User chooses: keep local (push), keep Notion (pull), or skip
5. Execute their choice

**Never auto-resolve conflicts.** Always ask.

## Step 5: Execute pulls (Notion → local)

For each page to pull, follow the pull procedure in `references/sync-engine.md`. In summary:

1. Fetch page via `notion-fetch(id=page_id)`
2. Parse properties from `<properties>` section using the property map in config.json
3. Extract content from `<content>` section
4. Run post-processing to clean Notion formatting artifacts (toggles, empty blocks, span colors, tab indentation). See `references/gotchas.md` for the cleaning rules.
5. **Content loss check**: if local file has >20% more words than the Notion version, flag for user review before overwriting
6. Convert Notion page URLs to local markdown filenames using the link registry: `python scripts/link_registry.py convert-links --direction pull --content-file <pulled-content>`
7. Build the file: YAML frontmatter + cleaned content body
8. Write to the sync folder
9. Capture the properties snapshot: for each property in the pull response, store its value in `manifest["pages"][page_id]["properties"]` keyed by `yaml_key`. This baseline is used by future diffs to detect property-only changes.
10. Update the manifest entry (timestamp, content hash)

## Step 6: Execute pushes (local → Notion)

For each page to push, use `push_target` from the diff output to decide which script calls to make.

**`notion-update-page` with `replace_content` is never called directly.** All content writes go through the direct Blocks API. All property writes go through MCP.

**Properties only (`push_target: "properties_only"`):**

```bash
python scripts/push_markdown.py push-properties \
  --file <local_path> --config-path .notion-sync/config.json
```

Take the JSON output and call:
```
notion-update-page(page_id=<page_id>, command="update_properties", properties=<output.properties>)
```

Then update the manifest properties snapshot.

**Content only (`push_target: "content_only"`):**

```bash
# 1. Prepare staging file (strip frontmatter, convert links, compute hash)
python scripts/push_markdown.py prepare \
  --file <local_path> \
  --output .notion-sync/push-staging/<slug>.md

# 2. Push content via direct Blocks API
python scripts/push_markdown.py push-content \
  --page-id <notion_id> \
  --file .notion-sync/push-staging/<slug>.md
```

Then update manifest `content_hash` and `last_synced`.

**Both content and properties (`push_target: "both"`):**

```bash
# 1. Prepare
python scripts/push_markdown.py prepare \
  --file <local_path> --output .notion-sync/push-staging/<slug>.md

# 2. Push content
python scripts/push_markdown.py push-content \
  --page-id <notion_id> --file .notion-sync/push-staging/<slug>.md

# 3. Push properties
python scripts/push_markdown.py push-properties \
  --file <local_path> --config-path .notion-sync/config.json
```

Followed by MCP call for properties (same as properties-only above), then manifest update for both hash and properties.

If push fails due to child pages, see `references/gotchas.md`.

## Step 7: Handle new Notion pages

For pages found in Notion but not in the manifest:

1. Generate a kebab-case filename from the title (use slug overrides from config if applicable)
2. If config has multiple `sync_folders`, ask the user which folder to place the new file in
3. Pull content and properties (same as Step 5)
4. Write the new file to the chosen folder
5. Add to manifest

## Step 8: Summary and commit

1. Show the user a summary of all changes made
2. Update `last_full_sync` timestamp in the manifest
3. Rebuild the link registry to reflect any new or changed mappings:
   ```bash
   python scripts/link_registry.py build --manifest-path .notion-sync/manifest.json
   ```
4. Ask the user to review changes before committing
5. Use the `/commit` skill — never auto-commit
6. If the project uses an auto-generated index (like INDEX.md), remind the user to regenerate it

## Important notes

- **Always read `references/sync-engine.md` and `references/gotchas.md`** before running a sync. They contain critical operational knowledge built from real incidents.
- **Always use `push_markdown.py` for all content writes — never `notion-update-page` with `replace_content`.** The MCP content path passes text through LLM token generation and is unreliable for documents over a few thousand words. See `references/gotchas.md`.
- **Token auto-loaded from `.notion-sync/.env` or `.env`.** Run `/notion-setup` if content pushes fail with token errors.
- **Always load the manifest fresh** from `.notion-sync/manifest.json` — never cache or hardcode page IDs.
- **Multi-select properties** require JSON array strings on push — plain strings silently drop values.
- **Use helper scripts for link conversion and push preparation** — `link_registry.py` and `push_markdown.py` eliminate ad-hoc scripting and reduce errors.
- **Content hash timing matters** — always compute the hash *after* link conversion, since converted content is what Notion stores. The `push_markdown.py` script handles this correctly.
