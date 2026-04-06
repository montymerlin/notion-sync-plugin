---
name: notion-setup
description: >
  Set up bidirectional Notion sync in the current folder. Use when the user says
  "set up notion sync", "connect notion", "configure notion sync", "link this folder
  to notion", or wants to establish a new sync between a Notion database and local
  markdown files. Also triggers when the notion-sync skill detects no existing config.
---

# Notion Sync Setup

Guide the user through connecting a Notion database to a local folder for bidirectional markdown sync. Creates the config and manifest files needed by the `/notion-sync` skill.

## Prerequisites

The Notion MCP must be available. Check that `notion-search` is in the tool list. If not, tell the user they need to connect the Notion MCP server in their Claude Desktop settings or Cowork plugin configuration.

## Step 1: Identify the database

Ask the user which Notion database they want to sync. They can provide:

- A database URL (extract the ID from it)
- A database name (use `notion-search` to find it)
- A data source ID directly

Use `notion-search` with relevant keywords to locate the database. Confirm with the user that the right database was found by showing its title and page count.

Record the **data source ID** (the 36-character UUID with dashes, or 32-character hex without).

## Step 2: Identify the local folder

Ask the user which local folder should sync with this database. Common patterns:

- `research/` — a research knowledge base
- `docs/` — documentation
- `notes/` — personal notes
- A custom folder name

If the folder doesn't exist, create it.

## Step 3: Map Notion properties to YAML frontmatter

Fetch a sample page from the database using `notion-fetch` to see what properties exist. Present the properties to the user and propose a mapping:

**Always mapped (required):**
- Page title → `title` (YAML field)
- Page ID → `notion_id` (YAML field, 32-char hex)
- Created time → `created`
- Last edited time → `last_edited`
- Last synced → `last_synced` (set by sync, not a Notion property)

**Auto-detected mappings** (propose these if the Notion properties exist):
- `Status` or `Draft` → `draft`
- `Tags` or `Category` → `category` (multi-select)
- `Topics` → `topics` (multi-select)
- `Summary` or `Short Summary` → `short_summary`

**User-defined mappings:** For any remaining properties the user wants to sync, ask what YAML field name to use and note the property type (text, select, multi-select, date, checkbox, number).

Present the proposed mapping and let the user adjust before confirming.

## Step 4: Create the config

Create a `.notion-sync/` directory in the current working directory (the repo root, not inside the sync folder). Write the configuration:

**`.notion-sync/config.json`:**
```json
{
  "data_source_id": "<database-uuid>",
  "sync_folder": "<folder-name>/",
  "property_map": {
    "Name": { "yaml_key": "title", "type": "title" },
    "Draft": { "yaml_key": "draft", "type": "select" },
    "Category": { "yaml_key": "category", "type": "multi_select" },
    "Topics": { "yaml_key": "topics", "type": "multi_select" },
    "Short Summary": { "yaml_key": "short_summary", "type": "rich_text" },
    "Created": { "yaml_key": "created", "type": "created_time" },
    "Last edited time": { "yaml_key": "last_edited", "type": "last_edited_time" }
  },
  "slug_overrides": {}
}
```

The `property_map` keys are exact Notion property names. The `type` field ensures correct serialisation on push (multi-select requires JSON array strings).

The `slug_overrides` object allows custom filename mappings for titles that don't slugify cleanly (e.g. `"d/acc": "d-acc"`).

**`.notion-sync/manifest.json`:**
```json
{
  "data_source_id": "<database-uuid>",
  "last_full_sync": null,
  "pages": {}
}
```

## Step 5: Initial population

Run an initial scan of the Notion database:

1. Use `notion-search` with 3-4 diverse queries to discover pages (single query returns max 25 results — run multiple to cover the database)
2. Deduplicate results by page ID
3. For each page found, add an entry to the manifest with title and Notion edit timestamp
4. Show the user: "Found N pages in the database. Ready to run first sync?"

Do NOT pull content yet — that's the job of `/notion-sync`. The setup just creates the config and manifest infrastructure.

## Step 6: Confirm and advise

Tell the user:

- The sync is configured. Run `/notion-sync` to perform the first bidirectional sync.
- Add `.notion-sync/manifest.json` to `.gitignore` if sync state (timestamps) should stay personal. Keep `config.json` tracked if the mapping should be shared with collaborators.
- The Notion Sync MCP connector must be available for the sync skill to work.

## Files created

```
.notion-sync/
├── config.json      # Database ID, folder, property mappings (shareable)
├── manifest.json    # Page tracking, timestamps, content hashes (personal state)
```
