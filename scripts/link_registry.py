#!/usr/bin/env python3
"""
Link Registry CLI Tool

Manages a bidirectional link registry between local markdown files and Notion page IDs.

Usage examples:
    # Build registry from manifest
    python link_registry.py build

    # Lookup page ID for a file
    python link_registry.py lookup --file research/kwaxala.md

    # Lookup file for a page ID
    python link_registry.py lookup --page 33ebf304370a81ffb1dafefd9c510128

    # Convert markdown links (push direction)
    python link_registry.py convert-links --direction push < input.md > output.md

    # Convert markdown links from file (pull direction)
    python link_registry.py convert-links --direction pull --content-file input.md

    # Use custom registry path
    python link_registry.py build --registry-path custom/path/links.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


class LinkRegistry:
    """Manages bidirectional file <-> Notion page ID mappings."""

    def __init__(self, registry_path: Path = None, manifest_path: Path = None):
        """
        Initialize LinkRegistry.

        Args:
            registry_path: Path to link-registry.json. Defaults to .notion-sync/link-registry.json
            manifest_path: Path to manifest.json. Defaults to .notion-sync/manifest.json
        """
        if registry_path is None:
            registry_path = Path(".notion-sync/link-registry.json")
        if manifest_path is None:
            manifest_path = Path(".notion-sync/manifest.json")

        self.registry_path = Path(registry_path)
        self.manifest_path = Path(manifest_path)
        self.by_file: Dict[str, str] = {}
        self.by_page: Dict[str, str] = {}

        # Load existing registry if it exists
        if self.registry_path.exists():
            self._load_registry()

    def _load_registry(self) -> None:
        """Load registry from disk."""
        try:
            with open(self.registry_path, "r") as f:
                data = json.load(f)
                self.by_file = data.get("by_file", {})
                self.by_page = data.get("by_page", {})
        except (json.JSONDecodeError, IOError):
            self.by_file = {}
            self.by_page = {}

    def _save_registry(self) -> None:
        """Save registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, "w") as f:
            json.dump({"by_file": self.by_file, "by_page": self.by_page}, f, indent=2)

    def build(self) -> int:
        """
        Build registry from manifest.json.

        Reads manifest.json, extracts all page entries with both local_file and a page ID,
        writes bidirectional mappings to link-registry.json.

        Returns:
            Number of entries built.

        Raises:
            FileNotFoundError: If manifest.json does not exist.
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found at {self.manifest_path}")

        with open(self.manifest_path, "r") as f:
            manifest = json.load(f)

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

        self._save_registry()
        return count

    def lookup_file(self, file_path: str) -> Optional[str]:
        """
        Look up page ID for a local file.

        Args:
            file_path: Path to local markdown file.

        Returns:
            Page ID or None if not found.
        """
        return self.by_file.get(file_path)

    def lookup_page(self, page_id: str) -> Optional[str]:
        """
        Look up local file for a page ID.

        Args:
            page_id: Notion page ID.

        Returns:
            File path or None if not found.
        """
        return self.by_page.get(page_id)

    def convert_links(
        self, content: str, direction: str
    ) -> Tuple[str, Dict[str, int]]:
        """
        Convert markdown links between local files and Notion URLs.

        Args:
            content: Markdown content to convert.
            direction: Either "push" (local -> Notion) or "pull" (Notion -> local).

        Returns:
            Tuple of (converted content, stats dict with links_converted and links_unresolved).

        Raises:
            ValueError: If direction is not "push" or "pull".
        """
        if direction not in ("push", "pull"):
            raise ValueError("direction must be 'push' or 'pull'")

        converted = content
        stats = {"links_converted": 0, "links_unresolved": 0}

        if direction == "push":
            # Convert [text](filename.md) -> [text](https://www.notion.so/PAGE_ID)
            # Pattern: [text](path/to/file.md) - match local file paths
            pattern = r"\[([^\]]+)\]\(([^)]+\.md)\)"

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

            converted = re.sub(pattern, replace_fn, converted)

        elif direction == "pull":
            # Convert [text](https://www.notion.so/PAGE_ID) -> [text](filename.md)
            # Pattern: [text](https://www.notion.so/PAGE_ID)
            pattern = r"\[([^\]]+)\]\(https://www\.notion\.so/([a-f0-9]+)\)"

            def replace_fn(match):
                text = match.group(1)
                page_id = match.group(2)

                file_path = self.lookup_page(page_id)
                if file_path:
                    stats["links_converted"] += 1
                    return f"[{text}]({file_path})"
                else:
                    stats["links_unresolved"] += 1
                    # Leave as-is if not found
                    return match.group(0)

            converted = re.sub(pattern, replace_fn, converted)

        return converted, stats


def cmd_build(args) -> None:
    """Execute build command."""
    registry = LinkRegistry(
        registry_path=args.registry_path, manifest_path=args.manifest_path
    )
    entries = registry.build()
    print(json.dumps({"status": "built", "entries": entries}))


def cmd_lookup(args) -> None:
    """Execute lookup command."""
    registry = LinkRegistry(
        registry_path=args.registry_path, manifest_path=args.manifest_path
    )

    if args.file:
        page_id = registry.lookup_file(args.file)
        if page_id:
            print(json.dumps({"page_id": page_id}))
        else:
            print(json.dumps({"error": "not_found"}))
    elif args.page:
        file_path = registry.lookup_page(args.page)
        if file_path:
            print(json.dumps({"local_file": file_path}))
        else:
            print(json.dumps({"error": "not_found"}))


def cmd_convert_links(args) -> None:
    """Execute convert-links command."""
    registry = LinkRegistry(
        registry_path=args.registry_path, manifest_path=args.manifest_path
    )

    # Read content from file or stdin
    if args.content_file:
        with open(args.content_file, "r") as f:
            content = f.read()
    else:
        content = sys.stdin.read()

    # Convert links
    converted, stats = registry.convert_links(content, args.direction)

    # Output converted content to stdout
    print(converted, end="")

    # Output stats to stderr
    print(json.dumps(stats), file=sys.stderr)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Manage bidirectional link registry between local files and Notion pages"
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=None,
        help="Path to link-registry.json (default: .notion-sync/link-registry.json)",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=None,
        help="Path to manifest.json (default: .notion-sync/manifest.json)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # build command
    subparsers.add_parser("build", help="Build registry from manifest")

    # lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Look up file or page ID")
    lookup_group = lookup_parser.add_mutually_exclusive_group(required=True)
    lookup_group.add_argument(
        "--file", type=str, help="Look up page ID for a local file"
    )
    lookup_group.add_argument(
        "--page", type=str, help="Look up local file for a page ID"
    )

    # convert-links command
    convert_parser = subparsers.add_parser(
        "convert-links", help="Convert markdown links between local and Notion URLs"
    )
    convert_parser.add_argument(
        "--direction",
        type=str,
        required=True,
        choices=["push", "pull"],
        help="Conversion direction: 'push' (local->Notion) or 'pull' (Notion->local)",
    )
    convert_parser.add_argument(
        "--content-file",
        type=Path,
        help="Read content from file instead of stdin",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "build":
            cmd_build(args)
        elif args.command == "lookup":
            cmd_lookup(args)
        elif args.command == "convert-links":
            cmd_convert_links(args)
    except FileNotFoundError as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
