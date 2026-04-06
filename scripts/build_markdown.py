#!/usr/bin/env python3
"""
Build a markdown file with YAML frontmatter from Notion page data.

Usage:
    python build_markdown.py --notion-id ID --title TITLE --properties JSON --content CONTENT --output PATH

Or as a library:
    from build_markdown import build_file, parse_frontmatter
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def build_frontmatter(notion_id: str, title: str, properties: dict, synced_at: str = None) -> str:
    """Build YAML frontmatter string from Notion properties."""
    if synced_at is None:
        synced_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    lines = ["---"]
    lines.append(f'notion_id: "{notion_id}"')
    # Escape quotes in title for YAML
    safe_title = title.replace('"', '\\"')
    lines.append(f'title: "{safe_title}"')

    # Simple string properties
    for key in ["draft", "maturity", "short_summary"]:
        val = properties.get(key, "")
        if val:
            safe_val = str(val).replace('"', '\\"')
            lines.append(f'{key}: "{safe_val}"')
        else:
            lines.append(f'{key}: ""')

    # Array properties (category, system_change, topics)
    for key in ["category", "system_change", "topics"]:
        val = properties.get(key, [])
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = [val] if val else []
        if val:
            lines.append(f"{key}:")
            for item in val:
                lines.append(f'  - "{item}"')
        else:
            lines.append(f"{key}: []")

    # Timestamps
    for key in ["created", "last_edited"]:
        val = properties.get(key, "")
        if val:
            lines.append(f'{key}: "{val}"')

    lines.append(f'last_synced: "{synced_at}"')
    lines.append("---")

    return "\n".join(lines)


def parse_frontmatter(filepath: str) -> tuple:
    """
    Parse YAML frontmatter from a markdown file.
    Returns (properties_dict, content_without_frontmatter).
    If no frontmatter found, returns (None, full_content).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    if not text.startswith("---"):
        return None, text

    # Find closing ---
    end_match = re.search(r'\n---\s*\n', text[3:])
    if not end_match:
        return None, text

    frontmatter_str = text[4:end_match.start() + 3]  # between the --- markers
    content = text[end_match.end() + 3 + 1:]  # after closing ---\n

    # Simple YAML parser for our known structure
    props = {}
    current_array_key = None
    current_array = []

    for line in frontmatter_str.split("\n"):
        line = line.rstrip()

        # Array item
        if line.startswith("  - "):
            val = line[4:].strip().strip('"')
            current_array.append(val)
            continue

        # If we were building an array, save it
        if current_array_key:
            props[current_array_key] = current_array
            current_array_key = None
            current_array = []

        # Key-value pair
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()

            # Check for empty array marker
            if val == "[]":
                props[key] = []
            elif val == "":
                # Could be start of array block
                current_array_key = key
                current_array = []
            else:
                # Strip quotes
                val = val.strip('"')
                props[key] = val

    # Save last array if any
    if current_array_key:
        props[current_array_key] = current_array

    return props, content


def strip_old_format_properties(content: str) -> str:
    """
    Remove old-style Notion property lines from the top of a file.
    These appear as plain text between the # title and the first --- or ## heading.

    Patterns matched:
    - Tags : Value
    - Maturity: Value
    - System Change: Value
    - Date: Month Day, Year Time
    - Short Summary: Value
    - Draft: Value
    """
    lines = content.split("\n")
    result = []
    in_header = True
    found_title = False
    property_patterns = [
        r'^Tags?\s*:\s',
        r'^Maturity\s*:\s',
        r'^System Change\s*:\s',
        r'^Date\s*:\s',
        r'^Short Summary\s*:\s',
        r'^Draft\s*:\s',
        r'^Created\s*:\s',
    ]

    for line in lines:
        if in_header:
            # Keep the title line
            if line.startswith("# ") and not found_title:
                result.append(line)
                found_title = True
                continue

            # Skip blank lines in the header zone
            if found_title and line.strip() == "":
                continue

            # Check if line matches a property pattern
            is_property = any(re.match(p, line) for p in property_patterns)
            if is_property:
                continue

            # If we hit a --- or ## or # or actual content, we're past the header
            if found_title and (line.startswith("---") or line.startswith("#") or line.strip()):
                in_header = False
                if line.startswith("---"):
                    # Skip the divider that typically separates properties from content
                    continue
                # Ensure blank line between title and content
                if result and result[-1].strip():
                    result.append("")
                result.append(line)
        else:
            result.append(line)

    return "\n".join(result)


def content_hash(content: str) -> str:
    """Generate a SHA-256 hash of content for change detection."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def build_file(notion_id: str, title: str, properties: dict,
               content: str, output_path: str, synced_at: str = None) -> str:
    """
    Build a complete markdown file with YAML frontmatter and write it.
    Returns the content hash.
    """
    frontmatter = build_frontmatter(notion_id, title, properties, synced_at)

    # Ensure content starts with the title heading
    content_stripped = content.strip()
    if not content_stripped.startswith(f"# {title}") and not content_stripped.startswith("# "):
        full_content = f"{frontmatter}\n\n# {title}\n\n{content_stripped}\n"
    else:
        full_content = f"{frontmatter}\n\n{content_stripped}\n"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    return content_hash(content_stripped)


def slugify(title: str) -> str:
    """Convert a title to a kebab-case slug for use as a filename."""
    s = title.lower()
    # Handle special cases
    s = s.replace("d/acc", "d-acc").replace("local/acc", "local-acc")
    s = s.replace("/", "-").replace("&", "and")
    s = s.replace("'", "").replace("\u2019", "").replace("\u2018", "")
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = s.replace("(", "").replace(")", "")
    s = s.replace(",", "").replace(":", "").replace(";", "")
    s = s.replace(".", "").replace("?", "").replace("!", "")
    s = s.replace("\u00e7", "c")  # ç -> c (e.g. Curaçao)
    s = re.sub(r'[^a-z0-9-]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')


def generate_filename(title: str, notion_id: str = None) -> str:
    """Generate a kebab-case filename from title."""
    return slugify(title) + ".md"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build markdown file with YAML frontmatter")
    parser.add_argument("--notion-id", required=True, help="32-char Notion page ID")
    parser.add_argument("--title", required=True, help="Page title")
    parser.add_argument("--properties", required=True, help="JSON string of properties")
    parser.add_argument("--content", default="", help="Markdown content (or use --content-file)")
    parser.add_argument("--content-file", help="Path to file containing markdown content")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--synced-at", help="ISO timestamp for last_synced (default: now)")

    args = parser.parse_args()

    props = json.loads(args.properties)

    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as f:
            md_content = f.read()
    else:
        md_content = args.content

    h = build_file(args.notion_id, args.title, props, md_content, args.output, args.synced_at)
    print(json.dumps({"output": args.output, "content_hash": h}))
