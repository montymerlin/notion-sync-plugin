# AGENTS.md — notion-sync

Canonical repo instructions for `notion-sync-plugin`.

## Project Identity

- **Name:** notion-sync
- **Type:** Host-agnostic Notion ↔ markdown sync skills + Python helpers, with Claude plugin packaging compatibility
- **Version:** 0.4.0
- **Stack:** Python scripts (stdlib only) + Markdown skill specs
- **Purpose:** Keep a Notion database and local markdown folders in sync — changes flow both directions with conflict detection and user-driven resolution
- **Repository:** https://github.com/montymerlin/notion-sync-plugin

## Canonical Structure

```
notion-sync-plugin/
├── .claude-plugin/
│   ├── plugin.json              # Plugin manifest (name, version, metadata)
│   └── marketplace.json         # Self-hosted marketplace listing
├── skills/
│   ├── notion-setup/
│   │   └── SKILL.md             # First-time configuration workflow
│   └── sync/
│       ├── SKILL.md             # Bidirectional sync workflow (runtime ID: notion-sync:sync)
│       └── references/
│           ├── sync-engine.md   # Detailed sync mechanics
│           └── gotchas.md       # Operational knowledge from real incidents
├── scripts/
│   ├── build_markdown.py        # Notion → local: build markdown with YAML frontmatter
│   ├── push_markdown.py         # Local → Notion: strip frontmatter, convert links, hash
│   ├── link_registry.py         # Bidirectional file↔page ID mapping
│   └── manifest.py              # Manifest management CLI (bootstrap, diff, discover)
├── docs/
│   └── superpowers/             # Plans and specs from past iterations (writing-plans skill output)
├── AGENTS.md                    # Canonical repo instructions
├── CLAUDE.md                    # Claude compatibility wrapper
├── SETUP.md                     # Canonical install + compatibility reference (all hosts)
├── CHANGELOG.md                 # Narrative change history
├── DECISIONS.md                 # Architectural decision log
├── ROADMAP.md                   # Future directions
├── README.md                    # Human-facing overview
└── .gitignore
```

## Canonical Rules

- `AGENTS.md` is the canonical instruction file for this repo.
- `CLAUDE.md` is a thin compatibility layer that points Claude-family hosts back to `AGENTS.md`.
- `skills/` and `scripts/` are the product. Skills hold orchestration; scripts hold deterministic mechanics.
- `.claude-plugin/` is Claude-specific packaging metadata, not the source of truth for skills or scripts.
- Workspace-specific config (database IDs, folder names, property maps) lives in the user's `.notion-sync/config.json`, never in the plugin.

## Packaging for Cowork

Cowork install is via a `.plugin` zip uploaded through Claude Desktop. Two paths:

1. **Use a packager skill** (e.g. the `cowork-plugin-packager` skill if installed in your workspace) — runs validation, packaging, and verification. Produces `notion-sync-<version>.plugin`.
2. **Build by hand** — see `SETUP.md` § "Cowork (Claude Desktop)" for the raw `zip` command and verification steps.

`SETUP.md` is the single source of truth for install pathways across Cowork, Claude Code CLI, Agent SDK, and direct API use — read it before changing install or packaging behavior.

## Runtime Conventions

- **Python 3.8+, stdlib only** — no external dependencies. Scripts use argparse, hashlib, json, re, pathlib, datetime.
- **Notion access via MCP** — the plugin assumes a Notion MCP connector is present in the host. The sync skill uses `notion-search`, `notion-fetch`, `notion-update-page`, and `notion-create-pages`.
- **Default state location** — scripts default to `.notion-sync/` in the current working directory. Override via `--config` and `--manifest` flags when needed.
- **Content hashing** — SHA-256 of body text, first 16 hex chars, prefixed `sha256:`. Tracks content, not metadata.
- **Push path is deterministic** — `push_markdown.py push-content` calls the Notion Blocks API directly (not via LLM-generated `new_str`) to eliminate content fabrication risk on large documents (see Decision 007).

## Documentation Rules

- README.md is human-facing.
- AGENTS.md is the canonical agent-facing document.
- CLAUDE.md exists for compatibility only and should stay short.
- SETUP.md is the canonical install + compatibility reference (all hosts).
- DECISIONS.md logs major structural choices before implementation.
- ROADMAP.md holds future ideas until they become decisions.
- CHANGELOG.md records narrative milestones after significant work.
- Skill `references/` files hold detailed mechanics and gotchas — skills reference these but don't duplicate the content.

## Naming

- Files: kebab-case for documents, snake_case for Python scripts
- Skill directories: kebab-case matching the skill's `name:` frontmatter
- Skill `name:` frontmatter: bare dir name (e.g. `notion-setup`, `notion-sync`) — host prepends the plugin name (`notion-sync:`) automatically; do NOT namespace the skill name manually
- Branches: `feature/short-description`, `fix/short-description`

## Design Principles

1. **Scripts handle mechanics, skills handle orchestration** — Scripts do the deterministic work (hashing, link conversion, file building, direct API calls). Skills guide the agent through the judgment calls (conflict resolution, user confirmation, folder selection).
2. **Progressive disclosure** — Start simple. The setup skill creates minimal config; the sync skill adds complexity only when needed (conflicts, multi-folder, surgical edits).
3. **Generalizable over specific** — Every design choice in skills and scripts must work across any Notion database and any local folder structure. Workspace-specific config lives in `.notion-sync/config.json`, not in the plugin.
4. **Compatibility layers, not duplicate sources** — `CLAUDE.md` and `marketplace.json` are compatibility wrappers; AGENTS.md and plugin.json are canonical.
5. **Cross-host portability** — the plugin runs in any host that supports MCP and skills. Don't assume Cowork or Claude Code specifically.
6. **No content fabrication via LLM** — push paths must use direct API calls, never `notion-update-page(replace_content, new_str=...)` for body content (LLM-generated `new_str` causes fabrication on large pages).

## Boundaries

### Do
- Read AGENTS.md first on every session
- Read the relevant SKILL.md and `references/` before modifying sync logic
- Test scripts can parse cleanly and produce valid JSON output after editing
- Log decisions in DECISIONS.md before implementing significant changes
- Update CHANGELOG.md after significant work sessions
- Keep skills generalizable — no hardcoded workspace data
- Update docs and metadata together when conventions change

### Don't
- Reintroduce `CLAUDE.md` as the canonical repo instruction file
- Overwrite existing files without confirmation
- Hardcode database IDs, page IDs, or workspace-specific paths in skills or scripts
- Push content to Notion via subagents or LLM-generated payloads (fabrication risk — see `gotchas.md` and Decision 007)
- Skip the link registry when converting links (ad-hoc matching causes bugs — see Decision 006)
- Auto-commit — always show changes and confirm with the user

## References

- [DECISIONS.md](DECISIONS.md) — Architectural decision log
- [ROADMAP.md](ROADMAP.md) — Future directions and inspiration
- [CHANGELOG.md](CHANGELOG.md) — Narrative change history
- [SETUP.md](SETUP.md) — Install + compatibility reference

<!-- Adapted from agentic-scaffold conventions; AGENTS.md added 2026-04-27 as canonical instruction file -->
