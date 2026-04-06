#!/usr/bin/env python3
"""
Manage the .notion-sync/manifest.json file.

Usage:
    # Initialize a new manifest
    python manifest.py init --data-source-id ID --manifest-path PATH

    # Get a page entry
    python manifest.py get --page-id ID --manifest-path PATH

    # Update a page entry
    python manifest.py update --page-id ID --manifest-path PATH \
        --local-file PATH --title TITLE --last-notion-edit TS --content-hash HASH

    # Remove a page entry
    python manifest.py remove --page-id ID --manifest-path PATH

    # List all pages
    python manifest.py list --manifest-path PATH

    # Get last sync time
    python manifest.py last-sync --manifest-path PATH

    # Set last sync time
    python manifest.py set-last-sync --manifest-path PATH --timestamp TS
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_MANIFEST_PATH = ".notion-sync/manifest.json"
DEFAULT_DATA_SOURCE_ID = "2babf304-370a-81ef-b829-000b7c9b81a5"


def load_manifest(path: str) -> dict:
    """Load manifest from file, or return empty structure."""
    p = Path(path)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "data_source_id": DEFAULT_DATA_SOURCE_ID,
        "last_full_sync": None,
        "pages": {}
    }


def save_manifest(manifest: dict, path: str):
    """Save manifest to file, creating parent dirs if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def cmd_init(args):
    manifest = {
        "data_source_id": args.data_source_id or DEFAULT_DATA_SOURCE_ID,
        "last_full_sync": None,
        "pages": {}
    }
    save_manifest(manifest, args.manifest_path)
    print(json.dumps({"status": "initialized", "path": args.manifest_path}))


def cmd_get(args):
    manifest = load_manifest(args.manifest_path)
    page = manifest.get("pages", {}).get(args.page_id)
    if page:
        print(json.dumps(page))
    else:
        print(json.dumps({"error": "not_found", "page_id": args.page_id}))


def cmd_update(args):
    manifest = load_manifest(args.manifest_path)
    synced_at = now_iso()
    manifest["pages"][args.page_id] = {
        "local_file": args.local_file,
        "title": args.title,
        "last_notion_edit": args.last_notion_edit,
        "last_synced": synced_at,
        "content_hash": args.content_hash or ""
    }
    save_manifest(manifest, args.manifest_path)
    print(json.dumps({"status": "updated", "page_id": args.page_id, "synced_at": synced_at}))


def cmd_remove(args):
    manifest = load_manifest(args.manifest_path)
    if args.page_id in manifest.get("pages", {}):
        del manifest["pages"][args.page_id]
        save_manifest(manifest, args.manifest_path)
        print(json.dumps({"status": "removed", "page_id": args.page_id}))
    else:
        print(json.dumps({"status": "not_found", "page_id": args.page_id}))


def cmd_list(args):
    manifest = load_manifest(args.manifest_path)
    pages = manifest.get("pages", {})
    result = []
    for pid, info in pages.items():
        result.append({
            "page_id": pid,
            "title": info.get("title", ""),
            "local_file": info.get("local_file", ""),
            "last_notion_edit": info.get("last_notion_edit", ""),
            "last_synced": info.get("last_synced", "")
        })
    print(json.dumps({"count": len(result), "pages": result}))


def cmd_last_sync(args):
    manifest = load_manifest(args.manifest_path)
    ts = manifest.get("last_full_sync")
    print(json.dumps({"last_full_sync": ts}))


def cmd_set_last_sync(args):
    manifest = load_manifest(args.manifest_path)
    manifest["last_full_sync"] = args.timestamp or now_iso()
    save_manifest(manifest, args.manifest_path)
    print(json.dumps({"status": "updated", "last_full_sync": manifest["last_full_sync"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage notion-sync manifest")
    parser.add_argument("--manifest-path", default=DEFAULT_MANIFEST_PATH)
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init")
    p_init.add_argument("--data-source-id")

    p_get = sub.add_parser("get")
    p_get.add_argument("--page-id", required=True)

    p_update = sub.add_parser("update")
    p_update.add_argument("--page-id", required=True)
    p_update.add_argument("--local-file", required=True)
    p_update.add_argument("--title", required=True)
    p_update.add_argument("--last-notion-edit", required=True)
    p_update.add_argument("--content-hash")

    p_remove = sub.add_parser("remove")
    p_remove.add_argument("--page-id", required=True)

    p_list = sub.add_parser("list")

    p_ls = sub.add_parser("last-sync")

    p_sls = sub.add_parser("set-last-sync")
    p_sls.add_argument("--timestamp")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "get":
        cmd_get(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "last-sync":
        cmd_last_sync(args)
    elif args.command == "set-last-sync":
        cmd_set_last_sync(args)
    else:
        parser.print_help()
        sys.exit(1)
