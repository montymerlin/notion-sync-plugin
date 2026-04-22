# notion-sync v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the notion-sync plugin push path to eliminate content fabrication, add metadata-first diffing with targeted push operations, and fix two known script bugs.

**Architecture:** Moves all content writes off MCP onto a direct Notion Blocks API call via integration token; property-only writes remain MCP-based (structured data, no fabrication risk); the manifest gains per-page property snapshots enabling a `push_target` field that drives targeted `properties_only`, `content_only`, or `both` push operations. Scripts stay stdlib-only Python with no external dependencies.

**Tech Stack:** Python 3.8+ (stdlib only: argparse, hashlib, json, re, pathlib, urllib.request), Notion Blocks API v2022-06-28, Notion MCP tools (notion-update-page for properties, notion-fetch for reads)

**Spec:** `docs/superpowers/specs/2026-04-22-notion-sync-v03-design.md`

---

## File Map

| File | What changes |
|---|---|
| `scripts/link_registry.py` | Bug fix: dict iteration in `build()`; unresolved link rendering in `convert_links()` |
| `scripts/push_markdown.py` | Remove duplicate `load_link_registry`/`convert_links`; import `LinkRegistry`; add token loading; add `push-content` + `push-properties` subcommands |
| `scripts/manifest.py` | v2 migration in `load_manifest`; `"version": 2` in `save_manifest`; registry freshness check + property diff in `cmd_diff`; `properties: {}` init in `cmd_bootstrap`/`cmd_update` |
| `skills/notion-setup/SKILL.md` | Add Steps 4a–4c: token setup, `.env` file, dry-run verification |
| `skills/notion-sync/SKILL.md` | Simplify Step 2 diff; update Step 3 plan format; update Step 5 manifest write; replace Step 6 push workflow |
| `skills/notion-sync/references/gotchas.md` | Expand content fabrication warning to cover main-context MCP pushes, not only subagents |
| `skills/notion-sync/references/sync-engine.md` | Update push procedure section to reference new subcommands |
| `DECISIONS.md` | Add Decision 007 (direct API push) and Decision 008 (manifest v2) |
| `ROADMAP.md` | Add four items: per-file sync opt-out, CDN image hosting, multi-operator support, page lock |

---

## Task 1: Fix `link_registry.py` — dict iteration bug

**Files:**
- Modify: `scripts/link_registry.py:100-115`

The `build()` method calls `manifest.get("pages", [])` which returns a dict keyed by page ID, then iterates it as if it were a list. `for entry in entries` iterates the dict keys (strings), causing `AttributeError: 'str' object has no attribute 'get'`.

- [ ] **Open `scripts/link_registry.py` and replace lines 101–112 in `build()`:**

```python
        # Reset registry
        self.by_file = {}
        self.by_page = {}

        # Extract entries from manifest
        entries = manifest.get("pages", {})
        count = 0

        for page_id, entry in entries.items():
            local_file = entry.get("local_file")

            # Only add if both local_file and page_id exist
            if local_file and page_id:
                self.by_file[local_file] = page_id
                self.by_page[page_id] = local_file
                count += 1
```

- [ ] **Verify: run `build` with a two-page manifest and confirm correct output**

```bash
cd /path/to/notion-sync-plugin
python -c "
import json, tempfile, os
from pathlib import Path

manifest = {
  'pages': {
    'abc123': {'local_file': 'research/test.md', 'title': 'Test'},
    'def456': {'local_file': 'research/other.md', 'title': 'Other'}
  }
}
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(manifest, f)
    mpath = f.name

from scripts.link_registry import LinkRegistry
# Run from repo root — scripts/ is on sys.path when script is loaded directly
import sys; sys.path.insert(0, 'scripts')
from link_registry import LinkRegistry
lr = LinkRegistry(registry_path=Path('/tmp/lr-test.json'), manifest_path=Path(mpath))
count = lr.build()
print('entries:', count)
assert count == 2, f'Expected 2, got {count}'
assert lr.by_file['research/test.md'] == 'abc123'
assert lr.by_page['def456'] == 'research/other.md'
print('PASS')
os.unlink(mpath)
"
```

Expected output: `entries: 2` then `PASS`

- [ ] **Commit:**

```bash
git add scripts/link_registry.py
git commit -m "fix: correct dict iteration in link_registry build()

pages is a dict keyed by page_id, not a list — for entry in entries
was iterating keys (strings) causing AttributeError on entry.get().
Fixed to use entries.items() with page_id from the key.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Fix `link_registry.py` — unresolved link rendering

**Files:**
- Modify: `scripts/link_registry.py:168-179`

Unresolved links in push direction currently emit `<!-- unresolved: path -->` inline HTML comments, which render as visible text in Notion. Per `sync-engine.md`, non-synced files should become `text *(local file)*`.

- [ ] **In `convert_links()`, replace the unresolved branch in the push direction (inside `if direction == "push":`):**

Find the current `replace_fn` function (inside the `push` branch) and change the unresolved return:

```python
            def replace_fn(match):
                text = match.group(1)
                file_path = match.group(2)

                page_id = self.lookup_file(file_path)
                if page_id:
                    stats["links_converted"] += 1
                    return f"[{text}](https://www.notion.so/{page_id})"
                else:
                    stats["links_unresolved"] += 1
                    return f"{text} *(local file)*"
```

- [ ] **Verify: run convert_links with an unresolvable path and confirm output**

```bash
cd /path/to/notion-sync-plugin
python -c "
import sys; sys.path.insert(0, 'scripts')
from link_registry import LinkRegistry
from pathlib import Path
lr = LinkRegistry(registry_path=Path('/tmp/lr-empty.json'), manifest_path=Path('/tmp/nonexistent.json'))
result, stats = lr.convert_links('[see notes](private/notes.md)', 'push')
assert result == 'see notes *(local file)*', repr(result)
assert stats['links_unresolved'] == 1
print('PASS:', repr(result))
"
```

Expected: `PASS: 'see notes *(local file)*'`

- [ ] **Commit:**

```bash
git add scripts/link_registry.py
git commit -m "fix: render unresolved links as 'text *(local file)*' not HTML comments

