#!/usr/bin/env python3
"""
Prepare local markdown files for pushing to Notion.

Reads markdown files, strips YAML frontmatter, converts local markdown links to Notion URLs,
and computes content hashes. Outputs prepared markdown ready for Notion API submission.

Usage:
    # Single file: read, convert links, compute hash, write to stdout
    python push_markdown.py prepare --file research/kwaxala.md
    python push_markdown.py prepare --file research/kwaxala.md --output /tmp/kwaxala.md

    # Batch mode: find changed files (hash mismatch with manifest), prepare all
    python push_markdown.py batch --folders research/ report/ --output-dir .notion-sync/push-staging/

Examples:
    # Check what would be pushed (dry-run with verbose output)
    python push_markdown.py prepare --file research/test.md 2>&1 | head

    # Batch process and see which files changed
    python push_markdown.py batch --folders research/ 2>&1 | python -m json.tool
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from link_registry import LinkRegistry

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


def _clear_page_blocks(page_id: str, token: str) -> int:
    """Delete all existing blocks from a page, skipping archived ones."""
    deleted = skipped = 0
    cursor = None
    while True:
        path = f"/blocks/{page_id}/children"
        if cursor:
            path += f"?start_cursor={cursor}"
        result = _notion_request("GET", path, token)
        blocks = result.get("results", [])
        if not blocks:
            break
        for block in blocks:
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
        if result.get("has_more"):
            cursor = result.get("next_cursor")
        else:
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


def cmd_push_content(args):
    """Handle 'push-content' subcommand: push staging file to Notion via Blocks API."""
    if args.dry_run:
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
    token = _load_token()
    if not token:
        print("Error: NOTION_TOKEN not found.\nAdd it to .notion-sync/.env — run /notion-setup for instructions.", file=sys.stderr)
        sys.exit(1)

    if not args.file:
        print("Error: --file is required for live push", file=sys.stderr)
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

    if args.lock:
        _notion_request("PATCH", f"/pages/{page_id}", token, {"locked": True})
        print("  Page locked", file=sys.stderr)

    print(json.dumps({"status": "pushed", "page_id": page_id, "blocks_pushed": pushed}))


def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from markdown."""
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


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


def content_hash(body: str) -> str:
    """Compute SHA-256 content hash (first 16 hex chars) of markdown body."""
    return "sha256:" + hashlib.sha256(body.strip().encode('utf-8')).hexdigest()[:16]


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


def cmd_batch(args):
    """Handle 'batch' subcommand: multi-file mode with change detection."""
    folders = [Path(f) for f in args.folders]
    output_dir = Path(args.output_dir)
    registry_path = Path(args.registry_path)
    manifest_path = Path(args.manifest_path)

    # Load registry and manifest
    registry = LinkRegistry(registry_path=registry_path)
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError):
            manifest = {}

    # Collect all .md files
    files_to_process = []
    for folder in folders:
        if folder.exists():
            files_to_process.extend(folder.glob('**/*.md'))

    # Build file_path → content_hash lookup from manifest pages
    manifest_pages = manifest.get("pages", {}) if isinstance(manifest, dict) else {}
    file_to_hash = {
        entry.get("local_file"): entry.get("content_hash", "")
        for entry in manifest_pages.values()
        if entry.get("local_file")
    }

    changed_files = []
    unchanged_files = []

    for file_path in sorted(files_to_process):
        converted_body, links_converted, links_unresolved, hash_value = prepare_file(
            file_path, registry
        )

        # Check if content changed (compare hash with manifest)
        file_str = str(file_path)
        manifest_hash = file_to_hash.get(file_str, "")

        if hash_value == manifest_hash:
            unchanged_files.append(file_str)
        else:
            # File changed: prepare and write to staging
            output_dir.mkdir(parents=True, exist_ok=True)
            relative_path = file_path.relative_to(Path.cwd())
            output_path = output_dir / relative_path.name
            output_path.write_text(converted_body, encoding='utf-8')

            changed_files.append({
                "file": file_str,
                "content_hash": hash_value,
                "links_converted": links_converted,
                "links_unresolved": links_unresolved,
            })

    # Print JSON summary to stderr
    summary = {
        "changed": len(changed_files),
        "unchanged": len(unchanged_files),
        "files": changed_files,
    }
    print(json.dumps(summary), file=sys.stderr)


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


def main():
    parser = argparse.ArgumentParser(
        description="Prepare local markdown files for pushing to Notion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--registry-path",
        default=".notion-sync/link-registry.json",
        help="Path to link registry JSON file (default: .notion-sync/link-registry.json)",
    )
    parser.add_argument(
        "--manifest-path",
        default=".notion-sync/manifest.json",
        help="Path to manifest JSON file (default: .notion-sync/manifest.json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'prepare' subcommand
    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare single file for pushing to Notion",
    )
    prepare_parser.add_argument(
        "--file",
        required=True,
        help="Path to markdown file to prepare",
    )
    prepare_parser.add_argument(
        "--output",
        help="Output file path (default: stdout)",
    )
    prepare_parser.set_defaults(func=cmd_prepare)

    # 'batch' subcommand
    batch_parser = subparsers.add_parser(
        "batch",
        help="Batch process changed files from folders",
    )
    batch_parser.add_argument(
        "--folders",
        nargs="+",
        required=True,
        help="Folders to scan for markdown files",
    )
    batch_parser.add_argument(
        "--output-dir",
        default=".notion-sync/push-staging/",
        help="Output directory for prepared files (default: .notion-sync/push-staging/)",
    )
    batch_parser.set_defaults(func=cmd_batch)

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
        help="Lock the Notion page after push",
    )
    push_content_parser.set_defaults(func=cmd_push_content)

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
