# Sync Engine: Detailed Mechanics

Reference document for the bidirectional sync process. Read this before executing any sync.

## Content hashing

Change detection relies on SHA-256 hashes of file content:

- Hash the **body only** — strip YAML frontmatter before hashing
- Truncate to first 16 hex characters: `sha256:a1b2c3d4e5f6g7h8`
- Store in the manifest alongside each page entry
- On sync, recompute the hash and compare to stored value

```python
import hashlib

def content_hash(body: str) -> str:
    h = hashlib.sha256(body.strip().encode('utf-8')).hexdigest()[:16]
    return f"sha256:{h}"
```

Property changes are detected separately by comparing YAML frontmatter fields to the manifest.

## Manifest structure

```json
{
  "data_source_id": "<database-uuid>",
  "last_full_sync": "2026-04-02T14:50:39.000Z",
  "pages": {
    "<32-char-hex-page-id>": {
      "local_file": "research/page-slug.md",
      "title": "Page Title",
      "last_notion_edit": "2026-03-24T13:57:46.206Z",
      "last_synced": "2026-03-24T14:00:00.000Z",
      "content_hash": "sha256:a1b2c3d4e5f6g7h8"
    }
  }
}
```

## Timestamp handling

Notion's `last_edited_time` is rounded to the nearest minute. When comparing timestamps for change detection, add a 60-second buffer to avoid false negatives:

```python
from datetime import datetime, timedelta

notion_edited = datetime.fromisoformat(notion_timestamp)
last_synced = datetime.fromisoformat(manifest_entry['last_synced'])

# Notion is considered changed if edited more than 60s after last sync
notion_changed = notion_edited > (last_synced + timedelta(seconds=60))
```

## Pull procedure (Notion → local)

### 1. Fetch the page

```
notion-fetch(id=<page_id>)
```

Returns two sections: `<properties>` (JSON) and `<content>` (markdown).

### 2. Parse properties

Read the property map from `.notion-sync/config.json`. For each mapped property, extract the value from the Notion response:

- **title**: string
- **select**: string (the selected option name)
- **multi_select**: array of strings (option names)
- **rich_text**: string (plain text content)
- **date**: ISO timestamp
- **created_time**: ISO timestamp
- **last_edited_time**: ISO timestamp
- **checkbox**: boolean
- **number**: number

### 3. Clean content

Run post-processing to remove Notion formatting artifacts. See `gotchas.md` for the full cleaning ruleset:

```python
import re

def clean_notion_markdown(content):
    # Remove {toggle="true"} from headings
    content = re.sub(r'\s*\{toggle="true"\}\s*$', '', content, flags=re.MULTILINE)
    # Remove <empty-block/> lines
    content = re.sub(r'^\s*<empty-block/>\s*$\n?', '', content, flags=re.MULTILINE)
    # Strip <span color="..."> tags, keep inner text
    content = re.sub(r'<span color="[^"]*">(.*?)\s*</span>', r'\1', content)
    # Strip leading tabs (toggle-indent artifacts)
    content = re.sub(r'^\t', '', content, flags=re.MULTILINE)
    # Clean up triple+ blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()
```

### 4. Content loss prevention

Before overwriting a local file, check word counts:

```python
local_words = len(local_body.split())
notion_words = len(notion_body.split())

if local_words > 0:
    reduction = (local_words - notion_words) / local_words
    if reduction > 0.20:  # More than 20% content loss
        # FLAG: ask user to choose local, Notion, or skip
```

This catches cases where Notion content is shorter than local — which can happen if content was never pushed or was lost during editing.

### 5. Convert links

Convert Notion page URLs back to local markdown filenames:

- `[text](https://www.notion.so/<page-id>)` → `[text](<local-filename>.md)`
- Look up page IDs in the manifest (strip dashes from the URL ID before matching)
- Leave external URLs untouched
- Leave anchor links (`#section-name`) as-is

### 6. Build and write the file

Construct YAML frontmatter from the parsed properties, append the cleaned content body, and write to the sync folder. Use the helper scripts (`build_markdown.py`) if available, or construct manually:

```yaml
---
notion_id: "<32-char-hex>"
title: "Page Title"
draft: "In progress"
# ... other mapped properties
created: "2026-01-15T10:00:00.000Z"
last_edited: "2026-04-02T14:50:39.000Z"
last_synced: "2026-04-06T12:00:00.000Z"
---

# Page Title

Content body here...
```

### 7. Update manifest

Set `last_notion_edit`, `last_synced` (current time), and `content_hash` (hash of new body).

## Push procedure (local → Notion)

### 1. Read and parse the local file

Separate YAML frontmatter from body. The `notion_id` in frontmatter (or manifest) identifies the target page.