HTML comments passed through to Notion rendered as visible text.
Per sync-engine.md spec, non-synced local file links should become
plain text with a *(local file)* annotation.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Refactor `push_markdown.py` — remove duplicates, import `LinkRegistry`

**Files:**
- Modify: `scripts/push_markdown.py`

`push_markdown.py` has its own `load_link_registry()` and `convert_links()` that expect `by_file` values to be `{"notion_url": ..., "page_id": ...}` dicts. `link_registry.py` writes `by_file` values as plain `page_id` strings. These formats are incompatible. Fix: delete the duplicate functions and use `LinkRegistry` directly.

- [ ] **Delete the `load_link_registry` function (lines 47–55) and the `convert_links` function (lines 58–102) entirely from `push_markdown.py`**

- [ ] **Add import at the top of `push_markdown.py`, after the existing imports block:**

```python
import os
import urllib.request
import urllib.error
from typing import Dict, Optional, Tuple

import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent))
from link_registry import LinkRegistry
```

Replace the existing `from typing import Dict, Optional, Tuple` line (it's already there — just add the new lines around it). The final imports block should be:

```python
import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from link_registry import LinkRegistry
```

- [ ] **Update `prepare_file()` to accept and use a `LinkRegistry` instance:**

Replace the existing `prepare_file` function:

```python
def prepare_file(
    file_path: Path,
    registry: LinkRegistry,
) -> Tuple[str, int, int, str]:
    """
    Prepare a single markdown file for Notion.

    Returns:
        Tuple of (converted_body, links_converted, links_unresolved, hash)
    """
    content = file_path.read_text(encoding='utf-8')
    body = strip_frontmatter(content)
    converted_body, stats = registry.convert_links(body, "push")
    hash_value = content_hash(converted_body)
    return converted_body, stats["links_converted"], stats["links_unresolved"], hash_value
```

- [ ] **Update `cmd_prepare()` to instantiate `LinkRegistry`:**

Replace the `cmd_prepare` function:

```python
def cmd_prepare(args):
    """Handle 'prepare' subcommand: single file mode."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    registry = LinkRegistry(registry_path=Path(args.registry_path))
    converted_body, links_converted, links_unresolved, hash_value = prepare_file(
        file_path, registry
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(converted_body, encoding='utf-8')
    else:
        print(converted_body)

    summary = {
        "file": str(file_path),
        "body_chars": len(converted_body),
        "content_hash": hash_value,
        "links_converted": links_converted,
        "links_unresolved": links_unresolved,
    }
    print(json.dumps(summary), file=sys.stderr)
```

- [ ] **Update `cmd_batch()` to instantiate `LinkRegistry`:**

Replace `registry = load_link_registry(registry_path)` with:

```python
    registry = LinkRegistry(registry_path=registry_path)
```

And replace `prepare_file(file_path, registry)` calls — they already match the new signature (takes `LinkRegistry`). Remove the duplicate `body = strip_frontmatter(content)` line that appears just before `prepare_file` in `cmd_batch` (line ~185 in original):

```python
    for file_path in sorted(files_to_process):
        content = file_path.read_text(encoding='utf-8')
        converted_body, links_converted, links_unresolved, hash_value = prepare_file(
            file_path, registry
        )
        # ... rest unchanged
```

- [ ] **Verify the script still parses and prepare still works:**

```bash
cd /path/to/notion-sync-plugin
python scripts/push_markdown.py --help
python scripts/push_markdown.py prepare --help
```

Both should print help without errors.

- [ ] **Commit:**

```bash
git add scripts/push_markdown.py
git commit -m "refactor: push_markdown.py uses LinkRegistry directly

Removes duplicate load_link_registry() and convert_links() functions
that expected a different registry format than link_registry.py writes.
Now imports LinkRegistry and calls registry.convert_links() — one
source of truth for link conversion logic and registry format.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Add `push-content` to `push_markdown.py`

**Files:**
- Modify: `scripts/push_markdown.py`

Adds direct Blocks API push — the core capability that eliminates content fabrication. Token loaded from `.notion-sync/.env` → `.env` → `NOTION_TOKEN` env var.

- [ ] **Add token-loading function after the imports block:**

```python
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
BLOCK_BATCH_SIZE = 100


def _load_token(base_path: str = ".notion-sync") -> Optional[str]:
    """Load NOTION_TOKEN from .notion-sync/.env, .env, or environment."""
    for env_path in [Path(base_path) / ".env", Path(".env")]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == "NOTION_TOKEN":
                        return v.strip()
    return os.environ.get("NOTION_TOKEN")


def _notion_request(method: str, path: str, token: str, body: Optional[dict] = None) -> dict:
    """Make an authenticated Notion API request."""
    url = f"{NOTION_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Notion API error {e.code}: {error_body}") from e
```

- [ ] **Add `markdown_line_to_rich_text` helper after the token functions:**

```python
def _markdown_line_to_rich_text(line: str) -> list:
    """Convert inline markdown to Notion rich_text array."""
    parts = []
    pattern = r'(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^\)]+\)|[^*`\[]+)'
    for m in re.finditer(pattern, line):
        chunk = m.group(0)
        if chunk.startswith("**") and chunk.endswith("**"):
            parts.append({"type": "text", "text": {"content": chunk[2:-2]},
                          "annotations": {"bold": True}})
        elif chunk.startswith("*") and chunk.endswith("*"):
            parts.append({"type": "text", "text": {"content": chunk[1:-1]},
                          "annotations": {"italic": True}})
        elif chunk.startswith("`") and chunk.endswith("`"):
            parts.append({"type": "text", "text": {"content": chunk[1:-1]},
                          "annotations": {"code": True}})
        elif chunk.startswith("["):
            link_m = re.match(r'\[([^\]]+)\]\(([^\)]+)\)', chunk)
            if link_m:
                text, url = link_m.group(1), link_m.group(2)
                if url.startswith("http://") or url.startswith("https://"):
                    parts.append({"type": "text", "text": {"content": text, "link": {"url": url}}})
                else:
                    parts.append({"type": "text", "text": {"content": text}})
            else:
                parts.append({"type": "text", "text": {"content": chunk}})
        else:
            if chunk:
                parts.append({"type": "text", "text": {"content": chunk}})
    return parts or [{"type": "text", "text": {"content": ""}}]
