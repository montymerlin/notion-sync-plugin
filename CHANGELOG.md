# Changelog — notion-sync

A narrative record of how this plugin evolves. Updated after significant work sessions, not per-commit.

---

## 2026-04-22 — v0.3.0: Direct Blocks API push, manifest v2, targeted diffs

The biggest architectural change since v0.2.0. Driven by a real failure: the EthicHub document (85K chars, ~300 blocks) came back from a push as visibly AI-regenerated prose — structure intact, content rewritten. The root cause is that `notion-update-page(replace_content, new_str=...)` generates `new_str` token-by-token through the LLM, making content drift near-certain for large documents.

**Content fabrication eliminated:** `push_markdown.py` gains a `push-content` subcommand that reads the prepared staging file as bytes and calls the Notion Blocks API directly. No LLM in the data path. Requires a Notion Internal Integration token stored in `.notion-sync/.env`. The `/notion-setup` skill has a new Step 5 that walks through token creation and verification.

**Metadata-first diffing:** `manifest.py` upgraded to v2 with a `"properties"` snapshot per page (keyed by `yaml_key`). The `diff` command now outputs a `push_target` field (`properties_only`, `content_only`, `both`, `none`) by comparing frontmatter fields against the manifest snapshot independently of the content hash. Property-only changes (e.g. updating `research_stage` in frontmatter) are now fast, targeted operations that skip the Blocks API entirely.

**Two-channel push:** `push_markdown.py push-properties` outputs a JSON payload for `notion-update-page(update_properties)` via MCP — no token needed, no fabrication risk. `push-content` handles body writes via direct API. The sync skill Step 6 is fully rewritten to route on `push_target`.

**Bug fixes:** `link_registry.py` `build()` was iterating manifest pages as a list instead of a dict — causing `AttributeError` on every build. Unresolved push links were emitting `<!-- unresolved: path -->` HTML comments that rendered as visible text in Notion; now renders as `text *(local file)*` per spec.

**Refactor:** Removed duplicate `load_link_registry()` and `convert_links()` from `push_markdown.py` (they had incompatible registry format expectations with `link_registry.py`). `push_markdown.py` now imports `LinkRegistry` directly.

**Reasoning artifacts:** Decision 007 (direct API push) and Decision 008 (manifest v2 property snapshots) in `DECISIONS.md`. Four new `ROADMAP.md` items: per-file sync opt-out, CDN image hosting, multi-operator support, page lock after push.

---

## 2026-04-22 — v0.2.2: Audit fixes

Reordered ROADMAP Decided section chronologically (001→006). Added Decision 006 (dual-distribution packaging) to the Decided section, which was missing despite the decision existing in DECISIONS.md. No functional changes.

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