### 2. Convert links for Notion

- `[text](filename.md)` → `[text](https://www.notion.so/<page-id>)` (look up in manifest)
- `[text](../other-folder/file.md)` → `text *(local file)*` (non-synced files can't link in Notion)
- Anchor links (`#section-name`) — leave as-is (they render as blue text in Notion but don't break)
- External URLs — leave untouched

### 3. Push content

```
notion-update-page(
  page_id="<notion_id>",
  command="replace_content",
  new_str="<body without YAML frontmatter>"
)
```

Use `replace_content` for full replacement. This is safer than targeted `update_content` which requires exact string matching against Notion's internal format.

**If push fails due to child pages**: Notion refuses to replace content if it would delete child pages. Options:
1. Add `allow_deleting_content: true` (destructive — deletes child pages)
2. Use `update_content` for targeted changes only
3. Push properties only, skip content

### 4. Push properties

```
notion-update-page(
  page_id="<notion_id>",
  command="update_properties",
  properties={
    "Property Name": "<value>"
  }
)
```

**Critical**: Multi-select properties must be serialised as JSON array strings:
```json
{
  "Category": "[\"Value1\", \"Value2\"]",
  "Topics": "[\"Topic1\", \"Topic2\"]"
}
```

Plain strings silently drop all but one value.

### 5. Update manifest and frontmatter

- Manifest: set `content_hash`, `last_synced`, `last_notion_edit` to current time
- Local file: update `last_synced` in YAML frontmatter

## Filename generation

Titles are converted to kebab-case slugs for filenames:

1. Lowercase the title
2. Apply slug overrides from `config.json` (e.g. `"d/acc" → "d-acc"`)
3. Replace `/` with `-`, `&` with `and`
4. Strip quotes, parentheses, commas, colons, semicolons, periods, question marks, exclamation marks
5. Replace any remaining non-alphanumeric characters with `-`
6. Collapse multiple consecutive dashes
7. Strip leading/trailing dashes
8. Append `.md`

## Link registry

The link registry provides bidirectional mapping between local files and Notion page IDs, eliminating the need for ad-hoc slug matching or title-based lookups during link conversion.

### File format

```json
// .notion-sync/link-registry.json
{
  "by_file": {
    "research/kwaxala.md": "33ebf304370a81ffb1dafefd9c510128"
  },
  "by_page": {
    "33ebf304370a81ffb1dafefd9c510128": "research/kwaxala.md"
  }
}
```

### Rebuild protocol

After every sync operation (pull, push, or setup), rebuild the registry:

```bash
python scripts/link_registry.py build --manifest-path .notion-sync/manifest.json
```

This walks the manifest, extracts all pages with both `local_file` and page ID, and writes both lookup directions. The rebuild is idempotent — running it multiple times produces the same result.

## Push preparation pipeline

The full pipeline for preparing a local file for Notion push:

1. **Read** the local markdown file
2. **Strip** YAML frontmatter (everything between `---` markers)
3. **Convert links** using the link registry: `[text](file.md)` → `[text](https://www.notion.so/<page-id>)`
4. **Compute hash** of the converted body (SHA-256, first 16 hex chars)
5. **Push** the converted body to Notion

Steps 1-4 are handled by `push_markdown.py`:

```bash
python scripts/push_markdown.py prepare --file research/kwaxala.md --output .notion-sync/push-staging/kwaxala.md
```

For batch operations:

```bash
python scripts/push_markdown.py batch --folders research/ report/
```

The batch command only processes files whose content hash differs from the manifest, outputting prepared bodies to `.notion-sync/push-staging/`.

## Multi-folder file discovery

When config has `sync_folders: ["research/", "report/"]`, file discovery walks all listed folders:

```bash
python scripts/manifest.py bootstrap --folders research/ report/
python scripts/manifest.py discover --folders research/ report/
```

`bootstrap` matches existing files to manifest entries by `notion_id` or `title`. `discover` finds files that aren't tracked in the manifest yet.

When creating new files from Notion, if multiple sync folders exist, the agent should ask the user which folder to place the file in.

## replace_content vs update_content decision tree

Choose the right push strategy based on the situation:

| Scenario | Strategy | Why |
|---|---|---|
| New page or full rewrite | `replace_content` | Clean slate, no format matching issues |
| Section-level edit | `update_content` with `old_str`/`new_str` | Preserves child pages, less disruptive |
| Page has child pages | `update_content` only | `replace_content` will fail or delete children |
| Content has complex Notion formatting | `update_content` | Preserving formatting you can't reproduce |
| First push (page was empty) | `replace_content` | No existing content to preserve |

When using `update_content`, always fetch the page first to get the exact current content for `old_str` matching.