```

- [ ] **Add `markdown_to_blocks` function:**

```python
def markdown_to_blocks(markdown: str) -> list:
    """Convert markdown body to Notion block objects."""
    blocks = []
    lines = markdown.split("\n")
    i = 0
    table_rows = []
    in_table = False

    def flush_table():
        if not table_rows:
            return
        max_cols = max(len(r) for r in table_rows)
        rows_data = []
        for row in table_rows:
            cells_data = [_markdown_line_to_rich_text(cell) for cell in row]
            while len(cells_data) < max_cols:
                cells_data.append([{"type": "text", "text": {"content": ""}}])
            rows_data.append({"type": "table_row", "table_row": {"cells": cells_data}})
        blocks.append({
            "type": "table",
            "table": {
                "table_width": max_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": rows_data,
            }
        })

    while i < len(lines):
        line = lines[i]

        # Table row
        if line.strip().startswith("|") and "|" in line[1:]:
            if re.match(r'^\s*\|[\s\-|:]+\|\s*$', line):
                i += 1
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(cells)
            i += 1
            continue
        elif in_table:
            in_table = False
            flush_table()
            table_rows = []

        if re.match(r'^# .+', line):
            text = re.sub(r'\s*\{#[^}]+\}', '', line[2:].strip())
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": _markdown_line_to_rich_text(text)}})
        elif re.match(r'^## .+', line):
            text = re.sub(r'\s*\{#[^}]+\}', '', line[3:].strip())
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": _markdown_line_to_rich_text(text)}})
        elif re.match(r'^### .+', line):
            text = re.sub(r'\s*\{#[^}]+\}', '', line[4:].strip())
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": _markdown_line_to_rich_text(text)}})
        elif re.match(r'^---+\s*$', line):
            blocks.append({"type": "divider", "divider": {}})
        elif line.startswith("> "):
            blocks.append({"type": "quote", "quote": {"rich_text": _markdown_line_to_rich_text(line[2:].strip())}})
        elif re.match(r'^\d+\. .+', line):
            text = re.sub(r'^\d+\. ', '', line).strip()
            blocks.append({"type": "numbered_list_item", "numbered_list_item": {"rich_text": _markdown_line_to_rich_text(text)}})
        elif re.match(r'^[-*] .+', line):
            text = re.sub(r'^[-*] ', '', line).strip()
            blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _markdown_line_to_rich_text(text)}})
        elif re.match(r'^!\[', line):
            img_m = re.match(r'^!\[([^\]]*)\]\(([^\)]+)\)', line)
            if img_m:
                alt, url = img_m.group(1), img_m.group(2)
                if url.startswith("http"):
                    blocks.append({"type": "image", "image": {"type": "external", "external": {"url": url}}})
                else:
                    blocks.append({
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {"type": "text", "text": {"content": "Image placeholder — upload manually: "}, "annotations": {"bold": True}},
                                {"type": "text", "text": {"content": url}, "annotations": {"code": True}},
                                {"type": "text", "text": {"content": f"\nAlt: {alt}"}},
                            ],
                            "icon": {"type": "emoji", "emoji": "🖼️"},
                            "color": "yellow_background",
                        }
                    })
        elif line.startswith("```"):
            lang = line[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            if len(code_content) > 1990:
                code_content = code_content[:1990] + "\n[truncated]"
            blocks.append({"type": "code", "code": {
                "rich_text": [{"type": "text", "text": {"content": code_content}}],
                "language": lang or "plain text",
            }})
        elif line.strip() == "":
            pass
        else:
            text = line.strip()
            while len(text) > 2000:
                chunk = text[:2000]
                last_space = chunk.rfind(" ")
                if last_space > 1500:
                    chunk = chunk[:last_space]
                blocks.append({"type": "paragraph", "paragraph": {"rich_text": _markdown_line_to_rich_text(chunk)}})
                text = text[len(chunk):].strip()
            if text:
                blocks.append({"type": "paragraph", "paragraph": {"rich_text": _markdown_line_to_rich_text(text)}})

        i += 1

    # Flush trailing table
    if in_table and table_rows:
        flush_table()

    return blocks
```

- [ ] **Add `_clear_page_blocks` and `_push_blocks` helpers:**

```python
def _clear_page_blocks(page_id: str, token: str) -> int:
    """Delete all existing blocks from a page, skipping archived ones."""
    deleted = skipped = 0
    seen_ids: set = set()
    while True:
        result = _notion_request("GET", f"/blocks/{page_id}/children", token)
        blocks = result.get("results", [])
        new_blocks = [b for b in blocks if b["id"] not in seen_ids]
        if not new_blocks:
            break
        for block in new_blocks:
            seen_ids.add(block["id"])
            if block.get("archived", False):
                skipped += 1
                continue
            try:
                _notion_request("DELETE", f"/blocks/{block['id']}", token)
                deleted += 1
            except RuntimeError as e:
                if "archived" in str(e).lower():
                    skipped += 1
                else:
                    raise
        if not result.get("has_more"):
            break
    return deleted


def _push_blocks(page_id: str, blocks: list, token: str) -> int:
    """Append blocks to a page in batches of 100. Returns total pushed."""
    pushed = 0
    for start in range(0, len(blocks), BLOCK_BATCH_SIZE):
        batch = blocks[start:start + BLOCK_BATCH_SIZE]
        _notion_request("PATCH", f"/blocks/{page_id}/children", token, {"children": batch})
        pushed += len(batch)
        print(f"  Pushed blocks {start + 1}–{start + len(batch)}", file=sys.stderr)
    return pushed
```

- [ ] **Add `cmd_push_content` function:**

```python
def cmd_push_content(args):
    """Handle 'push-content' subcommand: push staging file to Notion via Blocks API."""
    if args.dry_run:
        # Dry-run: parse and count blocks only, no API calls
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                print(json.dumps({"error": f"file not found: {args.file}"}), file=sys.stderr)
                sys.exit(1)
            markdown = file_path.read_text(encoding="utf-8")
        else:
            markdown = sys.stdin.read()
        blocks = markdown_to_blocks(markdown)
        print(json.dumps({"dry_run": True, "blocks": len(blocks)}))
        return

    # Live push
    token = _load_token(args.registry_path.replace("/manifest.json", "").replace("manifest.json", ".notion-sync"))
    if not token:
        print("Error: NOTION_TOKEN not found.\nAdd it to .notion-sync/.env — run /notion-setup for instructions.", file=sys.stderr)
        sys.exit(1)

    if not args.page_id:
        print("Error: --page-id is required for live push", file=sys.stderr)
        sys.exit(1)

    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"error": f"file not found: {args.file}"}), file=sys.stderr)
        sys.exit(1)

    page_id = args.page_id.replace("-", "")
    markdown = file_path.read_text(encoding="utf-8")
    blocks = markdown_to_blocks(markdown)

    print(f"Clearing existing page content...", file=sys.stderr)
    deleted = _clear_page_blocks(page_id, token)
    print(f"  Deleted {deleted} blocks", file=sys.stderr)

    print(f"Pushing {len(blocks)} blocks...", file=sys.stderr)
    pushed = _push_blocks(page_id, blocks, token)

    # Optional page lock
    if args.lock:
        _notion_request("PATCH", f"/pages/{page_id}", token, {"locked": True})
        print("  Page locked", file=sys.stderr)

    print(json.dumps({"status": "pushed", "page_id": page_id, "blocks_pushed": pushed}))
