# Setup Guide — notion-sync

Bidirectional sync between Notion databases and local markdown files with guided setup, change detection, conflict resolution, and content format conversion.

---

## Quick Install (for AI agents)

If you're an AI agent installing this plugin, **detect the host first**, then pick the matching path. Only ask the user the questions explicitly listed below.

```
1. Detect host:
   ├── Cowork (Claude Desktop, sandboxed)
   │     → Path A: Cowork upload (no questions needed)
   │     → Notion MCP must already be connected; if not, walk user through it
   │
   ├── Claude Code CLI (terminal, has `claude` command)
   │     → Path B: claude plugins install
   │     → ASK USER: "Install globally (every project) or locally (this project)?"
   │       • global → `claude plugins install github.com/montymerlin/notion-sync-plugin`
   │       • local  → symlink `ln -s <path> ./.claude/plugins/notion-sync`
   │     → ASK USER (if no NOTION_API_KEY in env): "Provide your Notion integration token"
   │
   ├── Codex / Cursor / VS Code
   │     → NOT SUPPORTED. Tell the user; suggest Cowork or Claude Code instead.
   │       (Plugin uses Claude-host-specific Notion MCP wrappers; no Codex equivalent.)
   │
   └── Unknown / custom Agent SDK host
         → Path C: Standard plugin loader; verify Python 3.8+ and a Notion MCP-equivalent are available first.
```

**Host detection signals:**
- `$CLAUDE_COWORK == "1"` or `mount | grep virtiofs` matches → Cowork
- `command -v claude` succeeds and not Cowork → Claude Code CLI
- Otherwise → ask the user which environment they're in.

**Pre-install dependencies:**
- Python 3.8+ on PATH (no external Python deps; stdlib only)
- A Notion API integration token (instructions below) — required for any host
- Notion MCP connector configured in the host (built into Cowork; via `claude mcp add` for Claude Code CLI)

If those aren't satisfied, surface to the user before proceeding.

---

## Compatibility Matrix

| Host                       | Status      | Notes                                                    |
|----------------------------|-------------|----------------------------------------------------------|
| Cowork (Claude Desktop)    | ✓           | Upload `.plugin` file; skills appear in `/` menu         |
| Claude Code CLI            | ✓           | Git-based install; skills invoked via natural language   |
| Codex (OpenAI)             | ✗           | Not supported — Cowork/Claude Code only                  |
| Cursor / VS Code           | ✗ MCP only  | No skill support in these editors                        |
| Claude Agent SDK           | ✓           | Standard plugin loader                                   |
| Anthropic API direct       | partial     | Manual tool wiring required                              |

---

## Installation

### Cowork (Claude Desktop)

**Best UX**: one-click install, slash-command discovery, automatic Notion MCP loading.

You need a `.plugin` zip to upload. Get one of these three ways:

**Option 1 — pre-built release (preferred when available):**
Download `notion-sync-<version>.plugin` from the GitHub Releases page of `montymerlin/notion-sync-plugin`.

**Option 2 — built locally from this repo:**

```bash
git clone https://github.com/montymerlin/notion-sync-plugin.git
cd notion-sync-plugin
zip -r /tmp/notion-sync-0.4.0.plugin . \
  -x "*.DS_Store" "*/__pycache__/*" "*.pyc" ".git/*" "node_modules/*" "*.log" "_dist/*" ".notion-sync/*"
```

The output `/tmp/notion-sync-0.4.0.plugin` is your upload artifact.

**Option 3 — built by a packager skill** (e.g. workspace `cowork-plugin-packager`):
The packaged file lives at `<workspace>/ops/plugins/_dist/notion-sync-0.4.0.plugin` after the skill runs.

Then upload:

1. Open Claude Desktop → **Cowork** → **Plugins** in the sidebar.
2. Click **+ Add plugin** → **Upload a file** → select the `.plugin`.
3. Confirm install. Skills `/notion-setup` and `/sync` appear under the `/` menu.

**Pre-upload verification (recommended):**

```bash
# Confirm the manifest is at the zip root
unzip -l /tmp/notion-sync-0.4.0.plugin | head -20

# Confirm size is under 50 MB (this plugin packages to ~74 KB)
du -h /tmp/notion-sync-0.4.0.plugin
```

**Known quirks**:

