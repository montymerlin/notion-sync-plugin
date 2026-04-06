---
name: notion-sync
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

**Local inventory:** For each file in the sync folder, compute a content hash (SHA-256 of body, excluding YAML frontmatter, first 16 hex chars). Compare to the hash stored in the manifest. If different, the file has local changes.

Also check YAML property fields against the manifest — property-only changes (e.g. updating draft status) count as local changes even if the body hash is the same.

**Notion inventory:** Run 3-4 diverse semantic search queries via `notion-search` to discover pages:

```
query=" "                          # Returns ~25 recent/popular pages
query="<domain keyword 1>"         # e.g. "finance blockchain"
query="<domain keyword 2>"         # e.g. "community ecological"
query="<domain keyword 3>"         # e.g. "governance protocol"
```

Adapt keywords to the database's content domain. Deduplicate by page ID across queries. Expect to find ~70-90% of pages per sync — search is semantic, not exhaustive.

For each Notion page found: compare its `last_edited_time` to the manifest's `last_synced` timestamp. Add a 60-second buffer (Notion rounds to nearest minute). If Notion is newer, the page has remote changes.

Pages in the manifest but not found in search are NOT considered deleted — they just weren't surfaced. Skip them in quick syncs. For full syncs, use targeted `notion-fetch` calls to check.

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
Notion Sync Plan (bidirectional):
  Pull from Notion:  N pages
  Push to Notion:    N pages
  Conflicts:         N pages (need resolution)
  New in Notion:     N pages
  Unchanged:         N pages (skipping)
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
6. Convert Notion page URLs in links back to local markdown filenames using the manifest
7. Build the file: YAML frontmatter + cleaned content body
8. Write to the sync folder
9. Update the manifest entry (timestamp, content hash)

## Step 6: Execute pushes (local → Notion)

For each page to push, follow the push procedure in `references/sync-engine.md`. In summary:

1. Read local file, separate YAML frontmatter from body
2. Convert local markdown links to Notion page URLs using the manifest
3. Push content via `notion-update-page(page_id, command="replace_content", new_str=<body>)`
4. Push properties via `notion-update-page(page_id, command="update_properties", properties={...})`
   - Multi-select properties MUST be pushed as JSON array strings: `'["value1", "value2"]'`
5. Update manifest entry and local file's `last_synced` in frontmatter

If push fails due to child pages, tell the user and offer options (see `references/gotchas.md`).

## Step 7: Handle new Notion pages

For pages found in Notion but not in the manifest:

1. Generate a kebab-case filename from the title
2. Pull content and properties (same as Step 5)
3. Write the new file
4. Add to manifest

## Step 8: Summary and commit

1. Show the user a summary of all changes made
2. Update `last_full_sync` timestamp in the manifest
3. Ask the user to review changes before committing
4. Use the `/commit` skill — never auto-commit
5. If the project uses an auto-generated index (like INDEX.md), remind the user to regenerate it

## Important notes

- **Always read `references/sync-engine.md` and `references/gotchas.md`** before running a sync. They contain critical operational knowledge built from real incidents.
- **Never use subagents to push content to Notion** — this has caused silent content fabrication and broken links. See gotchas.
- **Always load the manifest fresh** from `.notion-sync/manifest.json` — never cache or hardcode page IDs.
- **Multi-select properties** require JSON array strings on push — plain strings silently drop values.