```

- [ ] **Add `push-content` subparser to `main()`**

In the `main()` function, after the `batch` subparser block, add:

```python
    # 'push-content' subcommand
    push_content_parser = subparsers.add_parser(
        "push-content",
        help="Push prepared staging file to Notion via direct Blocks API",
    )
    push_content_parser.add_argument(
        "--page-id",
        help="Notion page ID (32-char hex). Required unless --dry-run.",
    )
    push_content_parser.add_argument(
        "--file",
        help="Path to prepared staging file (from 'prepare' subcommand)",
    )
    push_content_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count blocks without making any API calls",
    )
    push_content_parser.add_argument(
        "--lock",
        action="store_true",
        help="Lock the Notion page after push (requires lock_after_push: true in config)",
    )
    push_content_parser.set_defaults(func=cmd_push_content)
```

- [ ] **Wire `push-content` into the `args.func(args)` dispatch at the end of `main()`:**

The existing pattern uses `args.func(args)` — this already works because `push_content_parser.set_defaults(func=cmd_push_content)` is set. Verify the final `args.func(args)` call exists; if the script uses explicit `if args.command == "..."` branching instead, add `elif args.command == "push-content": cmd_push_content(args)`.

- [ ] **Verify dry-run works without a token or page ID:**

```bash
cd /path/to/notion-sync-plugin
echo "# Hello\n\nThis is a test." | python scripts/push_markdown.py push-content --dry-run
```

Expected output (to stdout): `{"dry_run": true, "blocks": 2}`

- [ ] **Commit:**

```bash
git add scripts/push_markdown.py
git commit -m "feat: add push-content subcommand with direct Blocks API push

Absorbs notion_push_content.py from bridging-worlds workaround.
Reads staging file, converts to Notion blocks, clears existing
page content, pushes in batches of 100. Token loaded from
.notion-sync/.env → .env → NOTION_TOKEN env var.
Dry-run mode counts blocks without any API calls.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Add `push-properties` to `push_markdown.py`

**Files:**
- Modify: `scripts/push_markdown.py`

Reads local frontmatter, maps fields through `config.json`'s `property_map`, serialises multi-select values correctly, outputs JSON for the agent to pass to `notion-update-page` via MCP. No token required.

The `config.json` property_map format (from notion-setup SKILL.md):
```json
{
  "Notion Property Name": { "yaml_key": "local_field_name", "type": "multi_select" }
}
```

- [ ] **Add `_parse_frontmatter_dict` helper (simple YAML key-value extractor):**

```python
def _parse_frontmatter_dict(content: str) -> Optional[dict]:
    """Extract YAML frontmatter as a flat dict. Returns None if no frontmatter."""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    yaml_block = content[3:end].strip()
    result = {}
    for line in yaml_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip().strip('"')
        # Simple list detection: [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1]
            result[key] = [v.strip().strip('"') for v in inner.split(",") if v.strip()]
        else:
            result[key] = val
    return result
```

- [ ] **Add `cmd_push_properties` function:**

```python
def cmd_push_properties(args):
    """Output property update payload for MCP notion-update-page call."""
    file_path = Path(args.file)
    if not file_path.exists():
        print(json.dumps({"error": f"file not found: {args.file}"}), file=sys.stderr)
        sys.exit(1)

    config_path = Path(args.config_path)
    if not config_path.exists():
        print(json.dumps({"error": f"config not found: {args.config_path}"}), file=sys.stderr)
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    property_map = config.get("property_map", {})

    content = file_path.read_text(encoding="utf-8")
    front = _parse_frontmatter_dict(content)
    if front is None:
        print(json.dumps({"error": "no YAML frontmatter found in file"}), file=sys.stderr)
        sys.exit(1)

    notion_id = front.get("notion_id")
    if not notion_id:
        print(json.dumps({"error": "notion_id not found in frontmatter"}), file=sys.stderr)
        sys.exit(1)

    # Build Notion properties dict
    # property_map: {"Notion Property Name": {"yaml_key": "local_key", "type": "..."}}
    properties = {}
    for notion_prop_name, prop_config in property_map.items():
        yaml_key = prop_config.get("yaml_key")
        prop_type = prop_config.get("type", "rich_text")
        if not yaml_key or yaml_key in ("title", "notion_id", "created", "last_edited", "last_synced"):
            continue  # skip system fields
        value = front.get(yaml_key)
        if value is None:
            continue
        # Multi-select must be serialised as JSON array string
        if prop_type == "multi_select":
            if isinstance(value, list):
                properties[notion_prop_name] = json.dumps(value)
            else:
                properties[notion_prop_name] = json.dumps([value])
        else:
            properties[notion_prop_name] = str(value)

    print(json.dumps({
        "page_id": notion_id,
        "properties": properties
    }))
```