- File size limit: **50 MB** (this plugin is ~74 KB).
- Some Claude Desktop builds reject `.plugin` extension at upload despite docs supporting it. **Workaround**: rename to `.zip` (contents identical). Tracked in [anthropics/claude-code#28337](https://github.com/anthropics/claude-code/issues/28337) and [#40414](https://github.com/anthropics/claude-code/issues/40414).
- The `.plugin` zip must have `.claude-plugin/plugin.json` at the **top level** (not nested inside an extra parent directory). The `zip` command above runs from inside the plugin dir specifically to avoid this.

**For organization-wide install**: **Organization settings** → **Plugins** → **Add plugins** → **Upload a file**.

---

### Claude Code CLI

**Best for**: developers working in the terminal, repos with `.mcp.json` already configured.

Two install scopes — **ask the user which one fits**:

- **Global** (every project on this machine): `claude plugins install github.com/montymerlin/notion-sync-plugin`
- **Local** (this project only, lives in `./.claude/plugins/`): symlink the cloned repo

**Global install:**

```bash
claude plugins install github.com/montymerlin/notion-sync-plugin
```

Or via marketplace:

```bash
claude plugins marketplace add notion-sync --url https://github.com/montymerlin/notion-sync-plugin/releases/download/latest/marketplace.json
claude plugins install notion-sync
```

**Local install** (project-scoped):

```bash
git clone https://github.com/montymerlin/notion-sync-plugin.git ~/src/notion-sync-plugin
mkdir -p ./.claude/plugins
ln -s ~/src/notion-sync-plugin ./.claude/plugins/notion-sync
```

Skills load automatically once installed. Type `/notion-setup` or `/sync` at the prompt, or invoke via natural language: "set up notion sync" or "sync my Notion database".

**Notion MCP setup** (required for sync to work):

```bash
claude mcp add -s user notion -- npx -y @notionhq/notion-mcp-server
export NOTION_API_KEY="secret_xxxxx"  # from notion.so/my-integrations
```

---

## Credentials & Authentication

### Notion API Token

The plugin uses the **Notion MCP connector** (included in Cowork; available for Claude Code via `claude mcp add`). You must have:

1. **Notion API key** — Create at https://www.notion.so/my-integrations
   - Click **+ New integration**
   - Name it "Claude Sync" or similar
   - Copy the **Internal Integration Token**
   - Paste into Cowork's Notion MCP setup or your Claude Code `.mcp.json`

2. **Database access** — Grant the integration access to each Notion database you want to sync:
   - Open the database in Notion
   - Click **...** (top-right) → **Connections**
   - Find and **connect** your integration

3. **Environment variable** (Claude Code CLI only):
   ```bash
   export NOTION_API_KEY="secret_xxxxx"
   ```

The `/notion-setup` skill will prompt you to select a database and confirm access during first-time configuration.

---

## Runtime Requirements

- **Python 3.8+** — Built-in on macOS and Linux; Windows users should have Python installed
- **Notion MCP connector** — Must be available in your Cowork session or Claude Code environment
- **No external Python dependencies** — Uses only the standard library (argparse, hashlib, json, re, pathlib, datetime)

Helper scripts in `scripts/` run automatically during `/notion-setup` and `/sync`:

- `build_markdown.py` — Converts Notion pages to local markdown with YAML frontmatter
- `push_markdown.py` — Prepares local markdown for Notion push; converts links, computes hashes
- `manifest.py` — Manages sync state, detects changes, bootstraps file tracking
- `link_registry.py` — Bidirectional file↔page ID mapping to eliminate slug-matching bugs

---

## Configuration

After `/notion-setup`, your project will have:

```
your-project/
├── .notion-sync/
│   ├── config.json          # Database ID, folders, property map (shareable)
│   ├── manifest.json        # Page tracking, sync state (personal — gitignore)
│   └── link-registry.json   # File↔page ID map (personal — gitignore)
├── research/                # Synced folder(s)
│   ├── page-one.md
│   └── page-two.md
```

**Sharing across collaborators**:

- **Commit** `config.json` — everyone needs the same database connection and property mappings
- **Gitignore** `manifest.json` and `link-registry.json` — these are personal sync state and API tokens
- Each collaborator runs `/notion-setup` once to create their own local state files

---

## Known Limits & Quirks

### Notion API Rate Limits

The Notion API enforces **3 requests per second** per API key. Large syncs (100+ pages) may hit this ceiling. The sync skill includes throttling and batching to stay under the limit; if you hit it, the skill will pause and retry.

### File Size Limit

The `.plugin` distribution is capped at **50 MB**. This plugin is 71 KB, so well under the limit.

### Content Hashing

Sync relies on **SHA-256 hashes** of page body text (first 16 hex chars, prefixed `sha256:`). If you manually edit frontmatter timestamps but not body text, the sync will not detect the change. This is intentional — sync tracks content, not metadata.

### Conflict Resolution

When both local and Notion versions have changed, `/sync` shows you a unified conflict plan and asks you to choose a resolution for each one. **Never auto-resolves** — conflicts always require user input.

### Link Conversion

Internal links (local markdown → Notion URLs, Notion URLs → local markdown) are tracked in `link-registry.json`. If you rename or move files outside of the sync skill, links may break. Use `/sync` to move files; the skill updates the registry automatically.

---

## Skills

| Skill           | Phrases                                              | What it does                                         |
|-----------------|------------------------------------------------------|------------------------------------------------------|
| `/notion-setup` | "set up notion sync", "connect notion", "link notion" | First-time config: database, folder, property mapping |
| `/sync`  | "sync", "notion sync", "pull from notion", "push"     | Bidirectional sync: detect, plan, resolve, execute   |

---

## Support & Feedback

- **Issues**: https://github.com/montymerlin/notion-sync-plugin/issues
- **Discussions**: https://github.com/montymerlin/notion-sync-plugin/discussions
- **Documentation**: See `README.md` for full feature overview and examples

---

## What's Next?

After installing, run `/notion-setup` to connect a Notion database. The skill will guide you through:

1. Selecting a Notion database
2. Choosing a local folder to sync
3. Mapping Notion properties to YAML frontmatter fields
4. Creating `.notion-sync/config.json`

Then use `/sync` whenever you want to pull changes from Notion or push local changes to Notion.

---

*notion-sync v0.3.0 | Python 3.8+ | MIT License*
