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

    # Bootstrap manifest from local files
    python manifest.py bootstrap --folders research/ report/ --manifest-path PATH

    # Show diff between local and manifest state
    python manifest.py diff --manifest-path PATH

    # Discover untracked local files
    python manifest.py discover --folders research/ report/ --manifest-path PATH
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from build_markdown import parse_frontmatter, content_hash
from link_registry import LinkRegistry


DEFAULT_MANIFEST_PATH = ".notion-sync/manifest.json"


def save_manifest(manifest: dict, path: str):
    """Save manifest to file, creating parent dirs if needed."""
    manifest.setdefault("version", 2)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


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


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def cmd_init(args):
    if not args.data_source_id:
        print(json.dumps({"error": "data_source_id is required"}), file=sys.stderr)
        sys.exit(1)
    manifest = {
        "data_source_id": args.data_source_id,
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


def cmd_bootstrap(args):
    """Bootstrap manifest by matching local files to Notion pages."""
    manifest = load_manifest(args.manifest_path)
    pages = manifest.get("pages", {})

    matched = 0
    unmatched_local = []
    unmatched_notion = set(title for page in pages.values() for title in [page.get("title", "")] if title)

    # Walk all .md files in specified folders
    for folder in args.folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue

        for md_file in folder_path.glob("**/*.md"):
            # Parse frontmatter to get notion_id and title
            props, content = parse_frontmatter(str(md_file))

            if props is None:
                unmatched_local.append(str(md_file))
                continue

            notion_id = props.get("notion_id")
            title = props.get("title")

            # Matching strategy
            matched_page_id = None

            # a. Match by notion_id if present
            if notion_id and notion_id in pages:
                matched_page_id = notion_id
            # b. Match by title if present
            elif title:
                for page_id, page_info in pages.items():
                    if page_info.get("title") == title:
                        matched_page_id = page_id
                        break

            if matched_page_id:
                # Update the manifest entry
                local_file_rel = str(md_file)
                content_body = content  # recompute hash on the body
                computed_hash = content_hash(content_body)

                pages[matched_page_id]["local_file"] = local_file_rel
                pages[matched_page_id]["content_hash"] = computed_hash
                pages[matched_page_id]["last_synced"] = pages[matched_page_id].get("last_notion_edit", now_iso())
                if "properties" not in pages[matched_page_id]:
                    pages[matched_page_id]["properties"] = {}

                matched += 1
                if title and title in unmatched_notion:
                    unmatched_notion.discard(title)
            else:
                unmatched_local.append(str(md_file))

    manifest["pages"] = pages
    save_manifest(manifest, args.manifest_path)

    print(json.dumps({
        "matched": matched,
        "unmatched_local": unmatched_local,
        "unmatched_notion": sorted(list(unmatched_notion)),
        "total_pages": len(pages)
    }))


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


def cmd_discover(args):
    """Discover untracked local files."""
    manifest = load_manifest(args.manifest_path)
    pages = manifest.get("pages", {})

    # Build set of tracked local files
    tracked_files = set()
    for page_info in pages.values():
        local_file = page_info.get("local_file")
        if local_file:
            tracked_files.add(local_file)

    untracked = []

    # Walk all .md files in specified folders
    for folder in args.folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            continue

        for md_file in folder_path.glob("**/*.md"):
            file_path_str = str(md_file)
            if file_path_str not in tracked_files:
                # Try to read title from frontmatter
                title = None
                try:
                    props, _ = parse_frontmatter(file_path_str)
                    if props:
                        title = props.get("title")
                except Exception:
                    pass

                # Fall back to filename if no title
                if not title:
                    title = md_file.stem.replace("-", " ").title()

                untracked.append({
                    "file": file_path_str,
                    "title": title
                })

    print(json.dumps({
        "untracked": sorted(untracked, key=lambda x: x["file"]),
        "count": len(untracked)
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage notion-sync manifest")
    parser.add_argument("--manifest-path", default=DEFAULT_MANIFEST_PATH)
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init")
    p_init.add_argument("--data-source-id", required=True)

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

    p_bootstrap = sub.add_parser("bootstrap")
    p_bootstrap.add_argument("--folders", nargs="+", required=True, help="Folders to scan for .md files")

    p_diff = sub.add_parser("diff")

    p_discover = sub.add_parser("discover")
    p_discover.add_argument("--folders", nargs="+", required=True, help="Folders to scan for .md files")

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
    elif args.command == "bootstrap":
        cmd_bootstrap(args)
    elif args.command == "diff":
        cmd_diff(args)
    elif args.command == "discover":
        cmd_discover(args)
    else:
        parser.print_help()
        sys.exit(1)