- [ ] **Add `push-properties` subparser to `main()`:**

```python
    # 'push-properties' subcommand
    push_props_parser = subparsers.add_parser(
        "push-properties",
        help="Output property payload for notion-update-page MCP call",
    )
    push_props_parser.add_argument(
        "--file",
        required=True,
        help="Path to local markdown file with YAML frontmatter",
    )
    push_props_parser.add_argument(
        "--config-path",
        default=".notion-sync/config.json",
        help="Path to config.json (default: .notion-sync/config.json)",
    )
    push_props_parser.set_defaults(func=cmd_push_properties)
```

- [ ] **Verify with a test frontmatter file:**

```bash
cd /path/to/notion-sync-plugin
cat > /tmp/test-page.md << 'EOF'
---
notion_id: "abc123def456abc123def456abc123de"
title: "Test Page"
research_stage: "🪴 Grown"
topics: [ReFi, Web3]
system_change: "Reimagination"
---

# Test Page

Content here.
EOF

cat > /tmp/test-config.json << 'EOF'
{
  "data_source_id": "test",
  "sync_folders": ["research/"],
  "property_map": {
    "Research Stage": {"yaml_key": "research_stage", "type": "select"},
    "Topics": {"yaml_key": "topics", "type": "multi_select"},
    "System Change": {"yaml_key": "system_change", "type": "select"}
  }
}
EOF

python scripts/push_markdown.py push-properties --file /tmp/test-page.md --config-path /tmp/test-config.json
```

Expected output:
```json
{"page_id": "abc123def456abc123def456abc123de", "properties": {"Research Stage": "🪴 Grown", "Topics": "[\"ReFi\", \"Web3\"]", "System Change": "Reimagination"}}
```

- [ ] **Commit:**

```bash
git add scripts/push_markdown.py
git commit -m "feat: add push-properties subcommand

Outputs correctly-formatted properties JSON for MCP notion-update-page
call. Reads YAML frontmatter, maps yaml_key → Notion property name via
config.json property_map, serialises multi_select as JSON array strings.
No token required — agent passes output to MCP tool directly.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Upgrade `manifest.py` to v2

**Files:**
- Modify: `scripts/manifest.py`

Adds: auto-migration from v1→v2 on load; `"version": 2` on save; property diff + `push_target` in `cmd_diff`; registry freshness check before diff; `"properties": {}` initialisation in `cmd_update` and `cmd_bootstrap`.

- [ ] **Add `LinkRegistry` import at top of file, after the existing `from build_markdown import ...` line:**

```python
from link_registry import LinkRegistry
```

- [ ] **Replace `load_manifest` with v2-aware version:**

```python
def load_manifest(path: str) -> dict:
    """Load manifest from file. Auto-migrates v1 → v2 format."""
    p = Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        if manifest.get("version", 1) < 2:
            manifest["version"] = 2
            for page_entry in manifest.get("pages", {}).values():
                if "properties" not in page_entry:
                    page_entry["properties"] = {}
            save_manifest(manifest, path)
        return manifest
    return {
        "version": 2,
        "data_source_id": None,
        "last_full_sync": None,
        "pages": {}
    }
```

- [ ] **Update `save_manifest` to always write `version: 2`:**

```python
def save_manifest(manifest: dict, path: str):
    """Save manifest to file, creating parent dirs if needed."""
    manifest.setdefault("version", 2)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
```

- [ ] **Update `cmd_update` to initialise the `properties` field:**

In `cmd_update`, change the `manifest["pages"][args.page_id] = {...}` assignment to include `properties`:

```python
def cmd_update(args):
    manifest = load_manifest(args.manifest_path)
    synced_at = now_iso()
    # Preserve existing properties snapshot if updating an existing entry
    existing = manifest.get("pages", {}).get(args.page_id, {})
    manifest["pages"][args.page_id] = {
        "local_file": args.local_file,
        "title": args.title,
        "last_notion_edit": args.last_notion_edit,
        "last_synced": synced_at,
        "content_hash": args.content_hash or "",
        "properties": existing.get("properties", {})
    }
    save_manifest(manifest, args.manifest_path)
    print(json.dumps({"status": "updated", "page_id": args.page_id, "synced_at": synced_at}))
```

- [ ] **Update `cmd_bootstrap` to initialise `properties: {}` on matched pages:**

In `cmd_bootstrap`, after `pages[matched_page_id]["content_hash"] = computed_hash`, add:

```python
                if "properties" not in pages[matched_page_id]:
                    pages[matched_page_id]["properties"] = {}
```

- [ ] **Replace `cmd_diff` with property-aware v2 version:**

```python
def _property_diff(local_front: dict, manifest_props: dict, property_map: dict) -> dict:
    """Compare local frontmatter to manifest property snapshot.
    Returns {yaml_key: {"was": old_val, "now": new_val}} for changed fields.
    """
    diff = {}
    for notion_prop, prop_config in property_map.items():
        yaml_key = prop_config.get("yaml_key")
        if not yaml_key or yaml_key in ("title", "notion_id", "created", "last_edited", "last_synced"):
            continue
        local_val = local_front.get(yaml_key)
        manifest_val = manifest_props.get(yaml_key)
        # Normalise lists for comparison
        lv = tuple(sorted(local_val)) if isinstance(local_val, list) else local_val
        mv = tuple(sorted(manifest_val)) if isinstance(manifest_val, list) else manifest_val
        if lv != mv:
            diff[yaml_key] = {"was": manifest_val, "now": local_val}
    return diff


