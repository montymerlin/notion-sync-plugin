# Gotchas and Lessons Learned

Critical operational knowledge built from real sync incidents. Read this before every sync session.

## Content format issues

### Notion tables are XML, not markdown

Notion internally stores tables as `<table><tr><td>` XML. When using `update_content` with `old_str`, the string must match this XML format — not markdown pipe tables. Always fetch the page first to see the actual format before attempting targeted edits.

On pull: if local has a markdown pipe table and Notion has XML, prefer the local format unless Notion has genuinely new table content.

### Notion toggles produce non-standard markdown

When pulling content from Notion, expect these artifacts:

- Headings with `{toggle="true"}` attribute
- Content wrapped in `<details>/<summary>` HTML blocks
- `<empty-block/>` tags in empty sections
- `<span color="...">` tags for colored text
- Tab-indented content inside toggles (renders as code blocks in standard markdown)

The `clean_notion_markdown()` function in `sync-engine.md` handles all of these. Run it on every pulled page.

### Tab indentation from toggles

Notion indents content inside toggles with leading tabs. In standard markdown, tabs render as code blocks — breaking the file's readability. The post-processing strips these tabs automatically, but be aware that this can affect intentionally indented content (rare).

## Data loss risks

### Content loss on pull

If content was added locally but never pushed, pulling the Notion version will overwrite it. The 20% word-count check catches most cases, but small additions may slip through.

**Prevention:** Always run a bidirectional sync (not pull-only). The change detection will classify the file as a conflict if both sides changed, giving the user a chance to review.

### Content fabrication on large document pushes

**Never use `notion-update-page` with `replace_content` for document bodies.** Two failure modes:

1. **Main-context fabrication**: When the agent calls `notion-update-page(command="replace_content", new_str="<content>")`, the `new_str` value is generated token-by-token by the LLM — even if the agent has just read the staging file. For documents over a few thousand words (and near-certain for documents over ~10K words), at least one substantive deviation from the source will occur. The EthicHub document (85K chars) was visibly "AI-regenerated" — structure preserved, prose rewritten.

2. **Subagent fabrication**: If a subagent can't access a file (e.g. temp files in `/tmp/`), it may generate content from training data instead of erroring.

**Rule:** Always use `push_markdown.py push-content` for content writes. This reads the staging file as bytes and sends it to the Blocks API directly — no LLM generation in the data path.

## Property handling

### Multi-select requires JSON array strings

When pushing multi-select properties (category, topics, tags, etc.), the value must be a JSON array string:

```
"Category": "[\"Value1\", \"Value2\"]"
```

NOT a plain string. Plain strings silently drop all but one value. This applies to all multi-select Notion properties.

### Property names are exact

Notion property names include all whitespace and casing. Some databases have property names with trailing spaces (e.g. `"Tags "` with a trailing space). The property map in `config.json` must use the exact Notion property name.

### Last edited time rounding

Notion's `last_edited_time` is rounded to the nearest minute. Always add a 60-second buffer when comparing timestamps to avoid false negatives in change detection.

## Push mechanics

### replace_content vs update_content

- **`replace_content`**: Replaces the entire page body. Safe and predictable, but fails if the page has child pages.
- **`update_content`**: Targeted search-and-replace. Requires `old_str` to exactly match Notion's internal format (which may differ from what you see in markdown).

Prefer `replace_content` for small-to-medium pages. Use `update_content` only when you need to preserve child pages or make surgical edits.

### Child page protection

Some Notion pages have child pages (sub-pages nested inside them). Using `replace_content` will fail with an error about deleting child content.

Options:
1. Include the child page reference in your `new_str` using `<page url="...">` format
2. Use `update_content` for targeted edits only
3. Push properties only and skip content
4. Use `allow_deleting_content: true` (destructive — deletes child pages)

Always ask the user before choosing option 4.

## Search limitations

### Semantic search is not exhaustive

The `notion-search` tool returns max 25 results per query and uses semantic matching. A single query will miss pages.

**Mitigation:** Run 3-4 diverse queries with different keywords. Deduplicate by page ID. Expect to find 70-90% of pages per sync round.

Pages not found in search are NOT deleted — they just weren't surfaced. The manifest tracks all known pages regardless of search results.

### New pages require search

Pages added directly in Notion won't appear in the manifest until discovered through search. Run diverse queries to catch new additions.

## Link conversion

### Anchor links don't work in Notion

Markdown `[text](#section-name)` renders as blue text in Notion that does nothing when clicked. These links are harmless but non-functional. Consider converting to bold on push if the visual is confusing.

### Notion auto-converts filenames to URLs

If you push content containing `[text](filename.md)` without converting to a Notion URL first, Notion may auto-convert it to `https://filename.md` — a broken external URL. Always convert local links to Notion page URLs before pushing.

## Workflow safety

### Never auto-commit after sync

Always show the user what changed and let them review before committing. Use the `/commit` skill for consistent formatting.

### Always run bidirectional sync

Running pull-only or push-only misses conflicts and risks overwriting changes. Always classify changes in both directions before executing any operations.

### Check for per-page asset subfolders

Some synced files have associated asset subfolders (images, PDFs, HTML files) referenced from the markdown. Be aware of these when moving or renaming files.

### Emoji and Unicode in Edit tool

Some files contain emoji sequences or Unicode characters that the Edit tool can't match reliably. For files with known emoji content, use Python `content.replace()` as a workaround, or write the complete file using the Write tool.

## Page discovery

### Database query is exhaustive; semantic search is not

Fetching a data source via `notion-fetch(id="collection://<data_source_id>")` returns all pages in the database. Semantic search returns max 25 results per query and may miss pages with unusual titles. Prefer database query for full syncs; use semantic search only as a fallback.

### Validate property maps against the schema

Run `notion-fetch` on the data source ID to see the full database schema, including all property names, types, and allowed options. Use this during setup to validate that the `config.json` property map uses exact Notion property names and types. This catches trailing spaces, case mismatches, and missing properties before they cause silent failures during sync.

## Content hashing

### Hash after link conversion, not before

When pushing to Notion, the content hash must be computed on the body *after* local links have been converted to Notion URLs. This is because the converted content is what Notion stores — if you hash before conversion, the hash won't match on the next pull, causing a false "changed" detection. The `push_markdown.py` script handles this correctly.

## Link conversion

### Use the link registry, not ad-hoc matching

The link registry (`.notion-sync/link-registry.json`) maintains a bidirectional map between local filenames and Notion page IDs. Use it for all link conversion — don't try to slugify Notion titles into filenames or manually build lookup tables. The registry is rebuilt from the manifest after every sync via `link_registry.py build`.

### Short slugs vs long Notion titles

Local files often use shorter slugs than Notion page titles (e.g. `berkana-two-loop.md` for "The Berkana Two Loop: Reimagining Finance — A Living Systems View"). Auto-slugifying Notion titles will not match these short slugs. The link registry solves this because it maps by page ID, not by title.

## Future considerations

### Notion webhooks

Notion supports webhooks for real-time change notification, but these aren't available via the MCP yet. When they become available, they could replace the timestamp-polling approach for detecting Notion-side changes.
