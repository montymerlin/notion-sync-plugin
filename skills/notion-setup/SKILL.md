---
name: notion:setup
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

## Step 2: Identify the local folder(s)

Ask the user which local folder(s) should sync with this database. Multiple folders can sync to the same database. Common patterns:

- `research/` — a research knowledge base
- `report/` — report drafts
- `docs/` — documentation
- `notes/` — personal notes

If any folder doesn't exist, create it.

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
  "sync_folders": ["<folder-name>/"],
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

## Step 5: Set up your Notion integration token

The sync needs a Notion integration token to push content directly via the Blocks API (bypasses the AI generation path for large documents).

1. Go to `https://www.notion.so/my-integrations` → **New integration** → give it a name → **Internal** → copy the **Internal Integration Secret** (starts with `ntn_` or `secret_`)
2. In Notion, open your target database page → click `...` (top right) → **Connections** → find your integration → **Connect**
3. Create the token file:
   ```bash
   echo "NOTION_TOKEN=ntn_your_token_here" > .notion-sync/.env
   ```
4. Verify the token loads correctly (no API call is made):
   ```bash
   python scripts/push_markdown.py push-content --dry-run
   ```
   Expected output: `{"dry_run": true, "blocks": 0}` — confirms token loads and script is functional.

The `.notion-sync/.env` file is gitignored. Each operator creates their own.

## Step 6: Initial population

Discover all pages in the Notion database:

1. Fetch the data source to enumerate pages: `notion-fetch(id="collection://<data_source_id>")`
   - Fallback: Run `notion-search` with 3-4 diverse queries if the database query is unavailable
2. Deduplicate results by page ID
3. For each page found, add an entry to the manifest with title and Notion edit timestamp
4. Run the bootstrap script to match existing local files to manifest entries:
   ```bash
   python scripts/manifest.py bootstrap --folders <sync_folders> --manifest-path .notion-sync/manifest.json
   ```
5. Build the link registry:
   ```bash
   python scripts/link_registry.py build --manifest-path .notion-sync/manifest.json
   ```
6. Show the user: "Found N pages, matched M to local files. Ready to run first sync?"

Do NOT pull content yet — that's the job of `/notion-sync`. The setup creates the config, manifest, and link registry infrastructure.

## Step 7: Confirm and advise

Tell the user:

- The sync is configured. Run `/notion-sync` to perform the first bidirectional sync.
- Add the entire `.notion-sync/` directory to `.gitignore` — this covers your config, manifest, link registry, staging files, and integration token. All of these are personal operator state.
- The Notion Sync MCP connector must be available for the sync skill to work.

## Files created

```
.notion-sync/
├── config.json          # Database ID, folders, property mappings (shareable)
├── manifest.json        # Page tracking, timestamps, content hashes (personal state)
└── link-registry.json   # Bidirectional file↔page ID map (auto-generated, personal)
```