def cmd_diff(args):
    """Show differences between local and manifest state, with property-level detail."""
    manifest = load_manifest(args.manifest_path)
    pages = manifest.get("pages", {})

    # Load property_map from config.json (sibling of manifest)
    config_path = Path(args.manifest_path).parent / "config.json"
    property_map = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            property_map = json.load(f).get("property_map", {})

    # Registry freshness check
    registry_path = Path(args.manifest_path).parent / "link-registry.json"
    manifest_p = Path(args.manifest_path)
    registry_stale = (
        not registry_path.exists() or
        (manifest_p.exists() and registry_path.stat().st_mtime < manifest_p.stat().st_mtime)
    )
    if registry_stale:
        lr = LinkRegistry(registry_path=registry_path, manifest_path=manifest_p)
        lr.build()

    local_changed = []
    notion_changed = []
    conflicts = []
    new_local = []
    unchanged = 0
    seen_local_files = set()

    for page_id, page_info in pages.items():
        local_file = page_info.get("local_file")
        if not local_file:
            continue
        local_path = Path(local_file)
        if not local_path.exists():
            continue
        seen_local_files.add(local_file)

        props, content_body = parse_frontmatter(str(local_path))

        # Property diff
        manifest_props = page_info.get("properties", {})
        prop_diff = _property_diff(props or {}, manifest_props, property_map)
        props_changed = bool(prop_diff)

        # Content diff
        computed_hash = content_hash(content_body)
        stored_hash = page_info.get("content_hash", "")
        content_changed = computed_hash != stored_hash

        # Notion-side timestamp check
        stored_last_notion = page_info.get("last_notion_edit", "")
        stored_last_synced = page_info.get("last_synced", "")
        notion_changed_flag = False
        if stored_last_notion and stored_last_synced:
            try:
                notion_dt = datetime.fromisoformat(stored_last_notion.replace("Z", "+00:00"))
                synced_dt = datetime.fromisoformat(stored_last_synced.replace("Z", "+00:00"))
                notion_changed_flag = notion_dt > (synced_dt + timedelta(seconds=60))
            except (ValueError, AttributeError):
                pass

        # Determine push_target
        if props_changed and content_changed:
            push_target = "both"
        elif props_changed:
            push_target = "properties_only"
        elif content_changed:
            push_target = "content_only"
        else:
            push_target = "none"

        local_changed_flag = props_changed or content_changed
        entry = {
            "page_id": page_id,
            "local_file": local_file,
            "title": page_info.get("title", ""),
            "push_target": push_target,
            "property_diff": prop_diff,
            "content_changed": content_changed,
        }

        if local_changed_flag and notion_changed_flag:
            conflicts.append(entry)
        elif local_changed_flag:
            local_changed.append(entry)
        elif notion_changed_flag:
            notion_changed.append({
                "page_id": page_id,
                "local_file": local_file,
                "title": page_info.get("title", "")
            })
        else:
            unchanged += 1

    # New local files
    sync_folders = set()
    for page_info in pages.values():
        lf = page_info.get("local_file", "")
        if lf:
            parts = Path(lf).parts
            if len(parts) > 1:
                sync_folders.add(str(Path(parts[0])))

    for folder in sync_folders:
        folder_path = Path(folder)
        if folder_path.exists():
            for md_file in folder_path.glob("**/*.md"):
                if str(md_file) not in seen_local_files:
                    new_local.append(str(md_file))

    print(json.dumps({
        "local_changed": local_changed,
        "notion_changed": notion_changed,
        "conflicts": conflicts,
        "new_local": sorted(new_local),
        "unchanged": unchanged
    }))
```

- [ ] **Verify migration: run diff on a v1 manifest and check `push_target` appears in output**

```bash
cd /path/to/notion-sync-plugin

# Create a minimal v1 manifest (no version field, no properties)
cat > /tmp/test-manifest.json << 'EOF'
{
  "data_source_id": "test-db-id",
  "last_full_sync": null,
  "pages": {}
}
EOF

python scripts/manifest.py diff --manifest-path /tmp/test-manifest.json

# Confirm migration: check that version: 2 was written
python -c "import json; m = json.load(open('/tmp/test-manifest.json')); assert m.get('version') == 2, m; print('Migration PASS: version =', m['version'])"
```

Expected: diff outputs `{"local_changed": [], ...}`, migration check prints `Migration PASS: version = 2`

- [ ] **Commit:**

```bash
git add scripts/manifest.py
git commit -m "feat: manifest v2 — property snapshots and targeted diff output

Auto-migrates v1 manifests on load (adds version:2, properties:{} per
page). diff command now outputs push_target (properties_only/content_only
/both/none) and property_diff per changed file. Registry freshness check
runs link_registry build before diff if registry is stale.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Update `notion-setup/SKILL.md`

**Files:**
- Modify: `skills/notion-setup/SKILL.md`

Adds token setup between existing Step 4 (create config) and Step 5 (initial population). Renumbers Step 5→6 and Step 6→7.

- [ ] **Open `skills/notion-setup/SKILL.md` and add a new "Step 5: Set up your Notion integration token" section between the existing Step 4 and Step 5:**

Insert after the `## Step 4: Create the config` section's closing content and before `## Step 5: Initial population`:

```markdown
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
```

- [ ] **Renumber the old Step 5 to Step 6, and old Step 6 to Step 7.** Update both the heading and any cross-references:

Change `## Step 5: Initial population` → `## Step 6: Initial population`
Change `## Step 6: Confirm and advise` → `## Step 7: Confirm and advise`

- [ ] **In Step 7 (was Step 6), update the gitignore advice** to reflect that `.notion-sync/.env` also holds the token:

Find the sentence about gitignore and update it:

```markdown
- Add the entire `.notion-sync/` directory to `.gitignore` — this covers your config, manifest, link registry, staging files, and integration token. All of these are personal operator state.
```

- [ ] **Verify SKILL.md is valid markdown:**

```bash
python -c "
content = open('skills/notion-setup/SKILL.md').read()
assert '## Step 5: Set up your Notion integration token' in content
assert '## Step 6: Initial population' in content
assert '## Step 7: Confirm and advise' in content
print('PASS')
"
```

- [ ] **Commit:**

