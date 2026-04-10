# CLAUDE.md — notion-cowork

Bidirectional sync between Notion databases and local markdown files for Claude Cowork.

## Project Identity

- **Name:** notion-cowork
- **Stack:** Python scripts + Markdown skill specs (Cowork plugin, zero runtime dependencies)
- **Purpose:** Keep a Notion database and local markdown folders in sync — changes flow both directions with conflict detection and user-driven resolution

## Directory Structure

```
notion-sync-plugin/
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest (name, version, metadata)
├── skills/
│   ├── notion-setup/
│   │   └── SKILL.md             # First-time configuration workflow
│   └── notion-sync/
│       ├── SKILL.md             # Bidirectional sync workflow
│       └── references/
│           ├── sync-engine.md   # Detailed sync mechanics
│           └── gotchas.md       # Operational knowledge from real incidents
├── scripts/
│   ├── build_markdown.py        # Notion → local: build markdown with YAML frontmatter
│   ├── push_markdown.py         # Local → Notion: strip frontmatter, convert links, hash
│   ├── link_registry.py         # Bidirectional file↔page ID mapping
│   └── manifest.py              # Manifest management CLI (bootstrap, diff, discover)
├── CLAUDE.md                    # This file — agent instructions
├── CHANGELOG.md                 # Narrative change history
├── DECISIONS.md                 # Architectural decision log
├── ROADMAP.md                   # Future directions
└── README.md                    # Human-facing overview
```

## Key Conventions

### This is a Cowork plugin

The primary deliverables are SKILL.md files (agent instructions) and Python helper scripts. There is no build step, no package manager, no test framework. Quality comes from clear instructions and correct scripts.

### Naming
- Files: kebab-case for documents, snake_case for Python scripts
- Skill directories: kebab-case matching the skill name
- Branches: `feature/short-description`, `fix/short-description`

### Commits
- Concise message focusing on "why" not "what"
- Reference decisions by number when relevant (e.g., "per Decision 003")
- Include `Co-Authored-By: Claude <noreply@anthropic.com>` when agent-assisted

### Documentation
- README.md is the human-facing overview — keep it current
- CLAUDE.md (this file) is the agent instruction set — update when conventions change
- DECISIONS.md logs architectural choices — add entries before implementing significant changes
- ROADMAP.md captures future directions — items flow to DECISIONS.md when evaluated
- CHANGELOG.md tracks evolution narratively — update after significant work sessions

### Skill files
- SKILL.md is the primary instruction set for each skill — it must be self-contained enough for an agent to follow without additional context
- `references/` subdirectories hold detailed mechanics and gotchas — skills reference these but don't duplicate their content
- Keep skills general-purpose — no workspace-specific config (database IDs, folder names, etc.)

### Scripts
- All scripts use argparse with subcommands, JSON output, and pathlib
- Scripts are importable as libraries (functions usable without CLI)
- Default paths assume `.notion-sync/` in the current working directory
- Content hashing: SHA-256 of body text, first 16 hex chars, prefixed `sha256:`

## Agent Boundaries

### Do
- Read this file first on every session
- Read the relevant SKILL.md and references before modifying sync logic
- Test scripts can parse without errors after editing
- Log decisions before implementing significant changes
- Update CHANGELOG.md after significant work sessions
- Keep skills generalizable — no hardcoded workspace data

### Don't
- Overwrite existing files without confirmation
- Hardcode database IDs, page IDs, or workspace-specific paths in skills or scripts
- Push content to Notion via subagents (fabrication risk — see gotchas.md)
- Skip the link registry when converting links (ad-hoc matching causes bugs)
- Auto-commit — always show changes and confirm with user

## Stack Conventions

- **Python 3.8+** — no external dependencies (stdlib only: argparse, hashlib, json, re, pathlib, datetime)
- **Type hints** encouraged on public functions
- **Docstrings** on every module and public function
- **JSON output** for all CLI commands (machine-readable, parseable by the agent)
- **No test framework** currently — verify scripts parse cleanly and produce expected JSON output

## Design Principles

1. **Scripts handle mechanics, skills handle orchestration** — Scripts do the deterministic work (hashing, link conversion, file building). Skills guide the agent through the judgment calls (conflict resolution, user confirmation, folder selection).

2. **Progressive disclosure** — Start simple. The setup skill creates minimal config; the sync skill adds complexity only when needed (conflicts, multi-folder, surgical edits).

3. **Generalizable over specific** — Every design choice in skills and scripts must work across any Notion database and any local folder structure. Workspace-specific config lives in `.notion-sync/config.json`, not in the plugin.

4. **Decisions as first-class artifacts** — Significant choices get logged in DECISIONS.md before implementation. This creates a searchable, auditable trail.

5. **Convention over configuration** — Prefer consistent patterns (kebab-case slugs, YAML frontmatter, SHA-256 hashes) over per-case options.

## References

- [DECISIONS.md](DECISIONS.md) — Architectural decision log
- [ROADMAP.md](ROADMAP.md) — Future directions and inspiration
- [CHANGELOG.md](CHANGELOG.md) — Narrative change history

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
