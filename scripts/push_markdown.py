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
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from markdown."""
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            return content[end + 3:].strip()
    return content.strip()


def content_hash(body: str) -> str:
    """Compute SHA-256 content hash (first 16 hex chars) of markdown body."""
    return "sha256:" + hashlib.sha256(body.strip().encode('utf-8')).hexdigest()[:16]


def load_link_registry(registry_path: Path) -> Dict:
    """Load link registry from JSON file."""
    if not registry_path.exists():
        return {"by_file": {}}
    try:
        with open(registry_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"by_file": {}}


def convert_links(body: str, registry: Dict) -> Tuple[str, int, int]:
    """
    Convert local markdown links to Notion URLs.

    Looks for [text](filename.md) patterns where filename.md is a relative .md link.
    Uses registry['by_file'] to map filenames to Notion page URLs.

    Returns:
        Tuple of (converted_body, links_converted_count, links_unresolved_count)
    """
    by_file = registry.get("by_file", {})
    converted = 0
    unresolved = 0

    # Pattern: [text](path.md) where path.md doesn't start with http and doesn't have anchors
    # Match relative .md links only (not http://, not #anchor only)
    pattern = r'\[([^\]]+)\]\(([a-zA-Z0-9\-_./]+\.md)\)'

    def replace_link(match):
        nonlocal converted, unresolved
        text = match.group(1)
        filename = match.group(2)

        # Try to find in registry: first with folder prefix, then without
        notion_url = None

        if filename in by_file:
            notion_url = by_file[filename].get("notion_url")
        else:
            # Try matching just the filename part (last component)
            filename_only = filename.split('/')[-1]
            for reg_filename, reg_data in by_file.items():
                if reg_filename.endswith(filename_only):
                    notion_url = reg_data.get("notion_url")
                    break

        if notion_url:
            converted += 1
            return f"[{text}]({notion_url})"
        else:
            unresolved += 1
            return match.group(0)  # Leave unchanged

    converted_body = re.sub(pattern, replace_link, body)
    return converted_body, converted, unresolved


def prepare_file(
    file_path: Path,
    registry: Dict,
) -> Tuple[str, int, int, str]:
    """
    Prepare a single markdown file for Notion.

    Returns:
        Tuple of (converted_body, links_converted, links_unresolved, hash)
    """
    content = file_path.read_text(encoding='utf-8')
    body = strip_frontmatter(content)
    converted_body, links_converted, links_unresolved = convert_links(body, registry)
    hash_value = content_hash(converted_body)

    return converted_body, links_converted, links_unresolved, hash_value


def cmd_prepare(args):
    """Handle 'prepare' subcommand: single file mode."""
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    registry_path = Path(args.registry_path)
    registry = load_link_registry(registry_path)

    converted_body, links_converted, links_unresolved, hash_value = prepare_file(
        file_path, registry
    )

    # Write body to output or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(converted_body, encoding='utf-8')
    else:
        print(converted_body)

    # Print JSON summary to stderr
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
    registry = load_link_registry(registry_path)
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

    changed_files = []
    unchanged_files = []

    for file_path in sorted(files_to_process):
        # Read frontmatter to extract notion_id
        content = file_path.read_text(encoding='utf-8')
        body = strip_frontmatter(content)
        converted_body, links_converted, links_unresolved, hash_value = prepare_file(
            file_path, registry
        )

        # Check if content changed (compare hash with manifest)
        file_str = str(file_path)
        manifest_entry = manifest.get(file_str, {})
        manifest_hash = manifest_entry.get("content_hash")

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