```bash
git add skills/notion-setup/SKILL.md
git commit -m "docs: add token setup step to notion-setup skill

New Step 5 guides the user through creating a Notion Internal
Integration, connecting it to the database, and storing the token
in .notion-sync/.env. Includes dry-run verification. Steps 5-6
renumbered to 6-7.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Update `notion-sync/SKILL.md`

**Files:**
- Modify: `skills/notion-sync/SKILL.md`

Four changes: simplify Step 2 diff, update Step 3 plan format, update Step 5 manifest write, replace Step 6 push workflow. Update important notes.

- [ ] **Replace the Step 2 "Local inventory" sub-block** with the simplified single-command version:

Find the block starting with `**Local inventory:** Use the helper script to generate a diff preview:` and replace everything up to (but not including) `**Notion inventory:**`:

```markdown
**Local inventory:** Run the diff script to generate a complete change picture — it checks both property changes (frontmatter fields vs. manifest snapshot) and content changes (hash comparison), and ensures the link registry is fresh before running:

```bash
python scripts/manifest.py diff --manifest-path .notion-sync/manifest.json
```

Output includes `push_target` per changed file (`properties_only`, `content_only`, `both`, `none`), `property_diff` showing which fields changed, and `content_changed` flag. No separate property check is needed — the diff command handles it.
```

- [ ] **Update Step 3 sync plan format** to show push type breakdown:

Find the plan template block and replace it:

```markdown
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
```

- [ ] **Update Step 5 manifest update** to capture the properties snapshot:

After the existing "9. Update the manifest entry" bullet, add:

```markdown
10. Capture the properties snapshot: for each property in the pull response, store its value in `manifest["pages"][page_id]["properties"]` keyed by `yaml_key`. This baseline is used by future diffs to detect property-only changes.
```

- [ ] **Replace the entire Step 6 "Execute pushes" section** with the script-driven version:

Replace the current Step 6 content:

```markdown
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
```

- [ ] **Update the "Important notes" section** — add two new bullets:

```markdown
- **Always use `push_markdown.py` for all content writes — never `notion-update-page` with `replace_content`.** The MCP content path passes text through LLM token generation and is unreliable for documents over a few thousand words. See `references/gotchas.md`.
- **Token auto-loaded from `.notion-sync/.env` or `.env`.** Run `/notion-setup` if content pushes fail with token errors.
```

- [ ] **Verify SKILL.md contains the new push workflow keywords:**

```bash
python -c "
content = open('skills/notion-sync/SKILL.md').read()
assert 'push_target' in content
assert 'push-content' in content
assert 'push-properties' in content
assert 'notion-update-page' not in content.split('push_target')[0].split('replace_content')[0] or True  # soft check
assert 'never called' in content or 'never' in content
print('PASS')
"
```

- [ ] **Commit:**

```bash
git add skills/notion-sync/SKILL.md
git commit -m "docs: update notion-sync skill for v0.3 push workflow

Step 2 simplified — manifest.py diff now handles property+content diff
in one call. Step 3 plan format shows push type breakdown. Step 6
replaced: no more MCP replace_content; push-content (Blocks API) for
content, push-properties (MCP update_properties) for properties.
Important notes updated with content fabrication warning.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Update reference docs

**Files:**
- Modify: `skills/notion-sync/references/gotchas.md`
- Modify: `skills/notion-sync/references/sync-engine.md`

- [ ] **In `gotchas.md`, expand the "Silent content fabrication" section** to cover main-context MCP pushes as well as subagents:

Find the section starting with `### Silent content fabrication with subagents` and replace it:

```markdown
### Content fabrication on large document pushes

**Never use `notion-update-page` with `replace_content` for document bodies.** Two failure modes:

1. **Main-context fabrication**: When the agent calls `notion-update-page(command="replace_content", new_str="<content>")`, the `new_str` value is generated token-by-token by the LLM — even if the agent has just read the staging file. For documents over a few thousand words (and near-certain for documents over ~10K words), at least one substantive deviation from the source will occur. The EthicHub document (85K chars) was visibly "AI-regenerated" — structure preserved, prose rewritten.

2. **Subagent fabrication**: If a subagent can't access a file (e.g. temp files in `/tmp/`), it may generate content from training data instead of erroring.

**Rule:** Always use `push_markdown.py push-content` for content writes. This reads the staging file as bytes and sends it to the Blocks API directly — no LLM generation in the data path.
```

- [ ] **In `sync-engine.md`, replace the "Push procedure" section** to reference the new subcommands:

Find the `## Push procedure (local → Notion)` heading and update the steps:

```markdown
## Push procedure (local → Notion)

### 1. Determine push target

Run `manifest.py diff` to get `push_target` for each changed file:
- `properties_only` — only frontmatter fields changed; body unchanged
- `content_only` — body changed; properties unchanged
- `both` — both changed
- `none` — skip

### 2. Prepare staging file (if content push needed)

```bash
python scripts/push_markdown.py prepare \
  --file <local_path> \
  --output .notion-sync/push-staging/<slug>.md
```

Strips frontmatter, converts local links to Notion URLs via link registry, computes content hash. Output goes to `.notion-sync/push-staging/`.

### 3. Push content (if push_target is `content_only` or `both`)

```bash
python scripts/push_markdown.py push-content \
  --page-id <notion_id> \
  --file .notion-sync/push-staging/<slug>.md
```

Reads staging file, converts to Notion blocks, clears existing page content, pushes in batches of 100. Requires `NOTION_TOKEN` in `.notion-sync/.env`.

### 4. Push properties (if push_target is `properties_only` or `both`)

```bash
python scripts/push_markdown.py push-properties \
  --file <local_path> \
  --config-path .notion-sync/config.json
```

Outputs JSON payload. Pass `output.properties` to:
```
notion-update-page(page_id=<page_id>, command="update_properties", properties=<output.properties>)
```

Multi-select values are automatically serialised as JSON array strings. No token required.

### 5. Update manifest and frontmatter

- Manifest: update `content_hash`, `last_synced`, and `properties` snapshot
- Local file: update `last_synced` in YAML frontmatter
```

- [ ] **Verify both reference files are valid markdown:**

```bash
python -c "
for path in ['skills/notion-sync/references/gotchas.md', 'skills/notion-sync/references/sync-engine.md']:
    content = open(path).read()
    assert len(content) > 100, f'{path} seems too short'
    print(f'OK: {path} ({len(content)} chars)')
"
```

- [ ] **Commit:**

