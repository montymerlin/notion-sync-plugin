# Changelog — notion-sync

A narrative record of how this plugin evolves. Updated after significant work sessions, not per-commit.

---

## 2026-04-21 — v0.2.1: Dual-distribution packaging

Added `marketplace.json` for Claude Code CLI installation via `claude plugins install`. Replaced the "This is a Cowork plugin" section in CLAUDE.md with a Distribution section covering both Claude Code CLI and Cowork install paths. Resolved the inconsistency where CLAUDE.md said "Cowork plugin" while README already showed dual-host installation. See Decision 006.

---

## 2026-04-10 — v0.2.0: Link registry, push scripts, multi-folder sync

Major upgrade based on learnings from the first real-world sync session (Bridging Worlds research commons, 46 pages). The session revealed that link conversion, initial population, and push preparation all required extensive ad-hoc scripting — this release eliminates that.

**New scripts:** `link_registry.py` (bidirectional file↔page ID mapping and link conversion), `push_markdown.py` (prepare local markdown for Notion push — strip frontmatter, convert links, compute hash).

**Upgraded scripts:** `manifest.py` gained three new commands: `bootstrap` (match local files to Notion pages by title/notion_id), `diff` (dry-run change preview), `discover` (find untracked files).

**Skill improvements:** Database query for exhaustive page discovery replaces semantic search. Multi-folder config (`sync_folders` array). Script-based push workflow. `replace_content` vs `update_content` decision guidance. Link registry rebuild after every sync.

**Reference docs expanded:** gotchas.md covers hash timing, short slugs, schema validation. sync-engine.md documents the link registry, push pipeline, and multi-folder discovery.

Also adopted the agentic scaffold (CLAUDE.md, DECISIONS.md, CHANGELOG.md, ROADMAP.md) for structured project governance.

---

## 2026-03 — v0.1.0: Initial release

First working version of the plugin. Two skills (`/notion-setup` and `/notion-sync`), two helper scripts (`build_markdown.py` and `manifest.py`), and reference documentation covering sync mechanics and operational gotchas. Supports bidirectional sync with content hashing, timestamp-based change detection, conflict resolution, and YAML frontmatter ↔ Notion property mapping.

<!-- Agentic Scaffold v0.1.0 | adapted for Cowork plugin conventions -->
