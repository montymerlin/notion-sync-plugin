# notion-sync

Bidirectional sync between Notion databases and local markdown files for Claude Cowork.

## What it does

Keeps a Notion database and a local folder of markdown files in sync. Changes flow in both directions: edit locally and push to Notion, or edit in Notion and pull to your local files. Conflicts are detected and resolved with your input — never auto-resolved.

Each markdown file has YAML frontmatter that maps to Notion page properties. The sync engine tracks changes via content hashing and timestamps, so it only transfers what's actually changed. Multiple local folders can sync to the same Notion database.

## Skills

| Skill | Runtime ID | Trigger phrases | What it does |
|-------|------------|-----------------|--------------|
| `notion-setup` | `notion-sync:notion-setup` | "set up notion sync", "connect notion", "link to notion" | First-time configuration — connects a Notion database, maps properties to YAML fields, creates config and manifest files |
| `sync` | `notion-sync:sync` | "sync", "notion sync", "pull from notion", "push to notion" | Bidirectional sync — detects changes, shows a plan, resolves conflicts, executes pulls and pushes |

> **Note:** in v0.4.0 the sync skill's directory was renamed from `notion-sync/` to `sync/` to clean up the doubled runtime ID (`notion-sync:notion-sync` → `notion-sync:sync`). If you've memorized an older slash command or invocation, update it accordingly.

## How it works

1. **Setup** (`notion-sync:notion-setup`): Connect a Notion database, choose a local folder, and map Notion properties to YAML frontmatter fields. Creates `.notion-sync/config.json` (shareable settings) and `.notion-sync/manifest.json` (personal sync state).

2. **Sync** (`notion-sync:sync`): Compares local files and Notion pages to detect changes on both sides. Presents a unified plan (N to pull, N to push, N conflicts). Resolves conflicts one by one with your input. Executes and updates the manifest.

## File structure

After setup, your project will have:

```
your-project/
├── .notion-sync/
│   ├── config.json          # Database ID, folders, property map (share this)
│   ├── manifest.json        # Page tracking and sync state (personal)
│   └── link-registry.json   # Bidirectional file↔page ID map (auto-generated)
├── research/                # Synced folder(s)
│   ├── page-one.md          # Synced files with YAML frontmatter
│   ├── page-two.md
│   └── ...
├── report/                  # Additional synced folder (optional)
│   └── ...
```

## Requirements

- **Notion MCP** — the Notion connector must be available in your Cowork session or Claude Code CLI environment. The sync skill uses `notion-search`, `notion-fetch`, `notion-update-page`, and `notion-create-pages`.
- **git-plugin** (recommended) — the sync workflow uses `/commit` for safe, structured commits after sync operations.

## Installation

See [SETUP.md](SETUP.md) for installation steps, compatibility matrix, credential setup, and known quirks across all hosts (Cowork, Claude Code CLI, API direct, etc.).

## Collaboration notes

When sharing a repo that uses notion-sync:

- **Share** `config.json` — it defines the database connection and property mappings that everyone needs
- **Gitignore** `.notion-sync/` entirely if only one person runs the sync. If sharing, gitignore `manifest.json` and `link-registry.json` but track `config.json`
- Each collaborator needs their own Notion MCP connection with access to the shared database
- Collaborators who don't use Notion can still edit the markdown files directly and push via git — the sync is optional tooling, not a requirement

## Helper scripts

The `scripts/` directory contains Python utilities used by the sync engine:

- **`build_markdown.py`** — builds markdown files with YAML frontmatter from Notion data (pull direction), parses frontmatter, generates kebab-case slugs, computes content hashes
- **`push_markdown.py`** — prepares local markdown for Notion push: strips frontmatter, converts local links to Notion URLs, computes content hash. Supports single-file and batch modes.
- **`manifest.py`** — CLI for managing the manifest: init, get, update, remove, list, bootstrap (match local files to Notion pages), diff (dry-run change preview), discover (find untracked files)
- **`link_registry.py`** — maintains a bidirectional map between local filenames and Notion page IDs. Handles link conversion in both directions (push and pull). Eliminates ad-hoc slug matching.

These can be used standalone or by the sync skill.

## License

MIT