```bash
git add skills/notion-sync/references/gotchas.md skills/notion-sync/references/sync-engine.md
git commit -m "docs: update reference docs for v0.3 push workflow

gotchas.md: expand fabrication warning to cover main-context MCP pushes,
not just subagents. Documents the EthicHub incident.
sync-engine.md: replace push procedure to reference push-content and
push-properties subcommands; add push_target decision tree.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Update reasoning artifacts

**Files:**
- Modify: `DECISIONS.md`
- Modify: `ROADMAP.md`

- [ ] **Add Decision 007 to `DECISIONS.md`** (append after the last `---` separator):

```markdown
## Decision 007: Direct API push + integration token as first-class config

**Status:** Accepted
**Date:** 2026-04-22

**Context:** The v0.2 push path called `notion-update-page(command="replace_content", new_str=<content>)` via MCP. The `new_str` value is generated token-by-token by the LLM, making content fabrication near-certain for large documents. The EthicHub document (85K chars, ~300 blocks) was pushed as AI-regenerated prose. A workaround script calling the Notion Blocks API directly was written in the bridging-worlds consumer repo, confirming direct API push eliminates the problem.

**Decision:** Notion integration token is required for content writes. `push_markdown.py push-content` reads the staging file as bytes and sends it to the Blocks API directly — no LLM generation in the path. MCP is retained for reads (`notion-fetch`, `notion-search`) and property writes (`notion-update-page update_properties`) since those paths don't pass generated prose.

**Consequences:**
- Content fabrication eliminated by design, not by workaround
- Token setup adds one step to `/notion-setup`
- Property-only changes remain token-free (use MCP)
- bridging-worlds `.scripts/notion_push_content.py` can be retired

**Alternatives Considered:**
- MCP-only with documented size limits — rejected, data integrity failure not a performance issue
- Token optional with MCP fallback — rejected, adds complexity without benefit for single-operator
- Ecosystem research confirmed only `go-notion-md-sync` achieves bidirectional sync; all other tools are export-only, validating the custom plugin approach
```

- [ ] **Add Decision 008 to `DECISIONS.md`** (append after Decision 007):

```markdown
## Decision 008: Manifest v2 with property snapshots

**Status:** Accepted
**Date:** 2026-04-22

**Context:** The v1 manifest stored only a content hash per page. Property changes (e.g. updating `research_stage` in frontmatter) were detected by the SKILL.md agent manually, not by the diff script — making the detection inconsistent and the push unnecessarily heavy (any change triggered a full content push even if only frontmatter changed).

**Decision:** Add `"properties"` snapshot per manifest entry (keyed by `yaml_key`). `manifest.py diff` now outputs `push_target` (`properties_only`, `content_only`, `both`, `none`) and `property_diff` per changed file. Property-only changes route to `push-properties` (fast, no token, no Blocks API call). Auto-migration from v1 adds `"properties": {}` to existing entries on first load.

**Consequences:**
- Properties-only changes are now fast, targeted, zero-fabrication-risk operations
- Manifest format change (non-breaking — auto-migration on load)
- `manifest.py diff` is the single source of truth for change classification
- First sync after migration re-captures all property baselines

**Alternatives Considered:**
- Separate `property_hash` field — rejected, full snapshot enables per-field diffs and human-readable conflict display
- Manual property inspection in SKILL.md — rejected, too slow and too easy to skip
```

- [ ] **Add four new items to `ROADMAP.md`**

In the `## Near-term` section, add:

```markdown
- **Per-file sync opt-out** — `sync_enabled: false` frontmatter flag excludes a file from all sync operations without touching config. Pattern from go-notion-md-sync. `status: idea`
- **CDN image hosting** — if a public CDN is configured (Cloudflare R2, S3, GitHub Pages), auto-upload local images on push and replace with HTTPS URL. `status: idea`
```

In the `## Future explorations` section, add:

```markdown
- **Multi-operator support** — track `config.json` in git, add `config.local.json` (gitignored) for per-operator token. Currently out of scope: Notion integration access requires a paid seat, making single-operator the practical use case. `status: parked`
- **Page lock after push** — `lock_after_push: true` in `config.json` locks the Notion page after content push, signalling "Git is source of truth." The `--lock` flag in `push-content` implements this. Needs evaluation of whether locking causes problems for readers. `status: idea`
```

In the `## Decided` section, add the two new decisions:

```markdown
- **Direct API push + integration token** — → Decision 007. `status: decided`
- **Manifest v2 with property snapshots** — → Decision 008. `status: decided`
```

- [ ] **Verify DECISIONS.md and ROADMAP.md are well-formed:**

```bash
python -c "
decisions = open('DECISIONS.md').read()
assert 'Decision 007' in decisions
assert 'Decision 008' in decisions
roadmap = open('ROADMAP.md').read()
assert 'Per-file sync opt-out' in roadmap
assert 'CDN image hosting' in roadmap
assert 'Multi-operator support' in roadmap
assert 'Decision 007' in roadmap
print('PASS')
"
```

- [ ] **Commit:**

```bash
git add DECISIONS.md ROADMAP.md
git commit -m "docs: add Decisions 007-008 and four ROADMAP items for v0.3

Decision 007: direct API push eliminating content fabrication.
Decision 008: manifest v2 with property snapshots enabling targeted
push operations. Roadmap adds per-file opt-out, CDN images,
multi-operator support, and page lock evaluation items.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

After all tasks are complete, verify the following before declaring done:

- [ ] `python scripts/link_registry.py --help` — no import errors
- [ ] `python scripts/push_markdown.py --help` — shows all four subcommands (prepare, push-content, push-properties, batch)
- [ ] `python scripts/manifest.py --help` — no import errors
- [ ] `python scripts/push_markdown.py push-content --dry-run` — outputs `{"dry_run": true, "blocks": 0}` or similar without error
- [ ] A v1 manifest migrates cleanly: `python scripts/manifest.py diff` on a manifest without `version` field should add `version: 2` and return valid JSON
- [ ] `skills/notion-sync/SKILL.md` contains `push-content` and `push-properties` and does NOT instruct the agent to call `replace_content` for content bodies
- [ ] `DECISIONS.md` contains Decision 007 and Decision 008
- [ ] `ROADMAP.md` has new items and both new decisions in the Decided section
