# notion-cowork

Bidirectional sync between Notion databases and local markdown files for Claude Cowork.

## What it does

Keeps a Notion database and a local folder of markdown files in sync. Changes flow in both directions: edit locally and push to Notion, or edit in Notion and pull to your local files. Conflicts are detected and resolved with your input — never auto-resolved.

Each markdown file has YAML frontmatter that maps to Notion page properties. The sync engine tracks changes via content hashing and timestamps, so it only transfers what's actually changed.

## Skills

| Skill | Trigger phrases | What it does |
|-------|----------------|--------------|
| `/notion-setup` | "set up notion sync", "connect notion", "link to notion" | First-time configuration — connects a Notion database, maps properties to YAML fields, creates config and manifest files |
| `/notion-sync` | "sync", "notion sync", "pull from notion", "push to notion" | Bidirectional sync — detects changes, shows a plan, resolves conflicts, executes pulls and pushes |

## How it works

1. **Setup** (`/notion-setup`): Connect a Notion database, choose a local folder, and map Notion properties to YAML frontmatter fields. Creates `.notion-sync/config.json` (shareable settings) and `.notion-sync/manifest.json` (personal sync state).

2. **Sync** (`/notion-sync`): Compares local files and Notion pages to detect changes on both sides. Presents a unified plan (N to pull, N to push, N conflicts). Resolves conflicts one by one with your input. Executes and updates the manifest.

## File structure

After setup, your project will have:

```
your-project/
├── .notion-sync/
│   ├── config.json      # Database ID, sync folder, property map (share this)
│   └── manifest.json    # Page tracking and sync state (personal, gitignore this)
├── research/            # (or whatever folder you chose)
│   ├── page-one.md      # Synced files with YAML frontmatter
│   ├── page-two.md
│   └── ...
```

## Requirements

- **Notion MCP** — the Notion connector must be available in your Cowork session or Claude Code CLI environment. The sync skill uses `notion-search`, `notion-fetch`, `notion-update-page`, and `notion-create-pages`.
- **git-cowork plugin** (recommended) — the sync workflow uses `/commit` for safe, structured commits after sync operations.

## Installation

### Claude Desktop (Cowork)

Open the `.plugin` file in Claude Desktop, or install from the plugin marketplace.

### Claude Code CLI

Copy the skills to your global or project skills directory:

```bash
git clone https://github.com/montymerlin/notion-cowork-plugin.git
cp -r notion-cowork-plugin/skills/* ~/.claude/skills/
cp -r notion-cowork-plugin/scripts/ ~/.claude/scripts/notion-sync/
```

## Collaboration notes

When sharing a repo that uses notion-sync:

- **Share** `config.json` — it defines the database connection and property mappings that everyone needs
- **Gitignore** `manifest.json` — it contains personal sync timestamps and content hashes that differ per user
- Each collaborator needs their own Notion MCP connection with access to the shared database
- Collaborators who don't use Notion can still edit the markdown files directly and push via git — the sync is optional tooling, not a requirement

## Helper scripts

The `scripts/` directory contains Python utilities used by the sync engine:

- **`build_markdown.py`** — builds markdown files with YAML frontmatter, parses frontmatter, generates kebab-case slugs, computes content hashes
- **`manifest.py`** — CLI for managing the manifest (init, get, update, remove, list pages)

These can be used standalone or by the sync skill.

## License

MIT
